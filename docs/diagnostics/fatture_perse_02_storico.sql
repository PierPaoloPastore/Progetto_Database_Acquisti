-- Secondo giro dopo i risultati Q1-Q5. Solo SELECT, blocchi indipendenti.

-- A. Imported_at NULL e' isolato o ricorre tra importazioni con success?
SELECT DATE(d.created_at) AS giorno_creazione,
       COUNT(*) AS documenti_con_success,
       SUM(d.imported_at IS NULL) AS senza_imported_at,
       MIN(d.id) AS primo_id, MAX(d.id) AS ultimo_id
FROM documents d
WHERE EXISTS (
    SELECT 1 FROM import_logs il
    WHERE il.document_id = d.id AND il.status = 'success'
)
GROUP BY DATE(d.created_at)
ORDER BY giorno_creazione;

-- B. Continuita dei log intorno ai primi e secondi passaggi osservati sul disco.
-- Zero righe NON dimostra da solo un reset: incrociare con access log/backup.
SELECT DATE(created_at) AS giorno, status, COUNT(*) AS quantita,
       MIN(id) AS primo_log, MAX(id) AS ultimo_log,
       SUM(document_id IS NULL) AS senza_documento
FROM import_logs
WHERE (created_at >= '2026-07-01' AND created_at < '2026-07-27')
   OR (created_at >= '2026-09-09' AND created_at < '2026-09-12')
GROUP BY DATE(created_at), status
ORDER BY giorno, status;

-- C. Trigger che potrebbero modificare/cancellare record o cambiare imported_at.
SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE,
       ACTION_TIMING, ACTION_STATEMENT
FROM information_schema.TRIGGERS
WHERE TRIGGER_SCHEMA = DATABASE()
  AND EVENT_OBJECT_TABLE IN ('documents', 'import_logs', 'document_audit_logs');

-- D. Eventi MySQL. Risultati vuoti dipendono anche dai privilegi dell'utente.
SELECT EVENT_NAME, STATUS, EVENT_DEFINITION
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = DATABASE();

-- E. Esiste in generale una traccia conservata delle cancellazioni?
SELECT action, COUNT(*) AS quantita, MIN(created_at) AS prima,
       MAX(created_at) AS ultima, SUM(document_id IS NULL) AS senza_documento
FROM document_audit_logs
GROUP BY action;
SELECT status, COUNT(*) AS quantita, MIN(created_at) AS primo,
       MAX(created_at) AS ultimo, SUM(document_id IS NULL) AS senza_documento
FROM import_logs
GROUP BY status;
