"""Dovuto XML e regolamento su DB temporaneo, senza dati operativi."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from test_import_lifecycle import ImportTestCase, invoice
from app.extensions import db
from app.models import Document
from app.parsers import fatturapa_parser, fatturapa_parser_v2
from app.services import payment_service as payments
from app.services.cbi_export_service import generate_cbi_xml, CbiExportError
from app.services.unit_of_work import UnitOfWork


def xml_with_amounts(number, amounts):
    xml = invoice((number,)).decode()
    start = xml.index("<DatiPagamento>")
    end = xml.index("</DatiPagamento>", start) + len("</DatiPagamento>")
    details = "".join(
        "<DettaglioPagamento><ModalitaPagamento>MP05</ModalitaPagamento>"
        + (f"<ImportoPagamento>{amount}</ImportoPagamento>" if amount is not None else "")
        + "</DettaglioPagamento>" for amount in amounts
    )
    return (xml[:start] + ("<DatiPagamento><CondizioniPagamento>TP02</CondizioniPagamento>"
            + details + "</DatiPagamento>" if amounts else "") + xml[end:]).encode()


class OriginalDueTests(ImportTestCase):
    def test_parsers_and_persistence(self):
        cases = [("lower", ["100"], "100"), ("absent", [], "122"),
                 ("missing", [None], "122"), ("zero", ["0"], "0"),
                 ("rates", ["40", "60"], "100"), ("mixed", [None, "0"], "0")]
        for number, amounts, expected in cases:
            with self.subTest(number=number):
                xml = xml_with_amounts(number, amounts)
                path = self.root / f"{number}.xml"
                path.write_bytes(xml)
                for parser in (fatturapa_parser, fatturapa_parser_v2):
                    dto = parser.parse_invoice_xml(path)[0]
                    self.assertEqual(dto.total_gross_amount, Decimal(expected))
                result = self.run_file(xml, path.name)
                self.assertEqual(result["state"], "committed", result)
                doc = Document.query.filter_by(document_number=number).one()
                self.assertEqual(doc.total_gross_amount, Decimal(expected))
                self.assertEqual(doc.is_paid, expected == "0")
                payments.attach_payment_amounts([doc])
                self.assertEqual(doc.remaining_amount, float(expected))

    def test_partial_full_dashboard_and_export(self):
        self.assertEqual(self.run_file(xml_with_amounts("partial", ["40", "60"]))["state"], "committed")
        doc = Document.query.one()
        doc.due_date = date(2020, 1, 1)
        doc.supplier.iban = "IT60X0542811101000000123456"
        rows = doc.payments.order_by("id").all()
        rows[0].expected_amount = Decimal("999")  # Scadenza modificata dopo import.
        rows[0].paid_amount = Decimal("30")
        rows[0].status = "partial"
        with UnitOfWork() as uow:
            payments._update_document_paid_status(uow, doc)
        db.session.commit()
        self.assertFalse(doc.is_paid)
        payments.attach_payment_amounts([doc])
        self.assertEqual(doc.remaining_amount, 70)
        self.assertEqual(doc.payment_overview_status, "partial")
        account = SimpleNamespace(iban=doc.supplier.iban, name="Prova", legal_entity_id=doc.legal_entity_id)
        del doc.remaining_amount  # Anche il chiamante senza annotazione usa il calcolo condiviso.
        export = generate_cbi_xml(documents=[doc], debtor_account=account)
        self.assertEqual(export.control_sum, Decimal("70"))
        self.assertIn(b'>70.00</', export.xml_bytes)
        with patch("app.web.routes_main.render_template", side_effect=lambda template, **kw: kw):
            from app.web.routes_main import index
            self.assertEqual(index()["total_unpaid_amount"], 70)
            self.assertEqual(index()["overdue_count"], 1)
        rows[1].paid_amount = Decimal("70")
        rows[1].status = "paid"
        with UnitOfWork() as uow:
            payments._update_document_paid_status(uow, doc)
        db.session.commit()
        self.assertTrue(doc.is_paid)
        payments.attach_payment_amounts([doc])
        self.assertEqual(doc.remaining_amount, 0)
        self.assertEqual(doc.payment_overview_status, "paid")
        with self.assertRaises(CbiExportError):
            generate_cbi_xml(documents=[doc], debtor_account=account)
        with patch("app.web.routes_main.render_template", side_effect=lambda template, **kw: kw):
            self.assertEqual(index()["unpaid_count"], 0)
        self.assertEqual(doc.total_gross_amount, Decimal("100"))

    def test_credit_notes_and_allocations(self):
        xml = xml_with_amounts("credit", ["100"]).replace(b"TD01", b"TD04")
        self.assertEqual(self.run_file(xml)["state"], "committed")
        credit = Document.query.one()
        self.assertEqual(credit.total_gross_amount, Decimal("-122"))
        self.assertEqual(credit.payments.count(), 0)
        doc = Document(document_type="credit_note", total_gross_amount=Decimal("-122"))
        snapshot = payments._calculate_document_settlement_snapshot(
            document=doc, payment_rows=[], allocated_out=Decimal("22"))
        self.assertEqual(snapshot["remaining_amount"], Decimal("-100"))
        self.assertEqual(snapshot["overview_status"], "partial")
        snapshot = payments._calculate_document_settlement_snapshot(
            document=doc, payment_rows=[], allocated_out=Decimal("122"))
        self.assertEqual(snapshot["available_credit_amount"], 0)
        doc.document_type = "invoice"
        doc.total_gross_amount = Decimal("100")
        snapshot = payments._calculate_document_settlement_snapshot(
            document=doc, payment_rows=[("partial", Decimal("30"))], allocated_in=Decimal("70"))
        self.assertEqual(snapshot["remaining_amount"], 0)
        self.assertEqual(snapshot["overview_status"], "paid")

    def test_invalid_payment_amount_is_rejected(self):
        for amount in ("invalid", "NaN", "Infinity"):
            with self.subTest(amount=amount):
                result = self.run_file(xml_with_amounts(amount, [amount]))
                self.assertEqual(result["state"], "failed")
        self.assertEqual(Document.query.count(), 0)
