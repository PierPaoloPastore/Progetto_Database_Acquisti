"""Riproduzioni investigative del comportamento attuale, NON test di correttezza.

Solo SQLite in memoria e file temporanei. Nessuna app factory/config produzione.
Parser simulato con DTO; repository, transazioni e gestione file reali.
Un PASS conferma lo scenario descritto, anche quando espone un difetto.
Eseguire dalla root: python docs/diagnostics/reproduce_import_lifecycle.py -v
"""
import ast
import copy
import logging
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flask import Flask
from sqlalchemy import Integer
from app.services import import_service as service
from app.services.document_service import DocumentService
from app.extensions import db
from app.models import Document, DocumentAuditLog, ImportLog, LegalEntity
from app.parsers.fatturapa_parser import InvoiceDTO, SupplierDTO
from app.repositories.document_repo import DocumentRepository


class ImportLifecycleInvestigation(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.storage = self.root / 'deposito'
        app = Flask('isolated-import-investigation')
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        db.init_app(app)
        self.stack.enter_context(app.app_context())
        self.stack.callback(db.engine.dispose)
        self.stack.callback(db.session.remove)
        # SQLite auto-incrementa solo INTEGER PRIMARY KEY, MySQL anche BIGINT.
        self.stack.enter_context(patch.object(DocumentAuditLog.__table__.c.id, 'type', Integer()))
        db.create_all()
        db.session.add(LegalEntity(id=1, name='Cliente fittizio', vat_number='99999999991'))
        db.session.commit()
        self.stack.enter_context(patch.object(service.settings_service, 'get_xml_storage_path', return_value=str(self.storage)))
        self.stack.enter_context(patch.object(service.settings_service, 'get_setting', return_value='1'))
        self.stack.enter_context(patch.object(service, '_extract_header_data', return_value={}))
        self.stack.enter_context(patch.object(service, '_write_import_report', return_value=None))
        self.stack.enter_context(patch.object(service, 'log_structured_event'))
        self.logger = logging.getLogger('isolated-import-investigation')
        self.logger.handlers = [logging.NullHandler()]
        self.logger.propagate = False

    def source(self, name='originale.xml', content=b'<example/>'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def dto(self, path, number='FT/123'):
        return InvoiceDTO(
            supplier=SupplierDTO(name='Fornitore fittizio', vat_number='99999999990', fiscal_code='99999999990'),
            invoice_number=number, invoice_date=date(2026, 6, 30),
            total_gross_amount=Decimal('122.00'), file_name=path.name,
        )

    def run_import(self, path, dtos=None):
        with patch.object(service, 'parse_invoice_xml', return_value=copy.deepcopy(dtos or [self.dto(path)])):
            return service._run_import_paths_locked([path], 'upload', self.storage, 1, self.logger, False)

    def test_01_failed_commit_leaves_copy_then_retry_creates_suffix(self):
        path = self.source()
        with patch.object(service.UnitOfWork, 'commit', side_effect=RuntimeError('commit fallito simulato')):
            result = self.run_import(path)
        self.assertEqual(result['errors'], 1)
        self.assertEqual(Document.query.count(), 0)
        self.assertEqual(ImportLog.query.count(), 0)
        self.assertEqual(len(list((self.storage / '2026').glob('*.xml'))), 1)
        self.assertTrue(path.exists())
        self.assertFalse((self.storage / 'Archivio/XML/2026/originale.xml').exists())
        result = self.run_import(path)
        self.assertEqual(result['imported'], 1)
        self.assertEqual(Document.query.count(), 1)
        self.assertTrue(Document.query.one().file_path.endswith('_1.xml'))

    def test_02_postparse_duplicate_creates_copy_without_new_document(self):
        self.assertEqual(self.run_import(self.source())['imported'], 1)
        renamed = self.source('rinominato.xml', b'<example>different bytes, same invoice</example>')
        result = self.run_import(renamed)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['details'][0]['duplicate_reason'], 'document_identity')
        self.assertEqual(Document.query.count(), 1)
        self.assertEqual(len(list((self.storage / '2026').glob('*.xml'))), 2)
        self.assertTrue((self.storage / 'Archivio/XML/2026/rinominato.xml').exists())

    def test_03_identical_reupload_creates_no_extra_copy(self):
        self.run_import(self.source())
        result = self.run_import(self.source('renamed.xml'))
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['details'][0]['duplicate_reason'], 'file_hash')
        self.assertEqual(Document.query.count(), 1)
        self.assertEqual(len(list((self.storage / '2026').glob('*.xml'))), 1)

    def test_04_multiple_bodies_second_is_skipped_by_shared_hash(self):
        path = self.source()
        dtos = [self.dto(path, 'A/1'), self.dto(path, 'A/2')]
        result = self.run_import(path, dtos)
        self.assertEqual((result['imported'], result['skipped']), (1, 1))
        self.assertEqual(result['details'][1]['duplicate_reason'], 'file_hash')
        self.assertEqual([d.document_number for d in Document.query.all()], ['A/1'])
        result = self.run_import(self.source(), dtos)
        self.assertEqual(result['details'][0]['duplicate_reason'], 'file_name')
        self.assertEqual(Document.query.count(), 1)

    def test_05_same_filename_different_invoice_skipped_before_parse(self):
        self.run_import(self.source())
        path = self.source(content=b'<example>another invoice</example>')
        result = self.run_import(path, [self.dto(path, 'OTHER/999')])
        self.assertEqual(result['details'][0]['duplicate_reason'], 'file_name')
        self.assertEqual([d.document_number for d in Document.query.all()], ['FT/123'])

    def test_06_delete_then_reimport_keeps_archive_and_creates_archive_suffix(self):
        self.run_import(self.source())
        old = Document.query.one()
        db.session.add(Document(id=10000, document_type='invoice', document_number='sentinella'))
        db.session.commit()
        self.assertTrue(DocumentService.delete_document(old.id))
        self.assertIsNone(ImportLog.query.filter_by(status='success').one().document_id)
        self.assertEqual(DocumentAuditLog.query.one().action, 'delete')
        self.assertTrue((self.storage / 'Archivio/XML/2026/originale.xml').exists())
        result = self.run_import(self.source())
        self.assertEqual(result['imported'], 1)
        self.assertTrue((self.storage / 'Archivio/XML/2026/originale_1.xml').exists())

    def test_07_legacy_first_import_from_destination_creates_suffix(self):
        # Esegue la funzione di salvataggio effettiva del codice del 24 settembre.
        source = subprocess.check_output(
            ['git', 'show', '86b5197:app/services/import_service.py'], cwd=ROOT, text=True,
        )
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == '_store_import_file')
        namespace = dict(vars(service))
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<legacy-storage>', 'exec'), namespace)
        legacy = namespace['_store_import_file']
        path = self.source('deposito/2026/originale.xml')
        with patch.object(service, '_store_import_file', side_effect=lambda p, y, dtos=None: legacy(p, y)):
            result = self.run_import(path)
        self.assertEqual(result['imported'], 1)
        self.assertEqual(Path(Document.query.one().file_path).name, 'originale_1.xml')
        self.assertEqual(Document.query.count(), 1)

    def test_08_filename_like_treats_underscore_as_wildcard(self):
        db.session.add(Document(document_type='invoice', file_name='SMXABC.xml#body1'))
        db.session.commit()
        match = DocumentRepository(db.session).find_existing_by_file_base('SM_ABC.xml')
        self.assertIsNotNone(match)
        self.assertEqual(match.file_name, 'SMXABC.xml#body1')

    def test_09_parsing_placeholder_blocks_future_retry(self):
        path = self.source()
        with patch.object(service, 'parse_invoice_xml', side_effect=ValueError('parsing fallito simulato')):
            result = service._run_import_paths_locked([path], 'upload', self.storage, 1, self.logger, False)
        self.assertEqual(result['warnings'], 1)
        self.assertIsNone(Document.query.one().document_number)
        self.assertIsNone(Document.query.one().supplier_id)
        result = self.run_import(self.source())
        self.assertEqual(result['details'][0]['duplicate_reason'], 'file_name')
        self.assertIsNone(Document.query.one().document_number)

    def test_10_archive_failure_does_not_undo_committed_document(self):
        with patch.object(service, '_archive_original_file', side_effect=OSError('archivio non accessibile simulato')):
            result = self.run_import(self.source())
        self.assertEqual((result['imported'], result['errors']), (1, 1))
        # Simula la fine della richiesta Flask e la perdita del lavoro non committato.
        db.session.remove()
        self.assertEqual(Document.query.count(), 1)
        self.assertEqual(ImportLog.query.filter_by(status='success').count(), 1)
        self.assertEqual(ImportLog.query.filter_by(status='error').count(), 0)

    def test_11_standalone_error_log_is_not_committed(self):
        summary = {'errors': 0, 'details': []}
        service._log_error_p7m(self.logger, 'fallita.p7m', ValueError('simulato'), summary, 'upload')
        self.assertEqual(summary['errors'], 1)
        db.session.remove()
        self.assertEqual(ImportLog.query.count(), 0)


if __name__ == '__main__':
    unittest.main()
