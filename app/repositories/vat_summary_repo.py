"""
Repository per il modello VatSummary.

Gestisce le operazioni di lettura/creazione dei riepiloghi IVA.
"""

from typing import List

from app.extensions import db
from app.models import VatSummary


def list_vat_summaries_by_invoice(document_id: int) -> List[VatSummary]:
    """Restituisce tutti i riepiloghi IVA associati a un documento."""
    return (
        VatSummary.query.filter_by(document_id=document_id)
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
