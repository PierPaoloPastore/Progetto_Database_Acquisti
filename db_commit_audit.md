# db.session.commit() usage audit in app/services

> **⚠️ REFACTORING IN CORSO**: Questo documento traccia la migrazione verso il pattern **UnitOfWork** per la gestione transazionale del database. L'obiettivo è rimuovere tutti i commit espliciti (`db.session.commit()`) dai Service Layer, delegando il controllo transazionale al pattern UnitOfWork per garantire atomicità, consistency e rollback coerente in caso di errori. Questa è la **priorità attuale** per migliorare la stabilità e manutenibilità del sistema.

## Findings

- `create_or_update_category` in `app/services/category_service.py` performs category creation or update and commits immediately. 【F:app/services/category_service.py†L37-L68】
- `assign_category_to_line` in `app/services/category_service.py` updates a single invoice line's category and commits. 【F:app/services/category_service.py†L71-L90】
- `bulk_assign_category_to_invoice_lines` in `app/services/category_service.py` updates multiple lines for an invoice and commits once. 【F:app/services/category_service.py†L93-L136】
- `run_import` in `app/services/import_service.py` handles XML import per file, committing after creating invoice data and import logs. 【F:app/services/import_service.py†L23-L127】
- `update_invoice_status` in `app/services/invoice_service.py` updates invoice status fields and commits. 【F:app/services/invoice_service.py†L140-L165】

## Suggested refactors using UnitOfWork

Below are example patches to wrap each transactional block in a `with UnitOfWork() as session:` context (no explicit commits), following the pattern used in other services. Repository calls are shown with an optional `session=session` parameter if they are adapted to accept it.

### `create_or_update_category`
```python
from app.services.unit_of_work import UnitOfWork

def create_or_update_category(name: str, description: Optional[str] = None, category_id: Optional[int] = None) -> Any:
    data = {
        "name": name,
        "description": description,
        "is_active": True,
    }

    with UnitOfWork() as session:
        if category_id is not None:
            category = get_category_by_id(category_id, session=session)
        else:
            category = get_category_by_name(name, session=session)

        if category is None:
            category = create_category(session=session, **data)
        else:
            update_category(category, **data)

        return category
```

### `assign_category_to_line`
```python
from app.services.unit_of_work import UnitOfWork

def assign_category_to_line(line_id: int, category_id: Optional[int]) -> Optional[InvoiceLine]:
    with UnitOfWork() as session:
        line = get_invoice_line_by_id(line_id, session=session)
        if line is None:
            return None

        if category_id is None:
            line.category_id = None
        else:
            category = get_category_by_id(category_id, session=session)
            if category is None:
                return None
            line.category_id = category.id

        return line
```

### `bulk_assign_category_to_invoice_lines`
```python
from app.services.unit_of_work import UnitOfWork

def bulk_assign_category_to_invoice_lines(invoice_id: int, category_id: Optional[int], line_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    with UnitOfWork() as session:
        lines = list_lines_by_invoice(invoice_id, session=session)
        if line_ids is not None:
            lines = [l for l in lines if l.id in line_ids]

        updated_count = 0
        if category_id is None:
            for line in lines:
                line.category_id = None
                updated_count += 1
        else:
            category = get_category_by_id(category_id, session=session)
            if category is None:
                return {
                    "success": False,
                    "message": "Categoria non trovata",
                    "updated_count": 0,
                }
            for line in lines:
                line.category_id = category.id
                updated_count += 1

        return {
            "success": True,
            "message": "Categorie aggiornate con successo",
            "updated_count": updated_count,
        }
```

### `run_import`
```python
from app.services.unit_of_work import UnitOfWork

def run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> Dict:
    ...
    for xml_path in xml_files:
        ...
        try:
            with UnitOfWork() as session:
                header_data = _extract_header_data(xml_path)
                legal_entity = _get_or_create_legal_entity(header_data, session=session)
                invoice_legal_entity_id = legal_entity_id or legal_entity.id
                if invoice_legal_entity_id is None:
                    raise ValueError("Impossibile determinare il legal_entity_id dal file XML e nessun valore fornito")

                if not hasattr(invoice_dto, "header") or invoice_dto.header is None:
                    invoice_dto.header = {}
                invoice_dto.header["legal_entity_id"] = invoice_legal_entity_id

                supplier = get_or_create_supplier_from_dto(invoice_dto.supplier, session=session)
                if supplier.id is None:
                    raise ValueError(f"ID fornitore nullo per {supplier.name}")

                invoice, created = _create_invoice_tree(
                    invoice_dto,
                    supplier.id,
                    invoice_legal_entity_id,
                    str(import_folder),
                    session=session,
                )

                if not created:
                    _log_skip(logger, file_name, invoice.id, summary, reason="Duplicato per file_name/file_hash")
                    _safe_log_import(
                        file_name=file_name,
                        status="skipped",
                        message="Fattura già presente (nome/hash)",
                        invoice_id=invoice.id,
                        folder=str(import_folder),
                        file_hash=invoice_dto.file_hash,
                        session=session,
                    )
                    continue

                create_import_log(
                    file_name=file_name,
                    file_hash=invoice_dto.file_hash,
                    import_source=str(import_folder),
                    status="success",
                    message="Import completato con successo",
                    invoice_id=invoice.id,
                    session=session,
                )

                _log_success(logger, file_name, invoice.id, supplier.id, summary)
        except Exception as exc:  # noqa: BLE001
            _log_error_db(logger, file_name, exc, summary, str(import_folder), invoice_dto)
```

### `update_invoice_status`
```python
from app.services.unit_of_work import UnitOfWork

def update_invoice_status(
    invoice_id: int,
    doc_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    due_date: Optional[date] = None,
) -> Optional[Invoice]:
    with UnitOfWork() as session:
        invoice = get_invoice_by_id(invoice_id, session=session)
        if invoice is None:
            return None

        if doc_status is not None:
            invoice.doc_status = doc_status
        if payment_status is not None:
            invoice.payment_status = payment_status
        if due_date is not None:
            invoice.due_date = due_date

        return invoice
```
