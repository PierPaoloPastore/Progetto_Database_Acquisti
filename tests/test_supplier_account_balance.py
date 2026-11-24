"""Riepiloghi e storico su SQLite in memoria, senza dati operativi."""
import re
import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import Document, LegalEntity, Payment, Supplier
from app.services.unit_of_work import UnitOfWork
from app.services.legal_entity_service import get_legal_entity_detail
from app.services.supplier_service import get_supplier_detail


class SupplierAccountBalanceTests(unittest.TestCase):
    def setUp(self):
        with patch("app.extensions._init_logging"):
            self.app = create_app(SimpleNamespace(
                TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite://",
                SECRET_KEY="isolated-test",
            ))
        context = self.app.app_context()
        context.push()
        self.addCleanup(context.pop)
        self.addCleanup(lambda: db.engine.dispose())
        self.addCleanup(db.session.remove)
        db.create_all()
        db.session.add_all([
            Supplier(id=1, name="Fornitore prova"),
            Supplier(id=2, name="Altro fornitore"),
            LegalEntity(id=1, name="Intestazione prova", vat_number="00000000001"),
            LegalEntity(id=2, name="Altra intestazione", vat_number="00000000002"),
        ])
        self.repo = UnitOfWork().documents

    def add_document(self, amount, *, supplier_id=1, legal_entity_id=1,
                     document_type="invoice", paid=()):
        doc = Document(document_type=document_type, supplier_id=supplier_id,
                       legal_entity_id=legal_entity_id, total_gross_amount=amount)
        db.session.add(doc)
        db.session.flush()
        for value in paid:
            db.session.add(Payment(document_id=doc.id, paid_amount=value))
        db.session.commit()
        return doc

    def test_multiple_payments_do_not_duplicate_equal_document_amounts(self):
        self.add_document(Decimal("105002"), paid=(Decimal("105002"),))
        self.add_document(Decimal("105002"), paid=(Decimal("0"), None))
        self.add_document(Decimal("2602"), paid=(Decimal("2602"),))
        self.assertEqual(self.repo.get_account_balance(1), {
            "expected_total": Decimal("212606"),
            "paid_total": Decimal("107604"),
            "residual": Decimal("105002"),
            "document_count": 3,
        })
        response = self.app.test_client().get("/suppliers/1")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        format_amount = self.app.jinja_env.filters["format_amount"]
        for amount in ("212606", "107604", "105002"):
            self.assertIn(format_amount(Decimal(amount)), html)
        self.assertNotIn(format_amount(Decimal("317608")), html)

    def test_filters_isolate_supplier_and_legal_entity(self):
        self.add_document(Decimal("100"), paid=(Decimal("10"), Decimal("20")))
        self.add_document(Decimal("200"), legal_entity_id=2, paid=(Decimal("50"),))
        self.add_document(Decimal("900"), supplier_id=2, paid=(Decimal("900"),))
        self.assertEqual(self.repo.get_account_balance(1, 1), {
            "expected_total": Decimal("100"), "paid_total": Decimal("30"),
            "residual": Decimal("70"), "document_count": 1,
        })
        snapshot = self.repo.get_account_balance(1)
        self.assertEqual(snapshot["expected_total"], Decimal("300"))
        self.assertEqual(snapshot["paid_total"], Decimal("80"))
        self.assertEqual(snapshot["document_count"], 2)

    def test_document_without_payments_and_empty_supplier(self):
        self.add_document(Decimal("100"))
        self.assertEqual(self.repo.get_account_balance(1), {
            "expected_total": Decimal("100"), "paid_total": 0,
            "residual": Decimal("100"), "document_count": 1,
        })
        self.assertEqual(self.repo.get_account_balance(2), {
            "expected_total": 0, "paid_total": 0, "residual": 0,
            "document_count": 0,
        })
        self.assertEqual(get_legal_entity_detail(1)["account_snapshot"], {
            "expected_total": Decimal("100"), "paid_total": 0,
            "residual": Decimal("100"), "document_count": 1,
        })
        empty = {"expected_total": 0, "paid_total": 0, "residual": 0,
                 "document_count": 0}
        self.assertEqual(get_legal_entity_detail(2)["account_snapshot"], empty)
        detail = get_supplier_detail(2)
        self.assertEqual(detail["documents"], [])
        self.assertEqual(detail["account_snapshot"], empty)

    def test_legal_entity_counts_each_document_once(self):
        self.add_document(Decimal("105002"), paid=(Decimal("105002"),))
        self.add_document(Decimal("105002"), paid=(Decimal("0"), None))
        self.add_document(Decimal("2602"), paid=(Decimal("2602"),))
        self.assertEqual(get_legal_entity_detail(1)["account_snapshot"], {
            "expected_total": Decimal("212606"),
            "paid_total": Decimal("107604"),
            "residual": Decimal("105002"),
            "document_count": 3,
        })
        response = self.app.test_client().get("/legal-entities/1")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        format_amount = self.app.jinja_env.filters["format_amount"]
        for amount in ("212606", "107604", "105002"):
            self.assertIn(format_amount(Decimal(amount)), html)
        self.assertNotIn(format_amount(Decimal("317608")), html)

    def test_legal_entity_filters_and_documents_without_supplier(self):
        self.add_document(Decimal("100"), paid=(Decimal("10"), Decimal("20")))
        self.add_document(Decimal("200"), legal_entity_id=2, paid=(Decimal("50"),))
        self.add_document(Decimal("900"), supplier_id=2,
                          paid=(Decimal("400"), Decimal("500")))
        self.add_document(Decimal("50"), supplier_id=None, document_type="f24")
        self.assertEqual(get_legal_entity_detail(1)["account_snapshot"], {
            "expected_total": Decimal("1050"), "paid_total": Decimal("930"),
            "residual": Decimal("120"), "document_count": 3,
        })
        filtered = get_legal_entity_detail(1, supplier_id=1)
        self.assertEqual(filtered["account_snapshot"], {
            "expected_total": Decimal("100"), "paid_total": Decimal("30"),
            "residual": Decimal("70"), "document_count": 1,
        })
        self.assertEqual(len(filtered["documents"]), 1)
        response = self.app.test_client().get("/legal-entities/1?supplier_id=1")
        self.assertEqual(response.status_code, 200)

    def test_supplier_history_includes_every_document_type(self):
        types = ("invoice", "credit_note", "f24", "insurance", "mav",
                 "cbill", "receipt", "rent", "tax", "other")
        expected_ids = []
        for doc_type in types:
            amount = Decimal("-20") if doc_type == "credit_note" else Decimal("100")
            doc = self.add_document(amount, document_type=doc_type)
            doc.document_number = f"PROVA-{doc_type}"
            expected_ids.append(doc.id)
        db.session.commit()
        detail = get_supplier_detail(1)
        self.assertEqual([doc.id for doc in detail["documents"]], expected_ids[::-1])
        self.assertEqual(detail["account_snapshot"]["document_count"], len(types))
        self.assertEqual(sum(doc.total_gross_amount for doc in detail["documents"]),
                         detail["account_snapshot"]["expected_total"])
        self.assertEqual(detail["account_snapshot"]["expected_total"], Decimal("880"))
        response = self.app.test_client().get("/suppliers/1")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertEqual([int(value) for value in re.findall(r'href="/documents/(\d+)"', html)],
                         expected_ids[::-1])
        self.assertIn("Storico Documenti (10)", html)
        for doc_type in types:
            self.assertIn(f"PROVA-{doc_type}", html)

    def test_supplier_history_respects_entity_filter_and_date_order(self):
        invoice = self.add_document(Decimal("100"))
        invoice.document_date = date(2026, 11, 1)
        credit = self.add_document(Decimal("-20"), document_type="credit_note")
        credit.document_date = date(2026, 11, 2)
        manual = self.add_document(Decimal("50"), document_type="f24")
        manual.document_date = credit.document_date
        self.add_document(Decimal("60"), legal_entity_id=2, document_type="other")
        self.add_document(Decimal("900"), supplier_id=2)
        detail = get_supplier_detail(1, legal_entity_id=1)
        self.assertEqual([doc.id for doc in detail["documents"]],
                         [manual.id, credit.id, invoice.id])
        self.assertEqual(detail["account_snapshot"]["document_count"], 3)
        self.assertEqual(detail["account_snapshot"]["expected_total"], Decimal("130"))
        self.assertEqual({row["id"]: row["invoice_count"]
                          for row in detail["available_legal_entities"]}, {1: 3, 2: 1})
        response = self.app.test_client().get("/suppliers/1?legal_entity_id=1")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertEqual([int(value) for value in re.findall(r'href="/documents/(\d+)"', html)],
                         [manual.id, credit.id, invoice.id])
        self.assertIn("Storico Documenti (3)", html)
