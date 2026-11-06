"""Conteggi e filtri su batch completi, senza database operativo."""
import json
import io
from datetime import datetime, date
from uuid import uuid4
from unittest.mock import patch

from test_import_lifecycle import ImportTestCase, invoice
from app.extensions import db
from app.models import Document, ImportLog
from app.services.import_history_service import history_page, present_summary


class ImportHistoryTests(ImportTestCase):
    def add_attempt(self, batch, state="committed", name="file.xml", number="A/1", warnings=None):
        attempt = str(uuid4())
        payload = {"version": 1, "kind": "attempt", "batch_id": batch,
                   "attempt_id": attempt, "state": state, "warnings": warnings or [],
                   "details": [{"document_number": number, "status": "success" if state == "committed" else "skipped"}]}
        db.session.add(ImportLog(file_name=name, status="error" if state == "failed" else "success",
                                 message=json.dumps(payload), created_at=datetime(2026, 11, 5, 10)))
        db.session.flush()
        return payload

    def test_large_batch_is_complete_and_bodies_are_not_counted(self):
        batch = str(uuid4())
        for index in range(61):
            payload = self.add_attempt(batch, name=f"file{index}.xml")
            db.session.add(ImportLog(file_name=f"file{index}.xml", status="success",
                message=json.dumps({"version": 1, "kind": "body", "attempt_id": payload["attempt_id"]})))
        db.session.commit()
        groups, cursor = history_page(search="file60.xml")
        self.assertEqual(len(groups), 1)
        self.assertEqual((groups[0]["files"], groups[0]["imported"]), (61, 61))
        self.assertIsNone(cursor)

    def test_global_filters_and_pagination_do_not_drop_group_members(self):
        old = str(uuid4())
        self.add_attempt(old, state="failed", name="old.xml", number="FAIL/1")
        for _ in range(26):
            self.add_attempt(str(uuid4()))
        self.add_attempt(old, state="duplicate", name="retry.xml")
        db.session.commit()
        groups, _ = history_page(outcome="problems", search="FAIL/1", since=date(2026, 11, 5), until=date(2026, 11, 5))
        self.assertEqual(len(groups), 1)
        self.assertEqual((groups[0]["files"], groups[0]["errors"], groups[0]["skipped"]), (2, 1, 1))
        first, cursor = history_page()
        second, _ = history_page(before=cursor)
        self.assertEqual(len(first), 25)
        self.assertEqual(len(second), 2)
        self.assertNotIn(old, {g["batch_id"] for g in second})
        self.assertEqual(history_page(until=date(2026, 11, 4))[0], [])

    def test_warnings_pending_and_legacy_remain_visible(self):
        self.add_attempt(str(uuid4()), warnings=["Archive incomplete"])
        self.add_attempt(str(uuid4()), state="started")
        db.session.add(ImportLog(file_name="legacy.xml", status="duplicate", message="old message"))
        db.session.add(ImportLog(file_name="unlinked.xml", status="success", message="Import completato"))
        db.session.commit()
        self.assertEqual(len(history_page(outcome="warnings")[0]), 1)
        self.assertEqual(len(history_page(outcome="pending")[0]), 2)
        legacy = history_page(search="legacy.xml")[0][0]
        self.assertTrue(legacy["legacy"])
        self.assertEqual(legacy["skipped"], 1)
        self.assertEqual(history_page(search="unlinked.xml")[0][0]["imported"], 0)

    def test_detail_groups_bodies_and_uses_real_import_date(self):
        details = [dict(file_name="multi.xml", attempt_id="a", invoice_id=7,
                        document_date="2026-10-01", status="skipped"),
                   dict(file_name="multi.xml", attempt_id="a", status="success"),
                   dict(file_name="bad.xml", attempt_id="b", status="conflict"),
                   dict(file_name="multi.xml", status="warning", message="archive warning")]
        with patch("app.services.import_history_service.registry.document_import_dates", return_value={7: datetime(2026, 11, 3, 12, 43)}):
            summary = present_summary({"details": details})
        self.assertEqual(len(summary["file_groups"]), 2)
        self.assertEqual(summary["file_groups"][0]["category"], "problems")
        self.assertEqual(details[0]["existing_imported_at"], "03/11/2026 12:43:00 UTC")
        self.assertEqual(details[0]["document_date"], "2026-10-01")
        with patch("app.services.import_history_service.registry.document_import_dates", return_value={}):
            present_summary({"details": details})
        self.assertIsNone(details[0]["existing_imported_at"])

    def test_multiple_bodies_are_expandable_in_one_file_row(self):
        from flask import render_template
        details = [dict(file_name="multi.xml", attempt_id="a", status="success",
                        document_number=f"A/{n}", message="Documento registrato") for n in (1, 2)]
        summary = present_summary({"details": details, "total_files": 1, "imported": 2,
            "skipped": 0, "errors": 0, "warnings": 0, "report_paths": []})
        with self.app.test_request_context():
            page = render_template("import/import_run.html", summary=summary)
        self.assertEqual(page.count('data-category="success"'), 1)
        self.assertIn("Altri esiti nello stesso file (1)", page)
        self.assertIn("A/1", page)
        self.assertIn("A/2", page)

    def test_history_filters_escape_html_and_validate_dates(self):
        batch = str(uuid4())
        self.add_attempt(batch, name="<script>alert(1)</script>.xml", state="failed")
        db.session.add(ImportLog(file_name="<script>legacy</script>.xml", status="error", message="old"))
        db.session.commit()
        client = self.app.test_client()
        page = client.get("/import/history?outcome=problems")
        self.assertEqual(page.status_code, 200)
        self.assertIn(batch, page.get_data(as_text=True))
        self.assertIn("&lt;script&gt;legacy&lt;/script&gt;.xml", page.get_data(as_text=True))
        self.assertNotIn("<script>legacy</script>", page.get_data(as_text=True))
        for args in ("since=bad", "since=2026-11-06&until=2026-11-01", "outcome=bogus"):
            self.assertEqual(client.get("/import/history?" + args).status_code, 400)

    def test_duplicate_dates_and_filters_in_live_response_and_reopened_page(self):
        self.run_file()
        doc = Document.query.one()
        doc.imported_at = datetime(2026, 11, 3, 12, 43)
        db.session.commit()
        batch = str(uuid4())
        client = self.app.test_client()
        result = client.post("/import/run", data={"batch_id": batch,
            "files": (io.BytesIO(invoice()), "invoice&copy.xml")},
            headers={"Accept": "application/json"})
        self.assertEqual(result.status_code, 200)
        summary = result.get_json()
        self.assertEqual(summary["skipped"], 1, summary)
        self.assertEqual(len(summary["file_groups"]), 1)
        self.assertEqual(summary["details"][0]["existing_imported_at"], "03/11/2026 12:43:00 UTC")
        page = client.get("/import/run?batch_id=" + batch).get_data(as_text=True)
        self.assertIn("03/11/2026 12:43:00 UTC", page)
        self.assertIn("Emessa il 2026-09-26", page)
        self.assertIn("invoice&amp;copy.xml", page)
        self.assertIn("data-outcome-filter", page)
