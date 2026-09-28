"""Prove isolate: parser reale, SQLite temporaneo, nessuna configurazione operativa."""
import copy
import json
import tempfile
import unittest
import os
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from flask import Flask
from sqlalchemy import Integer
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Document, DocumentAuditLog, ImportLog
from app.services import import_recovery_service as recovery
from app.services import import_service
from app.repositories.document_repo import DocumentRepository


def invoice(numbers=("A/1",), recipient="99999999991", amount="122.00"):
    header = f'''<FatturaElettronicaHeader>
    <DatiTrasmissione><IdTrasmittente><IdPaese>IT</IdPaese><IdCodice>99999999990</IdCodice></IdTrasmittente>
    <ProgressivoInvio>1</ProgressivoInvio><FormatoTrasmissione>FPR12</FormatoTrasmissione><CodiceDestinatario>0000000</CodiceDestinatario></DatiTrasmissione>
    <CedentePrestatore><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>99999999990</IdCodice></IdFiscaleIVA>
    <Anagrafica><Denominazione>Fornitore prova</Denominazione></Anagrafica><RegimeFiscale>RF01</RegimeFiscale></DatiAnagrafici>
    <Sede><Indirizzo>Via prova</Indirizzo><CAP>00100</CAP><Comune>Roma</Comune><Nazione>IT</Nazione></Sede></CedentePrestatore>
    <CessionarioCommittente><DatiAnagrafici><IdFiscaleIVA><IdPaese>IT</IdPaese><IdCodice>{recipient}</IdCodice></IdFiscaleIVA>
    <Anagrafica><Denominazione>Cliente prova</Denominazione></Anagrafica></DatiAnagrafici>
    <Sede><Indirizzo>Via prova</Indirizzo><CAP>00100</CAP><Comune>Roma</Comune><Nazione>IT</Nazione></Sede></CessionarioCommittente></FatturaElettronicaHeader>'''
    bodies = ''.join(f'''<FatturaElettronicaBody><DatiGenerali><DatiGeneraliDocumento>
    <TipoDocumento>TD01</TipoDocumento><Divisa>EUR</Divisa><Data>2026-09-26</Data><Numero>{number}</Numero><ImportoTotaleDocumento>{amount}</ImportoTotaleDocumento>
    </DatiGeneraliDocumento></DatiGenerali><DatiBeniServizi><DettaglioLinee><NumeroLinea>1</NumeroLinea><Descrizione>Prova</Descrizione>
    <Quantita>1.00</Quantita><PrezzoUnitario>100.00</PrezzoUnitario><PrezzoTotale>100.00</PrezzoTotale><AliquotaIVA>22.00</AliquotaIVA></DettaglioLinee>
    <DatiRiepilogo><AliquotaIVA>22.00</AliquotaIVA><ImponibileImporto>100.00</ImponibileImporto><Imposta>22.00</Imposta></DatiRiepilogo></DatiBeniServizi>
    <DatiPagamento><CondizioniPagamento>TP02</CondizioniPagamento><DettaglioPagamento><ModalitaPagamento>MP05</ModalitaPagamento>
    <DataScadenzaPagamento>2026-10-31</DataScadenzaPagamento><ImportoPagamento>{amount}</ImportoPagamento></DettaglioPagamento></DatiPagamento></FatturaElettronicaBody>'''
    for number in numbers)
    return f'<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" versione="FPR12">{header}{bodies}</p:FatturaElettronica>'.encode()


class ImportTestCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.storage = self.root / "deposito"
        self.database_uri = getattr(self, "database_uri", "sqlite:///" + str(self.root / "test.db"))
        from app import create_app
        with patch("app.extensions._init_logging"):
            self.app = create_app(SimpleNamespace(
                TESTING=True, SQLALCHEMY_DATABASE_URI=self.database_uri, SECRET_KEY="isolated-test",
            ))
        self.stack.enter_context(self.app.app_context())
        self.stack.callback(db.engine.dispose)
        self.stack.callback(db.session.remove)
        if self.database_uri.startswith("sqlite"):
            self.stack.enter_context(patch.object(DocumentAuditLog.__table__.c.id, "type", Integer()))
        if self.database_uri.startswith("mysql"):
            from sqlalchemy import inspect
            self.assertEqual(inspect(db.engine).get_table_names(), [], "Usare uno schema di test VUOTO")
            def clean_test_schema():
                db.session.remove()
                db.drop_all()
            self.stack.callback(clean_test_schema)
        db.create_all()
        self.stack.enter_context(patch.object(import_service.settings_service, "get_xml_storage_path", return_value=str(self.storage)))
        self.stack.enter_context(patch.object(import_service.settings_service, "get_setting", return_value="1"))

    def run_file(self, content=None, name="originale.xml"):
        path = self.root / name
        path.write_bytes(content if content is not None else invoice())
        result = recovery.import_file(path, "test-batch", "upload", self.storage)
        db.session.remove()
        return result

    def assert_registered(self, result, count=1):
        self.assertEqual(result["state"], "committed", result)
        self.assertEqual(Document.query.count(), count)
        for doc in Document.query.all():
            self.assertTrue((self.storage / doc.file_path).is_file())
            self.assertEqual(doc.invoice_lines.count(), 1)
            self.assertEqual(doc.payments.count(), 1)

    def worker(self, mode, result="worker.json", wait=True):
        env = dict(os.environ, IMPORT_WORKER_DATABASE_URL=self.database_uri)
        command = [sys.executable, str(Path(__file__).with_name("import_worker.py")), str(self.root), mode, result]
        if not wait:
            return subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return subprocess.run(command, env=env, capture_output=True, timeout=40)



