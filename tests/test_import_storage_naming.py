"""Naming dei nuovi import: file temporanei, nessun database reale."""
import logging
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services import import_service as service


class ImportStorageNamingTests(unittest.TestCase):
    def setUp(self):
        self.dto = SimpleNamespace(
            supplier=SimpleNamespace(name="Fornitore prova"),
            invoice_date=date(2026, 9, 26), registration_date=None,
            invoice_number="FT/123", file_name="originale.xml", file_hash=None,
            total_gross_amount=100, tipo_documento="TD01",
        )

    def test_storage_preserves_content_extensions_and_handles_edge_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(service.settings_service, "get_xml_storage_path", return_value=str(root / "deposito")):
                for extension in (".xml", ".xml.p7m", ".p7m"):
                    source = root / f"originale{extension}"
                    source.write_bytes(b"original content")
                    relative = service._store_import_file(source, 2026, [self.dto])
                    self.assertEqual(Path(relative).name, f"2026-09-26_Fornitore_prova_FT-123{extension}")
                    self.assertEqual((root / "deposito" / relative).read_bytes(), source.read_bytes())
                    second = service._store_import_file(source, 2026, [self.dto])
                    self.assertEqual(Path(second).name, f"2026-09-26_Fornitore_prova_FT-123_1{extension}")
                    multi = service._store_import_file(source, 2026, [self.dto, self.dto])
                    self.assertIn("_multi", multi)
                    fallback = service._store_import_file(source, 2026)
                    self.assertEqual(Path(fallback).name, source.name)

                self.dto.supplier.name = "../Fornitore: *?" + "a" * 300
                self.dto.invoice_number = "../" + "b" * 300
                safe = service._store_import_file(source, 2026, [self.dto])
                self.assertEqual(len(Path(safe).parts), 2)
                self.assertLess(len(Path(safe).name), 200)
                self.dto.invoice_date = None
                self.dto.supplier.name = None
                self.dto.invoice_number = None
                missing = service._store_import_file(source, 2026, [self.dto])
                self.assertEqual(Path(missing).name, "senza-data_fornitore_senza-numero.p7m")

    def test_import_links_new_path_preserves_original_and_skips_reimport(self):
        uow = MagicMock()
        uow.__enter__.return_value = uow
        uow.documents.find_existing_by_file_base.return_value = None
        uow.documents.find_fatturapa_duplicate.return_value = (None, None)
        uow.suppliers.get_or_create_from_dto.return_value = SimpleNamespace(id=1)
        document = SimpleNamespace(id=42, document_date=self.dto.invoice_date)
        uow.documents.create_from_fatturapa.return_value = (document, True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "originale.xml"
            source.write_bytes(b"original content")
            with (
                patch.object(service, "UnitOfWork", return_value=uow),
                patch.object(service.settings_service, "get_setting", return_value="1"),
                patch.object(service.settings_service, "get_xml_storage_path", return_value=str(root / "deposito")),
                patch.object(service, "find_document_by_file_hash", return_value=None),
                patch.object(service, "parse_invoice_xml", return_value=[self.dto]) as parse,
                patch.object(service, "_extract_header_data", return_value={}),
                patch.object(service, "create_import_log"),
                patch.object(service, "_write_import_report", return_value=None),
                patch.object(service, "log_structured_event"),
            ):
                result = service._run_import_paths_locked(
                    [source], "upload", root / "deposito", 1, logging.getLogger(__name__), False,
                )
                self.assertEqual(result["errors"], 0)
                self.assertEqual(result["imported"], 1)
                self.assertEqual(Path(document.file_path).name, "2026-09-26_Fornitore_prova_FT-123.xml")
                self.assertTrue((root / "deposito" / document.file_path).is_file())
                self.assertEqual(self.dto.file_name, "originale.xml")
                archived = root / "deposito/Archivio/XML/2026/originale.xml"
                self.assertEqual(archived.read_bytes(), b"original content")
                self.assertFalse(source.exists())

                uow.documents.find_existing_by_file_base.return_value = document
                result = service._run_import_paths_locked(
                    [archived], "upload", root / "deposito", 1, logging.getLogger(__name__), False,
                )
                self.assertEqual(result["skipped"], 1)
                parse.assert_called_once()
                uow.documents.create_from_fatturapa.assert_called_once()


if __name__ == "__main__":
    unittest.main()
