-- Terzo giro: include i documenti SENZA log success, esclusi dalla query A precedente.
-- Solo SELECT. Gli eventuali buchi negli ID NON dimostrano cancellazioni.

-- F. Documenti creati a luglio prima dell'importazione del 25, anche incompleti/manuali.
SELECT d.id, d.document_number, d.document_date, d.total_gross_amount,
       d.file_name, d.file_path, d.import_source, d.imported_at,
       d.created_at, d.updated_at, d.doc_status, d.note,
       (SELECT COUNT(*) FROM import_logs il WHERE il.document_id = d.id) AS numero_log
FROM documents d
WHERE d.created_at >= '2026-07-01' AND d.created_at < '2026-07-25'
ORDER BY d.created_at, d.id;

-- G. Cancellazioni conservate e log scollegati: statistiche complessive.
SELECT action, COUNT(*) AS quantita, MIN(created_at) AS prima,
       MAX(created_at) AS ultima, SUM(document_id IS NULL) AS senza_documento
FROM document_audit_logs
GROUP BY action;
SELECT status, COUNT(*) AS quantita, MIN(created_at) AS primo,
       MAX(created_at) AS ultimo, SUM(document_id IS NULL) AS senza_documento
FROM import_logs
GROUP BY status;
