"""Report import: controlli senza connessioni al database reale."""
import csv
import logging
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import import_service as service
from app.repositories.document_repo import DocumentRepository


class ImportReportTests(unittest.TestCase):
    def setUp(self):
        self.document = SimpleNamespace(
            id=42, file_name="originale.xml", document_number="FT/123",
            document_date=date(2026, 9, 23), supplier=SimpleNamespace(name="Fornitore prova"),
        )
        self.dto = SimpleNamespace(
            file_name="rinominato.xml", file_hash="abc", invoice_number="FT-123",
            invoice_date=date(2026, 9, 23), supplier=self.document.supplier,
            total_gross_amount=100, tipo_documento="TD01",
        )
        self.logger = logging.getLogger(__name__)

    def test_repository_reports_actual_match_and_preserves_old_api(self):
        repo = DocumentRepository(MagicMock())
        for criterion in ("file_name", "file_hash", "document_identity"):
            with self.subTest(criterion=criterion):
                repo.get_by_file_name = MagicMock(return_value=self.document if criterion == "file_name" else None)
                repo.get_by_file_hash = MagicMock(return_value=self.document if criterion == "file_hash" else None)
                repo.find_existing_by_supplier_number_date = MagicMock(return_value=self.document)
                args = dict(invoice_dto=self.dto, supplier_id=1, legal_entity_id=1)
                self.assertEqual(repo.find_fatturapa_duplicate(**args), (self.document, criterion))
                self.assertIs(repo.find_existing_fatturapa_document(**args), self.document)
                if criterion == "file_name":
                    repo.get_by_file_hash.assert_not_called()
        repo.get_by_file_name.return_value = None
        repo.get_by_file_hash.return_value = None
        self.dto.invoice_number = None
        self.assertEqual(repo.find_fatturapa_duplicate(**args), (None, None))

    def test_skip_report_distinguishes_names_and_metadata_source(self):
        for incoming, criterion, expected in (
            ("originale.xml", "file_name", "si"),
            ("originale.xml#body2", "file_name", "si"),
            ("rinominato.xml", "file_hash", "no"),
            ("rinominato.xml", "document_identity", "no"),
        ):
            with self.subTest(criterion=criterion, incoming=incoming):
                summary = {"skipped": 0, "details": []}
                dto = self.dto if criterion == "document_identity" else None
                service._log_skip(
                    self.logger, incoming, 42, summary,
                    context=service._report_context(dto, self.document, criterion),
                )
                row = summary["details"][0]
                self.assertEqual(row["same_file_name"], expected)
                self.assertEqual(row["existing_document_number"], "FT/123")
                self.assertEqual(row["document_number"], "FT-123" if dto else "FT/123")
                self.assertEqual(row["document_data_source"], "file importato" if dto else "documento esistente")
                self.assertIn(service._DUPLICATE_REASONS[criterion], row["message"])

    def test_postcheck_writes_valid_db_status_and_csv_metadata(self):
        uow = MagicMock()
        uow.__enter__.return_value = uow
        uow.documents.find_existing_by_file_base.return_value = None
        uow.documents.find_fatturapa_duplicate.return_value = (self.document, "document_identity")
        uow.suppliers.get_or_create_from_dto.return_value = SimpleNamespace(id=1)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            xml = root / self.dto.file_name
            xml.write_text("<example/>", encoding="utf-8")
            with (
                patch.object(service, "UnitOfWork", return_value=uow),
                patch.object(service.settings_service, "get_setting", return_value="1"),
                patch.object(service, "find_document_by_file_hash", return_value=None),
                patch.object(service, "parse_invoice_xml", return_value=[self.dto]),
                patch.object(service, "_extract_header_data", return_value={}),
                patch.object(service, "_store_import_file", return_value="2026/test.xml"),
                patch.object(service, "_archive_original_file"),
                patch.object(service, "create_import_log") as create_log,
                patch.object(service, "__file__", str(root / "app/services/import_service.py")),
            ):
                summary = service._run_import_paths_locked(
                    [xml], "upload", root, 1, self.logger, False,
                )
            self.assertEqual(summary["errors"], 0)
            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(create_log.call_args.kwargs["status"], "duplicate")
            uow.commit.assert_called_once()
            with (root / summary["report_path"]).open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["document_number"], "FT-123")
            self.assertEqual(row["supplier_name"], "Fornitore prova")
            self.assertEqual(row["same_file_name"], "no")
            self.assertEqual(row["duplicate_reason"], "document_identity")
            self.assertEqual(row["existing_file_name"], "originale.xml")


if __name__ == "__main__":
    unittest.main()
