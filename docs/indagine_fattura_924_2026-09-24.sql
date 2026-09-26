-- Diagnostica MySQL, solo SELECT. Eseguire sullo schema operativo corretto.
-- Le query non correggono dati e non avviano importazioni.

-- 1. Identita dell'istanza e fuso orario.
SELECT DATABASE() AS schema_corrente, @@hostname AS host_mysql,
       @@port AS porta_mysql, @@session.time_zone AS fuso_sessione,
       @@system_time_zone AS fuso_sistema, NOW() AS ora_server,
       UTC_TIMESTAMP() AS ora_utc;

-- 2. Documento e candidati simili, con colonne nominate e anagrafiche.
SELECT d.id, d.document_type, d.document_number, d.document_date,
       d.due_date, d.registration_date, d.supplier_id, s.name AS fornitore,
       s.vat_number AS piva_fornitore, s.fiscal_code AS cf_fornitore,
       d.legal_entity_id, le.name AS intestatario, le.vat_number AS piva_intestatario,
       d.total_gross_amount, d.is_paid, d.doc_status, d.print_status,
       d.physical_copy_status, d.file_name, d.file_path,
       d.import_source, d.imported_at, d.created_at, d.updated_at
FROM documents d
LEFT JOIN suppliers s ON s.id = d.supplier_id
LEFT JOIN legal_entities le ON le.id = d.legal_entity_id
WHERE d.id = 924 OR d.document_number LIKE '%2351%'
   OR d.file_name LIKE '%GeaXw%'
ORDER BY d.created_at, d.id;

-- 3. Anagrafiche del fornitore, comprese eventuali varianti/disattivazioni.
SELECT id, name, vat_number, fiscal_code, is_active, typical_due_rule, typical_due_days
FROM suppliers
WHERE id = 55 OR name LIKE '%BUONINFANTE%' OR vat_number = '02106670652';
SELECT id, name, vat_number, fiscal_code, is_active
FROM legal_entities
WHERE id = 3 OR name LIKE '%BUONINFANTE%';

-- 4. Tutte le fatture del fornitore e appartenenza alla query server scadenziario.
SELECT d.id, d.document_number, d.document_date, d.due_date,
       d.supplier_id, d.legal_entity_id, d.total_gross_amount, d.is_paid,
       CASE WHEN d.is_paid = 0 THEN 'inclusa lato server'
            ELSE 'esclusa lato server' END AS scadenziario,
       d.imported_at, d.created_at, d.updated_at, d.print_status, d.file_name
FROM documents d
JOIN suppliers s ON s.id = d.supplier_id
WHERE s.id = 55 OR s.name LIKE '%BUONINFANTE%' OR s.vat_number = '02106670652'
ORDER BY d.document_date, d.document_number, d.id;

-- 5. Esiti persistiti: possono mancare quelli dei controlli preliminari.
SELECT id, document_id, file_name, file_hash, status, message, import_source, created_at
FROM import_logs
WHERE document_id = 924 OR file_name LIKE '%GeaXw%'
   OR document_id IN (SELECT id FROM documents WHERE document_number LIKE '%2351%')
ORDER BY created_at, id;

-- 6. Audit: cercare anche payload per documenti eliminati (FK diventa NULL).
SELECT id, document_id, action, created_at, payload
FROM document_audit_logs
WHERE document_id = 924 OR payload LIKE '%GeaXw%' OR payload LIKE '%2351%'
ORDER BY created_at, id;

-- 7. Pagamenti/scadenze associati, senza aggregazioni che possano confondere rate ed eventi.
SELECT p.id, p.document_id, p.due_date, p.expected_amount,
       p.paid_amount, p.paid_date, p.status, p.payment_method,
       p.payment_document_id, p.created_at, p.updated_at
FROM payments p
WHERE p.document_id = 924
   OR p.document_id IN (SELECT id FROM documents WHERE document_number LIKE '%2351%')
ORDER BY p.document_id, p.created_at, p.id;
SELECT * FROM credit_note_allocations WHERE invoice_document_id = 924 OR credit_note_document_id = 924;

-- 8. Aggiornamenti contemporanei: un gruppo programmed allo stesso orario e'
-- compatibile con una stampa di gruppo, ma non costituisce prova autonoma.
SELECT id, document_number, supplier_id, legal_entity_id,
       created_at, imported_at, updated_at, print_status
FROM documents
WHERE updated_at >= '2026-09-24 07:10:00'
  AND updated_at < '2026-09-24 07:13:00'
ORDER BY updated_at, id;

-- 9. Eventuali automatismi DB, visibili solo secondo i privilegi dell'utente.
SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE, ACTION_STATEMENT
FROM information_schema.TRIGGERS
WHERE TRIGGER_SCHEMA = DATABASE() AND EVENT_OBJECT_TABLE IN ('documents', 'payments');
SELECT EVENT_NAME, STATUS, EVENT_DEFINITION
FROM information_schema.EVENTS WHERE EVENT_SCHEMA = DATABASE();
