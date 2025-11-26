"""
Repository per il modello VatSummary.

Gestisce le operazioni di lettura/creazione dei riepiloghi IVA.
"""

from typing import List

from app.extensions import db
from app.models import VatSummary


def list_vat_summaries_by_invoice(invoice_id: int) -> List[VatSummary]:
    """Restituisce tutti i riepiloghi IVA associati a una fattura."""
    return (
        VatSummary.query.filter_by(invoice_id=invoice_id)
        .order_by(VatSummary.vat_rate.asc())
        .all()
    )


def create_vat_summary(**kwargs) -> VatSummary:
    """
    Crea un nuovo riepilogo IVA e lo aggiunge alla sessione.

    Non esegue il commit.
    """
    summary = VatSummary(**kwargs)
    db.session.add(summary)
    return summary
