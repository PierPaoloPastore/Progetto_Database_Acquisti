-- Aggiunge "credit_note" ai CHECK constraint di documents.
-- Eseguire nel DB applicativo (usa DATABASE()).

SET @schema := DATABASE();

-- Drop chk_documents_type (nome reale variabile)
SELECT tc.CONSTRAINT_NAME
INTO @chk_documents_type
FROM information_schema.table_constraints AS tc
WHERE tc.CONSTRAINT_SCHEMA = @schema
  AND tc.TABLE_NAME = 'documents'
  AND tc.CONSTRAINT_TYPE = 'CHECK'
  AND tc.CONSTRAINT_NAME LIKE 'chk_documents_type%';

SET @sql := IF(
  @chk_documents_type IS NULL,
  'SELECT "chk_documents_type non trovato" AS info;',
  CONCAT('ALTER TABLE documents DROP CHECK `', @chk_documents_type, '`;')
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Drop chk_documents_invoice_type (nome reale variabile)
SELECT tc.CONSTRAINT_NAME
INTO @chk_documents_invoice_type
FROM information_schema.table_constraints AS tc
WHERE tc.CONSTRAINT_SCHEMA = @schema
  AND tc.TABLE_NAME = 'documents'
  AND tc.CONSTRAINT_TYPE = 'CHECK'
  AND tc.CONSTRAINT_NAME LIKE 'chk_documents_invoice_type%';

SET @sql := IF(
  @chk_documents_invoice_type IS NULL,
  'SELECT "chk_documents_invoice_type non trovato" AS info;',
  CONCAT('ALTER TABLE documents DROP CHECK `', @chk_documents_invoice_type, '`;')
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Aggiunge i nuovi vincoli con credit_note
ALTER TABLE documents
  ADD CONSTRAINT chk_documents_type
    CHECK (document_type IN (
      'invoice',
      'credit_note',
      'f24',
      'insurance',
      'mav',
      'cbill',
      'receipt',
      'rent',
      'tax',
      'other'
    ));

ALTER TABLE documents
  ADD CONSTRAINT chk_documents_invoice_type
    CHECK (
      (document_type IN ('invoice', 'credit_note') AND invoice_type IN ('immediate', 'deferred'))
      OR (document_type NOT IN ('invoice', 'credit_note') AND invoice_type IS NULL)
    );