class ImportLifecycleTests(ImportTestCase):
    def test_deleted_document_reuses_deposit_file(self):
        from app.services.document_service import DocumentService
        self.assert_registered(self.run_file())
        doc = Document.query.one()
        original_path = doc.file_path
        self.assertEqual(len(Path(original_path).parts), 2)
        self.assertTrue(DocumentService.delete_document(doc.id, reason="Prova reimportazione"))
        result = self.run_file(name="rinominato.xml")
        self.assert_registered(result)
        self.assertEqual(Document.query.one().file_path, original_path)
        self.assertEqual(len(list((self.storage / "2026").rglob("*.xml"))), 1)
        self.assertTrue(any("Riutilizzato" in warning for warning in result["warnings"]))

    def test_reuses_orphan_in_legacy_attempt_folder(self):
        existing = self.storage / "2026" / "vecchio-tentativo" / "storico.xml"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(invoice())
        self.assert_registered(self.run_file())
        self.assertEqual(self.storage / Document.query.one().file_path, existing)
        self.assertEqual(len(list((self.storage / "2026").rglob("*.xml"))), 1)

    def test_same_readable_name_different_content_is_not_overwritten(self):
        with patch.object(import_service, "_import_filename", return_value="fattura.xml"):
            self.assert_registered(self.run_file())
            original = self.storage / Document.query.one().file_path
            self.assert_registered(self.run_file(invoice(("A/2",))), 2)
        self.assertEqual(original.read_bytes(), invoice())
        paths = [doc.file_path for doc in Document.query.all()]
        self.assertEqual(len(set(paths)), 2)
        self.assertTrue(all(len(Path(path).parts) == 2 for path in paths))

    def test_import_without_file_digest(self):
        with patch.object(recovery.hashlib, "file_digest", create=True):
            del recovery.hashlib.file_digest
            for content in (b"", b"abc", b"x" * (1024 * 1024 + 17)):
                path = self.root / "hash.bin"
                path.write_bytes(content)
                self.assertEqual(recovery.sha256(path), recovery.hashlib.sha256(content).hexdigest())
            self.assert_registered(self.run_file())
            self.assertEqual(self.run_file()["state"], "duplicate")

    def test_failure_records_code_location_without_exception_data(self):
        with patch.object(recovery, "sha256", side_effect=AttributeError("private invoice data")):
            result = self.run_file()
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["error_code"], "AttributeError")
        self.assertTrue(any(frame["function"] == "import_file" for frame in result["error_trace"]))
        self.assertNotIn("private invoice data", json.dumps(result))
        self.assertEqual(Document.query.count(), 0)

    def test_crash_before_manifest_is_found_in_database(self):
        with patch.object(recovery, "_checkpoint", side_effect=SystemExit), self.assertRaises(SystemExit):
            self.run_file()
        db.session.remove()
        self.assertEqual(ImportLog.query.filter_by(status="warning").count(), 1)
        db.session.remove()
        results = recovery.recover_imports()
        self.assertEqual(results[0]["state"], "failed", results)
        self.assert_registered(self.run_file())

    def test_changed_stored_xml_is_a_conflict(self):
        result = self.run_file()
        path = self.storage / Document.query.one().file_path
        path.write_bytes(invoice(amount="999.00"))
        result = self.run_file()
        self.assertEqual(result["state"], "conflict", result)
        self.assertEqual(Document.query.count(), 1)

    def test_mixed_existing_and_new_body_is_not_blocked_by_file_hash(self):
        self.assert_registered(self.run_file())
        result = self.run_file(invoice(("A/1", "A/2")))
        self.assert_registered(result, 2)
        self.assertEqual([d["status"] for d in result["details"]], ["skipped", "success"])

    def test_unavailable_storage_after_commit_is_not_reported_success(self):
        with patch.object(recovery, "_finish_committed", side_effect=OSError("offline")):
            result = self.run_file()
        self.assertEqual(result["state"], "reconcile", result)
        self.assertEqual(Document.query.count(), 1)
        self.assertEqual(recovery.summarize([result], "test")["imported"], 0)
        self.assert_registered(recovery.reconcile_attempt(result["attempt_id"]))

    def test_real_process_crash_and_restart(self):
        (self.root / "originale.xml").write_bytes(invoice())
        result = self.worker("published")
        self.assertEqual(result.returncode, 73, result.stderr.decode(errors="replace"))
        result = self.worker("recover")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        recovered = json.loads((self.root / "worker.json").read_text(encoding="utf-8"))
        self.assertEqual(recovered[0]["state"], "failed")
        self.assert_registered(self.run_file())

    def test_real_process_dies_after_commit(self):
        (self.root / "originale.xml").write_bytes(invoice())
        result = self.worker("committed")
        self.assertEqual(result.returncode, 74, result.stderr.decode(errors="replace"))
        result = self.worker("recover")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        recovered = json.loads((self.root / "worker.json").read_text(encoding="utf-8"))
        self.assert_registered(recovered[0])
        self.assertEqual(self.run_file()["state"], "duplicate")

    def test_delete_shared_xml_preserves_other_body_and_audit(self):
        from app.services.document_service import DocumentService
        result = self.run_file(invoice(("A/1", "A/2")))
        ids = [d["invoice_id"] for d in result["details"]]
        self.assertTrue(DocumentService.delete_document(ids[0], reason="Prova annullamento"))
        db.session.remove()
        other = db.session.get(Document, ids[1])
        self.assertTrue((self.storage / other.file_path).is_file())
        audit = json.loads(DocumentAuditLog.query.one().payload)
        self.assertEqual(audit["reason"], "Prova annullamento")
        self.assertEqual(audit["before"]["document_number"], "A/1")
        self.assertEqual(audit["before"]["import_identity"]["identity"][2], "TD01")

    def test_missing_final_file_is_repaired_without_inserting(self):
        result = self.run_file()
        doc = Document.query.one()
        (self.storage / doc.file_path).unlink()
        db.session.remove()
        recovered = recovery.reconcile_attempt(result["attempt_id"])
        self.assert_registered(recovered)

    def test_multi_body_is_atomic_and_repeat_returns_all_ids(self):
        content = invoice(("A/1", "A/2"))
        first = self.run_file(content)
        self.assert_registered(first, 2)
        second = self.run_file(content, "rinominato.xml")
        self.assertEqual(second["state"], "duplicate", second)
        self.assertEqual([d["invoice_id"] for d in first["details"]], [d["invoice_id"] for d in second["details"]])
        self.assertEqual(Document.query.count(), 2)

    def test_failure_on_second_body_rolls_back_everything(self):
        original = DocumentRepository._create_line
        calls = []
        def fail(repo, *args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("injected")
            return original(repo, *args, **kwargs)
        with patch.object(DocumentRepository, "_create_line", fail):
            result = self.run_file(invoice(("A/1", "A/2")))
        self.assertEqual(result["state"], "failed", result)
        self.assertEqual(Document.query.count(), 0)
        self.assertEqual(ImportLog.query.filter_by(status="success").count(), 0)
        self.assertEqual(ImportLog.query.filter_by(status="error").count(), 1)
        self.assert_registered(self.run_file(invoice(("A/1", "A/2"))), 2)

    def test_commit_ack_lost_reconciles_without_duplicate(self):
        original = Session.commit
        calls = []
        def lost(session):
            calls.append(1)
            original(session)
            if len(calls) == 2:
                raise ConnectionError("ACK lost")
        with patch.object(Session, "commit", lost):
            result = self.run_file()
        self.assert_registered(result)
        self.assertEqual(self.run_file()["state"], "duplicate")

    def test_commit_failure_before_server_commit_is_retryable(self):
        original = Session.commit
        calls = []
        def failed(session):
            calls.append(1)
            if len(calls) == 2:
                raise ConnectionError("before commit")
            original(session)
        with patch.object(Session, "commit", failed):
            result = self.run_file()
        self.assertEqual(result["state"], "failed", result)
        self.assertEqual(Document.query.count(), 0)
        events = [json.loads(line) for path in recovery.diagnostic_root().glob("*.jsonl")
                  for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertFalse(any(event["state"] == "committed" for event in events))
        self.assertFalse(any(d.get("status") == "success" for event in events for d in event["details"]))
        self.assert_registered(self.run_file())

    def test_crash_after_publish_recovered_by_new_context(self):
        original = recovery._checkpoint
        def crash(payload, phase):
            original(payload, phase)
            if phase == "published":
                raise SystemExit("process terminated")
        with patch.object(recovery, "_checkpoint", crash), self.assertRaises(SystemExit):
            self.run_file()
        db.session.remove()
        results = recovery.recover_imports()
        self.assertEqual(results[0]["state"], "failed", results)
        self.assertEqual(Document.query.count(), 0)
        self.assert_registered(self.run_file())

    def test_same_name_other_invoice_and_equivalent_xml(self):
        self.assert_registered(self.run_file())
        self.assert_registered(self.run_file(invoice(("A1",))), 2)
        equivalent = invoice().replace(b">\n    <", b"><")
        result = self.run_file(equivalent, "equivalente.xml")
        self.assertEqual(result["state"], "duplicate", result)
        self.assertEqual(result["details"][0]["duplicate_reason"], "document_identity")
        self.assertEqual(self.run_file(invoice(amount="123.00"))["state"], "conflict")

    def test_recipient_and_document_type_are_part_of_identity(self):
        self.assert_registered(self.run_file())
        self.assert_registered(self.run_file(invoice(recipient="99999999992")), 2)
        self.assert_registered(self.run_file(invoice().replace(b"TD01", b"TD24")), 3)

    def test_diagnostic_or_archive_failure_does_not_reverse_success(self):
        with patch.object(recovery, "RotatingFileHandler", side_effect=PermissionError), patch.object(recovery, "_archive", side_effect=OSError):
            result = self.run_file()
        self.assert_registered(result)
        self.assertGreaterEqual(len(result["warnings"]), 2)
        self.assertEqual(self.run_file()["state"], "duplicate")

    def test_storage_unavailable_has_durable_db_failure(self):
        with patch.object(recovery, "save_json", side_effect=OSError("unavailable")):
            result = self.run_file()
        self.assertEqual(result["state"], "failed")
        self.assertEqual(Document.query.count(), 0)
        self.assertEqual(ImportLog.query.filter_by(status="error").count(), 1)

    def test_parse_error_creates_no_placeholder(self):
        result = self.run_file(b"<broken>")
        self.assertEqual(result["state"], "failed")
        self.assertEqual(Document.query.count(), 0)
        self.assert_registered(self.run_file())


if __name__ == "__main__":
    unittest.main()
