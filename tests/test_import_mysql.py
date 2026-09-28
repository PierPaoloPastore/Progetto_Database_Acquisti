"""Opt-in: schema MySQL vuoto, dedicato, con nome test_import_*. Nessun fallback."""
import json
import os
import unittest
from sqlalchemy.engine import make_url
import test_import_lifecycle as lifecycle


@unittest.skipUnless(os.environ.get("IMPORT_TEST_MYSQL_URL"), "MySQL di test non configurato")
class ImportMySQLTests(lifecycle.ImportLifecycleTests):
    def setUp(self):
        self.database_uri = os.environ["IMPORT_TEST_MYSQL_URL"]
        url = make_url(self.database_uri)
        if url.get_backend_name() != "mysql" or not (url.database or "").startswith("test_import_"):
            raise ValueError("Richiesto schema MySQL dedicato test_import_*; vietato il DB operativo")
        super().setUp()

    def test_two_independent_processes_import_once(self):
        (self.root / "originale.xml").write_bytes(lifecycle.invoice(("A/1", "A/2")))
        first = self.worker("normal", "first.json", wait=False)
        second = self.worker("normal", "second.json", wait=False)
        try:
            _, error1 = first.communicate(timeout=40)
            _, error2 = second.communicate(timeout=40)
            self.assertEqual(first.returncode, 0, error1.decode(errors="replace"))
            self.assertEqual(second.returncode, 0, error2.decode(errors="replace"))
        finally:
            for process in (first, second):
                if process.poll() is None:
                    process.kill()
                    process.wait()
        states = [json.loads((self.root / name).read_text(encoding="utf-8"))["state"]
                  for name in ("first.json", "second.json")]
        self.assertCountEqual(states, ["committed", "duplicate"])
        self.assertEqual(lifecycle.Document.query.count(), 2)
