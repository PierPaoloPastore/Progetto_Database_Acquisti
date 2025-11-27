from sqlalchemy import func  # questo rimane in alto nel file


def get_supplier_account_balance(
    supplier_id: int, legal_entity_id: Optional[int] = None
) -> Dict[str, Decimal | int]:
    """Calcola l'estratto conto di un fornitore, opzionalmente filtrato per legal entity.

    Ritorna un dizionario con:
    - expected_total: totale fatture (expected_amount)
    - paid_total: totale pagato (paid_amount)
    - residual: expected_total - paid_total
    - invoice_count: numero di fatture considerate
    """
    query = (
        db.session.query(
            func.coalesce(func.sum(Invoice.expected_amount), 0),
            func.coalesce(func.sum(Payment.paid_amount), 0),
            func.count(func.distinct(Invoice.id)),
        )
        .select_from(Invoice)
        .outerjoin(Payment, Payment.invoice_id == Invoice.id)
        .filter(Invoice.supplier_id == supplier_id)
    )

    if legal_entity_id is not None:
        query = query.filter(Invoice.legal_entity_id == legal_entity_id)

    expected_total, paid_total, invoice_count = query.one()

    residual = expected_total - paid_total

    return {
        "expected_total": expected_total,
        "paid_total": paid_total,
        "residual": residual,
        "invoice_count": invoice_count,
    }
