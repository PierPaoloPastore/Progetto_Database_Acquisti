-- PRIMO GIRO: solo lettura. Eseguire sul DB utilizzato dagli operatori.
-- Nessun filtro temporale sui log: Marcantuono presenta copie di luglio.
-- Conservare separati i risultati Q1-Q5, anche se vuoti.

-- Q1: istanza e configurazione effettiva delle tabelle interessate.
SELECT DATABASE() AS db_corrente, @@hostname AS server_mysql, @@port AS porta,
       @@session.time_zone AS fuso_sessione, @@system_time_zone AS fuso_sistema,
       NOW() AS ora_server, UTC_TIMESTAMP() AS ora_utc;
SELECT TABLE_NAME, ENGINE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('documents', 'import_logs', 'document_audit_logs');

-- Q2: documenti attualmente presenti, anche con numero/nome alterato.
SELECT d.id, d.document_type, d.document_number, d.document_date,
       d.registration_date, d.due_date, d.total_gross_amount,
       d.supplier_id, s.name AS fornitore, s.vat_number AS piva_fornitore,
       d.legal_entity_id, le.name AS intestatario, le.vat_number AS piva_intestatario,
       d.is_paid, d.doc_status, d.print_status, d.physical_copy_status,
       d.file_name, d.file_path, d.import_source, d.imported_at, d.created_at, d.updated_at
FROM documents d
LEFT JOIN suppliers s ON s.id = d.supplier_id
LEFT JOIN legal_entities le ON le.id = d.legal_entity_id
WHERE d.id = 924
   OR d.file_name LIKE '%y3R4F%' OR d.file_path LIKE '%y3R4F%'
   OR d.file_name LIKE '%GeaXw%' OR d.file_path LIKE '%GeaXw%'
   OR d.document_number LIKE '%3521%' OR d.document_number LIKE '%2351%'
   OR (d.document_date = '2026-06-30' AND d.total_gross_amount IN (400.59, 1959.54)
       AND (s.vat_number IN ('02305140655', '02106670652')
            OR s.name LIKE '%MARCANTUONO%' OR s.name LIKE '%BUONINFANTE%'))
ORDER BY d.created_at, d.id;

-- Q3: log dei due contenuti (SHA-256 calcolati sui file reali).
-- document_id NULL su un vecchio success e' un indizio di perdita del collegamento;
-- non identifica da solo chi/quando/perche' ha eliminato o alterato il documento.
SELECT il.id, il.created_at AS data_log, il.status, il.document_id,
       d.id AS id_documento_esistente, d.document_number, d.created_at AS creazione_documento,
       il.file_name, il.file_hash, il.import_source, il.message
FROM import_logs il
LEFT JOIN documents d ON d.id = il.document_id
WHERE il.file_name LIKE '%y3R4F%' OR il.file_name LIKE '%GeaXw%'
   OR il.file_hash IN (
       '84dfd8eb6d2d80e5301f4464315c336d4b337b734297e621cb0c7eaa4c8b0f4d',
       '9e019ba2439866014fa08e1222eb1e623e57f0defbe9a6e893b848ad2295836c'
   )
   OR il.document_id = 924
   OR il.document_id IN (
       SELECT id FROM documents
       WHERE document_number LIKE '%3521%' OR document_number LIKE '%2351%'
   )
ORDER BY il.created_at, il.id;

-- Q4: modifiche/cancellazioni, anche se la FK document_id e' diventata NULL.
SELECT id, document_id, action, created_at, payload
FROM document_audit_logs
WHERE document_id = 924
   OR payload LIKE '%y3R4F%' OR payload LIKE '%GeaXw%'
   OR payload LIKE '%3521%' OR payload LIKE '%2351%'
ORDER BY created_at, id;

-- Q5: vincoli effettivi, per distinguere modello Python e DB operativo.
SELECT tc.TABLE_NAME, tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE,
       kcu.COLUMN_NAME, kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME,
       rc.DELETE_RULE
FROM information_schema.TABLE_CONSTRAINTS tc
LEFT JOIN information_schema.KEY_COLUMN_USAGE kcu
  ON kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
 AND kcu.TABLE_NAME = tc.TABLE_NAME AND kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
  ON rc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
 AND rc.TABLE_NAME = tc.TABLE_NAME AND rc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
WHERE tc.CONSTRAINT_SCHEMA = DATABASE()
  AND tc.TABLE_NAME IN ('documents', 'import_logs', 'document_audit_logs')
ORDER BY tc.TABLE_NAME, tc.CONSTRAINT_NAME, kcu.ORDINAL_POSITION;
