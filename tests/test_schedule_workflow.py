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

from app.extensions import db
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

    def test_cancel_does_not_program_and_cannot_be_confirmed_later(self):
        token = self.generate()
        self.assertEqual(self.client.post("/payments/schedule/cancel", data={"token": token}).status_code, 200)
        self.assertEqual(self.client.post("/payments/schedule/confirm", data={"token": token}).status_code, 409)
        self.assertEqual(self.flags(), ["not_printed"] * 3)
        self.assertEqual(len(self.events("schedule_cancel")), 1)

    def test_replay_does_not_duplicate_audit_or_reprogram_after_unmark(self):
        token = self.generate()
        self.client.post("/payments/schedule/confirm", data={"token": token})
        self.client.post("/payments/schedule/unprogram", data={"document_ids": "1,2"})
        response = self.client.post("/payments/schedule/confirm", data={"token": token})
        self.assertTrue(response.json["already_done"])
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
        with self.assertLogs(self.app.logger, level="ERROR"):
            response = self.client.post("/payments/schedule/print", data={"document_ids": "1"},
                                        headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(self.events("schedule_failed")[0].payload)["reason"], "pdf_render_error")
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


if __name__ == "__main__":
    unittest.main()
