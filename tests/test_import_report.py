"""Report strutturato con transazioni isolate e XML sintetici."""
import csv
import io
from pathlib import Path
from unittest.mock import patch
from werkzeug.datastructures import FileStorage

from test_import_lifecycle import ImportTestCase, invoice
from app.services import import_service, import_recovery_service as recovery
from app.models import Document
from uuid import uuid4


class ImportReportTests(ImportTestCase):
    def test_history_and_import_date_are_visible(self):
        from datetime import datetime
        from app.extensions import db
        from app.models import ImportLog
        client = self.app.test_client()
        batch_id = str(uuid4())
        for content in (invoice(), invoice(), b"invalid xml"):
            client.post("/import/run", data={"batch_id": batch_id,
                "files": (io.BytesIO(content), "history.xml")}, headers={"Accept": "application/json"})
        doc = Document.query.one()
        doc.imported_at = datetime(2026, 9, 24, 7, 13)
        db.session.commit()
        db.session.connection().connection.driver_connection.create_function(
            "year", 1, lambda value: int(value[:4]) if value else None)
        page = client.get("/import/history?file=history.xml")
        self.assertEqual(page.status_code, 200)
        for label in ("Registrato", "Già presente", "Fallito", batch_id):
            self.assertIn(label, page.get_data(as_text=True))
        for url in ("/documents/review/list", f"/documents/{doc.id}"):
            page = client.get(url)
            self.assertEqual(page.status_code, 200)
            self.assertIn("24/09/2026 07:13", page.get_data(as_text=True))
        for index in range(51):
            db.session.add(ImportLog(file_name="page_test.xml", status="error", message=f"legacy-{index}"))
        db.session.commit()
        first = client.get("/import/history?file=page_test.xml").get_data(as_text=True)
        self.assertIn("legacy-50", first)
        self.assertNotIn("legacy-0<", first)
        from app.repositories.import_log_repo import import_history_page
        rows = import_history_page(file_name="page_test.xml")
        second = client.get(f"/import/history?file=page_test.xml&before={rows[49].id}").get_data(as_text=True)
        self.assertIn("legacy-0", second)
        self.assertNotIn("legacy-50", second)
        self.assertIn("Nessun import trovato", client.get("/import/history?file=nonexistent").get_data(as_text=True))

    def test_route_recovers_batch_without_original_browser_cookie(self):
        batch_id = str(uuid4())
        client = self.app.test_client()
        response = client.post("/import/run", data={
            "batch_id": batch_id, "files": (io.BytesIO(invoice()), "originale.xml"),
        }, headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 200)
        summary = response.get_json()
        self.assertEqual(summary["imported"], 1, summary)
        self.assertIn("/documents/", summary["details"][0]["document_url"])
        self.assertLess(len(response.headers.get("Set-Cookie", "")), 1000)
        other_browser = self.app.test_client()
        page = other_browser.get("/import/run?batch_id=" + batch_id)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Cliente prova", page.data)
        self.assertIn(b"Report CSV", page.data)
        state = other_browser.get("/import/status/" + batch_id).get_json()
        self.assertEqual(state["imported"], 1)
        self.assertEqual(len(state["report_paths"]), 1)

    def test_upload_same_name_different_content_and_report(self):
        files = [FileStorage(io.BytesIO(invoice((number,))), filename="originale.xml")
                 for number in ("A/1", "A/2")]
        summary = import_service.run_import_files(files, batch_id="report-test")
        self.assertEqual(summary["imported"], 2, summary)
        self.assertEqual(summary["total_files"], 2)
        with Path(summary["report_path"]).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual({row["document_number"] for row in rows}, {"A/1", "A/2"})
        self.assertTrue(all(row["legal_entity_name"] == "Cliente prova" for row in rows))
        self.assertTrue(all(row["attempt_id"] for row in rows))
        self.assertEqual(recovery.batch_summary("report-test")["imported"], 2)

    def test_duplicate_has_existing_link_and_precise_criterion(self):
        self.run_file()
        summary = import_service.run_import_files([FileStorage(io.BytesIO(invoice()), filename="rinominata.xml")])
        self.assertEqual(summary["skipped"], 1, summary)
        row = summary["details"][0]
        self.assertEqual(row["duplicate_reason"], "file_hash")
        self.assertEqual(row["same_file_name"], "no")
        self.assertEqual(row["invoice_id"], Document.query.one().id)

    def test_report_failure_cannot_reverse_committed_import(self):
        with patch.object(import_service, "_write_import_report", return_value=None):
            summary = import_service.run_import_files([FileStorage(io.BytesIO(invoice()), filename="originale.xml")])
        self.assertEqual(summary["imported"], 1, summary)
        self.assertEqual(summary["errors"], 0)
