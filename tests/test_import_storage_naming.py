"""Naming dei nuovi import: file temporanei, nessun database reale."""
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.services import import_service as service


class ImportStorageNamingTests(unittest.TestCase):
    def setUp(self):
        self.dto = SimpleNamespace(
            supplier=SimpleNamespace(name="Fornitore prova"),
            invoice_date=date(2026, 9, 26), registration_date=None,
            invoice_number="FT/123", file_name="originale.xml", file_hash=None,
            total_gross_amount=100, tipo_documento="TD01",
        )

    def test_readable_names_preserve_extensions_and_multi_suffix(self):
        for extension in (".xml", ".xml.p7m", ".p7m"):
            source = Path(f"originale{extension}")
            self.assertEqual(service._import_filename(source, [self.dto]),
                             f"2026-09-26_Fornitore_prova_FT-123{extension}")
            self.assertIn("_multi", service._import_filename(source, [self.dto, self.dto]))
            self.assertEqual(service._import_filename(source), source.name)
        self.dto.supplier.name = "../Fornitore: *?" + "a" * 300
        self.dto.invoice_number = "../" + "b" * 300
        safe = service._import_filename(source, [self.dto])
        self.assertEqual(len(Path(safe).parts), 1)
        self.assertLess(len(safe), 200)
        self.dto.invoice_date = None
        self.dto.supplier.name = None
        self.dto.invoice_number = None
        self.assertEqual(service._import_filename(source, [self.dto]), "senza-data_fornitore_senza-numero.p7m")


if __name__ == "__main__":
    unittest.main()
