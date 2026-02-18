"""
Route principali dell'applicazione (dashboard, home, ecc.).
"""

from datetime import date, timedelta

from flask import Blueprint, render_template
from sqlalchemy import func
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

        unpaid_query = base_query.filter(
            Document.document_type == "invoice",
            Document.is_paid == False,
        )
        unpaid_count = unpaid_query.count()
        overdue_count = unpaid_query.filter(
            Document.due_date.isnot(None),
            Document.due_date < today,
        ).count()
        due_soon_count = unpaid_query.filter(
            Document.due_date.isnot(None),
            Document.due_date >= today,
            Document.due_date <= soon_limit,
        ).count()

        total_unpaid_amount = (
            uow.session.query(func.coalesce(func.sum(Document.total_gross_amount), 0))
            .filter(
                Document.document_type == "invoice",
                Document.is_paid == False,
            )
            .scalar()
            or 0
        )

        upcoming_due = (
            uow.session.query(Document)
            .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
            .filter(
                Document.document_type == "invoice",
                Document.is_paid == False,
                Document.due_date.isnot(None),
            )
            .order_by(Document.due_date.asc())
            .limit(8)
            .all()
        )

        last_imports = (
            uow.session.query(Document)
            .options(joinedload(Document.supplier))
            .filter(Document.imported_at.isnot(None))
            .order_by(Document.imported_at.desc())
            .limit(6)
            .all()
        )

    payment_service.attach_payment_amounts(upcoming_due)

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
