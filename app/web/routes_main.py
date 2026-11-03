"""
Route principali dell'applicazione (dashboard, home, ecc.).
"""

from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, render_template
from sqlalchemy.orm import joinedload

from app.models import Document
from app.services import payment_service
from app.services.unit_of_work import UnitOfWork

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """
    Dashboard / homepage iniziale.

    In questa fase mostra solo un placeholder, poi sarà sostituita
    da una dashboard vera (statistiche, ultimi import, scadenze, ecc.).
    """
    today = date.today()
    soon_limit = today + timedelta(days=7)

    with UnitOfWork() as uow:
        base_query = uow.session.query(Document)

        review_count = base_query.filter(
            Document.doc_status == "pending_physical_copy"
        ).count()
        missing_copy_count = base_query.filter(
            Document.physical_copy_status == "missing"
        ).count()

        # ponytail: snapshot in memoria; elaborare a blocchi se lo storico cresce troppo.
        invoices = (
            base_query.options(joinedload(Document.supplier), joinedload(Document.legal_entity))
            .filter(Document.document_type == "invoice")
            .all()
        )
        payment_service.attach_payment_amounts(invoices)
        unpaid = [doc for doc in invoices if doc.remaining_amount > 0]
        unpaid_count = len(unpaid)
        overdue_count = sum(bool(doc.due_date and doc.due_date < today) for doc in unpaid)
        due_soon_count = sum(bool(doc.due_date and today <= doc.due_date <= soon_limit) for doc in unpaid)
        total_unpaid_amount = sum((Decimal(str(doc.remaining_amount)) for doc in unpaid), Decimal("0"))
        upcoming_due = sorted(
            (doc for doc in unpaid if doc.due_date), key=lambda doc: doc.due_date
        )[:8]

        last_imports = (
            uow.session.query(Document)
            .options(joinedload(Document.supplier))
            .filter(Document.imported_at.isnot(None))
            .order_by(Document.imported_at.desc())
            .limit(6)
            .all()
        )

    return render_template(
        "dashboard.html",
        review_count=review_count,
        missing_copy_count=missing_copy_count,
        unpaid_count=unpaid_count,
        overdue_count=overdue_count,
        due_soon_count=due_soon_count,
        total_unpaid_amount=total_unpaid_amount,
        upcoming_due=upcoming_due,
        last_imports=last_imports,
        today=today,
        soon_limit=soon_limit,
    )
