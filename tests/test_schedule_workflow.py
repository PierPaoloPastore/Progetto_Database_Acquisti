"""Run: python -B -m unittest discover -s tests -p test_schedule_workflow.py -v."""
import hashlib
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from itsdangerous import SignatureExpired
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from sqlalchemy import text

from app.extensions import JsonFormatter, db
from app.middleware.auth_stub import init_auth_stub
from app.models import Document, DocumentAuditLog, LegalEntity, Supplier
from app.services import document_service, schedule_service
from app.repositories.document_audit_log_repo import DocumentAuditLogRepository
from app.web import routes_payments as routes


class ScheduleWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="test-only-key", TESTING=True,
                               SQLALCHEMY_DATABASE_URI="sqlite://")
        db.init_app(self.app)
        init_auth_stub(self.app)
        self.app.register_blueprint(routes.payments_bp, url_prefix="/payments")
        self.app.add_url_rule("/documents/<int:document_id>", endpoint="documents.detail_view", view_func=lambda document_id: "")
        self.app.add_url_rule("/help/<slug>", endpoint="help.guide_view", view_func=lambda slug: "")
        templates = Path(__file__).resolve().parents[1] / "app/templates"
        self.app.jinja_loader = ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}"}),
            FileSystemLoader(str(templates)),
        ])
        self.app.jinja_env.filters.update(format_amount=str, format_int=str)
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(lambda: db.engine.dispose())
        self.addCleanup(db.session.remove)
        # SQLite richiede INTEGER per l'autoincremento della PK, MySQL usa BIGINT.
        with db.engine.begin() as connection:
            connection.execute(text("CREATE TABLE document_audit_logs (id INTEGER PRIMARY KEY, "
                                    "document_id INTEGER, action VARCHAR(16) NOT NULL, "
                                    "payload TEXT, created_at DATETIME NOT NULL)"))
        db.create_all()
        supplier = Supplier(name="Fornitore prova")
        entity = LegalEntity(name="Intestatario prova", vat_number="00000000000")
        db.session.add_all([supplier, entity])
        db.session.flush()
        for document_id in (1, 2, 3):
            db.session.add(Document(id=document_id, document_type="invoice",
                                    document_number=f"TEST-{document_id}", supplier_id=supplier.id,
                                    legal_entity_id=entity.id, total_gross_amount=100,
                                    total_taxable_amount=80, document_date=date(2026, 11, 1)))
        db.session.commit()
        self.client = self.app.test_client()
        self.pdf = b"%PDF-1.4 test generated PDF"
        self.renderer = patch.object(routes, "render_pdf_from_html", return_value=self.pdf).start()
        self.addCleanup(patch.stopall)
        patch.object(routes, "get_setting", side_effect=lambda key, default: default).start()

    def generate(self, ids="1,2"):
        response = self.client.post("/payments/schedule/print", data={"document_ids": ids},
                                    headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.headers["X-Schedule-Token"]

    def flags(self):
        db.session.expire_all()
        return [doc.print_status for doc in db.session.query(Document).order_by(Document.id)]

    def events(self, action):
        return db.session.query(DocumentAuditLog).filter_by(action=action).all()

    def test_generation_does_not_program_and_records_exact_pdf(self):
        self.generate()
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        event = self.events("schedule_gen")[0]
        payload = json.loads(event.payload)
        self.assertEqual([doc["id"] for doc in schedule_service.generation_documents(payload)], [1, 2])
        self.assertEqual(payload["pdf_sha256"], hashlib.sha256(self.pdf).hexdigest())
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["actor"]["identity_source"], "CurrentUserStub")
        self.assertIn(payload["schedule_id"], self.renderer.call_args.args[0])

    def test_confirmation_uses_generated_list_ignoring_new_selection(self):
        token = self.generate()
        preview = self.client.post("/payments/schedule/preview", data={"token": token}).json
        self.assertEqual([doc["id"] for doc in preview["documents"]], [1, 2])
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        response = self.client.post("/payments/schedule/confirm", data={"token": token, "document_ids": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.flags(), ["programmed", "programmed", "not_printed"])
        self.assertEqual({row.document_id for row in self.events("schedule_confirm")}, {1, 2})

    def test_http_trace_correlates_audit_logs_and_each_response(self):
        with self.assertLogs(level="INFO") as captured:
            generated = self.client.post("/payments/schedule/print", data={"document_ids": "1,2"},
                                         headers={"X-Schedule-Action": "schedule.generate"})
            token = generated.headers["X-Schedule-Token"]
            confirmed = self.client.post("/payments/schedule/confirm?secret=query-secret",
                                         data={"token": token, "password": "form-secret"}, headers={
                                             "X-Schedule-Action": "schedule.confirm_print",
                                             "X-Request-ID": "client-chosen-id",
                                             "Authorization": "Bearer authorization-secret",
                                             "User-Agent": "Schedule test browser",
                                         })
            unmarked = self.client.post("/payments/schedule/unprogram", data={"document_ids": "1,2"},
                                        headers={"X-Schedule-Action": "schedule.unprogram"})
        request_ids = [response.headers["X-Request-ID"] for response in (generated, confirmed, unmarked)]
        self.assertEqual(len(set(request_ids)), 3)
        entries = [json.loads(JsonFormatter().format(record))["extra"] for record in captured.records]
        for response, action, endpoint, handler, ui_action, log_event in (
            (generated, "schedule_gen", "schedule_print", "schedule_print", "schedule.generate", "generated"),
            (confirmed, "schedule_confirm", "schedule_confirm", "schedule_finish", "schedule.confirm_print", "confirmed"),
            (unmarked, "schedule_unmark", "schedule_unprogram", "schedule_unprogram", "schedule.unprogram", "unprogrammed"),
        ):
            with self.subTest(action=action):
                self.assertEqual(response.status_code, 200)
                request_id = response.headers["X-Request-ID"]
                self.assertRegex(request_id, r"^[0-9a-f]{32}$")
                events = self.events(action)
                self.assertTrue(events)
                for event in events:
                    actor = json.loads(event.payload)["actor"]
                    self.assertEqual(actor["request_id"], request_id)
                    self.assertEqual(actor["method"], "POST")
                    self.assertEqual(actor["endpoint"], f"payments.{endpoint}")
                    self.assertEqual(actor["handler"], f"app.web.routes_payments.{handler}")
                    self.assertEqual(actor["ui_action"], ui_action)
                    if action == "schedule_confirm":
                        self.assertEqual(actor["path"], "/payments/schedule/confirm")
                        self.assertEqual(actor["user_agent"], "Schedule test browser")
                matching_logs = [entry for entry in entries if entry.get("request_id") == request_id]
                self.assertEqual({entry["schedule_event"] for entry in matching_logs}, {log_event, "http_request"})
                for entry in matching_logs:
                    self.assertEqual(entry["actor"]["request_id"], request_id)
                http_log = next(entry for entry in matching_logs if entry["schedule_event"] == "http_request")
                self.assertEqual(http_log["status_code"], response.status_code)
        generation = json.loads(self.events("schedule_gen")[0].payload)
        self.assertEqual(generation["closed_by"]["request_id"], confirmed.headers["X-Request-ID"])
        stored = " ".join(event.payload for event in db.session.query(DocumentAuditLog))
        logged = " ".join(JsonFormatter().format(record) for record in captured.records)
        for secret in (token, "query-secret", "form-secret", "authorization-secret", "client-chosen-id"):
            self.assertNotIn(secret, stored + logged)
        self.assertEqual(self.flags(), ["not_printed"] * 3)

    def test_http_trace_on_rejection_and_unknown_client_action(self):
        with self.assertLogs(level="INFO") as captured:
            rejected = self.client.post("/payments/schedule/confirm", data={"token": "invalid-secret"},
                                        headers={"X-Schedule-Action": "unknown-client-action"})
        self.assertEqual(rejected.status_code, 409)
        request_id = rejected.headers["X-Request-ID"]
        entries = [json.loads(JsonFormatter().format(record))["extra"] for record in captured.records]
        self.assertEqual({entry["schedule_event"] for entry in entries}, {"rejected", "http_request"})
        for entry in entries:
            self.assertEqual(entry["request_id"], request_id)
            self.assertEqual(entry["actor"]["endpoint"], "payments.schedule_confirm")
            self.assertIsNone(entry["actor"]["ui_action"])
        logged = " ".join(JsonFormatter().format(record) for record in captured.records)
        self.assertNotIn("invalid-secret", logged)
        self.assertNotIn("unknown-client-action", logged)
        self.assertFalse(self.events("schedule_confirm"))
        self.assertEqual(self.flags(), ["not_printed"] * 3)

        token = self.generate("1")
        response = self.client.post("/payments/schedule/confirm", data={"token": token},
                                    headers={"X-Schedule-Action": "schedule.unprogram"})
        self.assertEqual(response.status_code, 200)
        actor = json.loads(self.events("schedule_confirm")[0].payload)["actor"]
        self.assertEqual(actor["endpoint"], "payments.schedule_confirm")
        self.assertIsNone(actor["ui_action"])

    def test_cancel_does_not_program_and_cannot_be_confirmed_later(self):
        token = self.generate()
        response = self.client.post("/payments/schedule/cancel", data={"token": token},
                                    headers={"X-Schedule-Action": "schedule.cancel"})
        self.assertEqual(response.status_code, 200)
        actor = json.loads(self.events("schedule_cancel")[0].payload)["actor"]
        self.assertEqual(actor["request_id"], response.headers["X-Request-ID"])
        self.assertEqual(actor["ui_action"], "schedule.cancel")
        self.assertEqual(self.client.post("/payments/schedule/confirm", data={"token": token}).status_code, 409)
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        self.assertEqual(len(self.events("schedule_cancel")), 1)

    def test_replay_does_not_duplicate_audit_or_reprogram_after_unmark(self):
        token = self.generate()
        confirmed = self.client.post("/payments/schedule/confirm", data={"token": token})
        self.client.post("/payments/schedule/unprogram", data={"document_ids": "1,2"})
        with self.assertLogs(self.app.logger, level="INFO") as captured:
            response = self.client.post("/payments/schedule/confirm", data={"token": token})
        self.assertTrue(response.json["already_done"])
        self.assertNotEqual(response.headers["X-Request-ID"], confirmed.headers["X-Request-ID"])
        self.assertEqual(captured.records[0].schedule_event, "http_request")
        self.assertEqual(captured.records[0].request_id, response.headers["X-Request-ID"])
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        self.assertEqual(len(self.events("schedule_confirm")), 2)
        self.assertEqual(len(self.events("schedule_unmark")), 2)

    def test_changed_document_rejects_entire_confirmation(self):
        token = self.generate()
        db.session.get(Document, 2).total_gross_amount = 101
        db.session.commit()
        self.assertEqual(self.client.post("/payments/schedule/confirm", data={"token": token}).status_code, 409)
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        self.assertFalse(self.events("schedule_confirm"))

    def test_paid_document_rejects_entire_confirmation(self):
        token = self.generate()
        db.session.get(Document, 2).is_paid = True
        db.session.commit()
        self.assertEqual(self.client.post("/payments/schedule/confirm", data={"token": token}).status_code, 409)
        self.assertEqual(self.flags(), ["not_printed"] * 3)

    def test_token_requires_original_session_and_valid_signature(self):
        token = self.generate()
        other_client = self.app.test_client()
        self.assertEqual(other_client.post("/payments/schedule/confirm", data={"token": token}).status_code, 409)
        self.assertEqual(self.client.post("/payments/schedule/confirm", data={"token": token + "broken"}).status_code, 409)
        with patch.object(routes, "_schedule_signer") as signer:
            signer.return_value.loads.side_effect = SignatureExpired("expired")
            self.assertEqual(self.client.post("/payments/schedule/confirm", data={"token": token}).status_code, 409)
        self.assertEqual(self.flags(), ["not_printed"] * 3)

    def test_audit_failure_rolls_back_flags_and_generation_outcome(self):
        token = self.generate()
        original_add = DocumentAuditLogRepository.add
        calls = 0

        def fail_second(repository, event):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("audit unavailable")
            return original_add(repository, event)

        with patch.object(DocumentAuditLogRepository, "add", fail_second):
            with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
                self.client.post("/payments/schedule/confirm", data={"token": token})
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        self.assertFalse(self.events("schedule_confirm"))
        self.assertEqual(json.loads(self.events("schedule_gen")[0].payload)["status"], "pending")

    def test_generation_failure_and_unavailable_selection_are_audited(self):
        self.renderer.return_value = None
        response = self.client.post("/payments/schedule/print", data={"document_ids": "1"},
                                    headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 501)
        response = self.client.post("/payments/schedule/print", data={"document_ids": "1,99"},
                                    headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.events("schedule_failed")), 2)
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        self.assertFalse(self.events("schedule_gen"))

    def test_render_exception_is_audited_without_programming(self):
        self.renderer.side_effect = RuntimeError("renderer crashed")
        with self.assertLogs(self.app.logger, level="ERROR") as captured:
            response = self.client.post("/payments/schedule/print", data={"document_ids": "1"},
                                        headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(self.events("schedule_failed")[0].payload)["reason"], "pdf_render_error")
        actor = json.loads(self.events("schedule_failed")[0].payload)["actor"]
        self.assertEqual(actor["request_id"], response.headers["X-Request-ID"])
        self.assertEqual(captured.records[0].request_id, actor["request_id"])
        self.assertEqual(self.flags(), ["not_printed"] * 3)

    def test_supplier_iban_change_invalidates_printed_snapshot(self):
        token = self.generate()
        db.session.query(Supplier).one().iban = "CHANGED"
        db.session.commit()
        with self.assertLogs(self.app.logger, level="WARNING"):
            response = self.client.post("/payments/schedule/confirm", data={"token": token})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.flags(), ["not_printed"] * 3)

    def test_generation_audit_failure_prevents_delivery(self):
        with patch.object(DocumentAuditLogRepository, "add", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
                self.generate()
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        self.assertFalse(self.events("schedule_gen"))

    def test_review_preserves_programming_and_audit_is_readable(self):
        token = self.generate("1")
        self.client.post("/payments/schedule/confirm", data={"token": token})
        document_service.update_document_status(1, "verified")
        self.assertEqual(self.flags(), ["programmed", "not_printed", "not_printed"])
        events = document_service.list_document_audit_logs()
        generated = next(event for event in events if event["action"] == "schedule_gen")
        self.assertEqual(len(generated["schedule_documents"]), 1)
        self.assertIn("operatore non autenticato", generated["summary"])
        self.assertIn("confermato", generated["summary"])
        confirmed = next(event for event in events if event["action"] == "schedule_confirm")
        actor = json.loads(self.events("schedule_confirm")[0].payload)["actor"]
        self.assertIn(actor["request_id"], confirmed["summary"])
        self.assertIn("POST /payments/schedule/confirm", confirmed["summary"])
        self.assertIn("payments.schedule_confirm", confirmed["summary"])
        legacy = DocumentAuditLog(action="schedule_unmark", payload=json.dumps({
            "actor": {"session_id": "legacy-session"},
            "before": {"print_status": "programmed"}, "after": {"print_status": "not_printed"},
        }))
        self.assertIn("legacy-session", document_service._build_audit_view(legacy)["summary"])


if __name__ == "__main__":
    unittest.main()
