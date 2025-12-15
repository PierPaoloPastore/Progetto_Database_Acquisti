"""
Route per la gestione dei Pagamenti.
"""
from __future__ import annotations
from datetime import date, datetime
from flask import Blueprint, request, redirect, url_for, flash, render_template

from app.models import Document
from app.services.payment_service import (
    add_payment,
    create_batch_payment,
    delete_payment,
    list_payments_by_document,
    list_overdue_payments_for_ui,
)
from app.services.unit_of_work import UnitOfWork

payments_bp = Blueprint("payments", __name__)

@payments_bp.route("/", methods=["GET"], endpoint="payment_index")
@payments_bp.route("/", methods=["GET"], endpoint="inbox_view")
def payment_index():
    """
    Mostra la dashboard dei pagamenti (Scadenzario / Inbox).
    """
    today = date.today()

    with UnitOfWork() as uow:
        overdue_invoices = list_overdue_payments_for_ui()

        all_unpaid_invoices = (
            uow.session.query(Document)
            .filter(
                Document.document_type == "invoice",
                Document.is_paid == False,
            )
            .order_by(Document.due_date.asc())
            .all()
        )

    return render_template(
        "payments/inbox.html",
        overdue_invoices=overdue_invoices,
        all_unpaid_invoices=all_unpaid_invoices,
        today=today,
    )

@payments_bp.route("/add/<int:document_id>", methods=["POST"])
def add_view(document_id: int):
    try:
        # Gestione virgola/punto per l'importo
        amount_str = request.form.get("amount", "0").replace(",", ".")
        if not amount_str:
            amount = 0.0
        else:
            amount = float(amount_str)
            
        date_str = request.form.get("payment_date")
        description = request.form.get("description")

        if not date_str:
            flash("Data pagamento obbligatoria.", "warning")
            return redirect(url_for("documents.detail_view", document_id=document_id))

        payment_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        add_payment(
            document_id=document_id,
            amount=amount,
            payment_date=payment_date,
            description=description
        )
        flash("Pagamento aggiunto con successo.", "success")

    except ValueError:
        flash("Importo non valido.", "danger")
    except Exception as e:
        flash(f"Errore durante il salvataggio: {e}", "danger")

    return redirect(url_for("documents.detail_view", document_id=document_id))

@payments_bp.route("/delete/<int:payment_id>", methods=["POST"])
def delete_view(payment_id: int):
    # Recuperiamo document_id prima di cancellare per il redirect 
    # (idealmente il service potrebbe ritornarlo, ma qui usiamo il referrer)
    
    if delete_payment(payment_id):
        flash("Pagamento cancellato.", "success")
    else:
        flash("Errore: pagamento non trovato.", "danger")

    # Torna alla pagina da cui sei venuto (solitamente il dettaglio fattura)
    return redirect(request.referrer or url_for("documents.list_view"))


@payments_bp.route("/batch", methods=["POST"])
def batch_payment():
    """Registra un pagamento cumulativo su più scadenze."""
    file = request.files.get("file")
    method = request.form.get("method") or request.form.get("payment_method")
    notes = request.form.get("notes")

    selected_payments = request.form.getlist("payment_id")
    allocations = []
    for payment_id in selected_payments:
        raw_amount = (request.form.get(f"amount_{payment_id}") or "0").replace(",", ".")
        try:
            amount = float(raw_amount)
        except ValueError:
            continue

        if amount <= 0:
            continue

        allocations.append({"payment_id": int(payment_id), "amount": amount})

    if not allocations:
        flash("Seleziona almeno un pagamento con un importo valido.", "warning")
        return redirect(url_for("payments.payment_index"))

    try:
        create_batch_payment(file, allocations, method, notes)
        flash("Pagamento cumulativo registrato con successo.", "success")
    except Exception as exc:  # pragma: no cover - logging/flash only
        flash(f"Errore durante il pagamento cumulativo: {exc}", "danger")

    return redirect(url_for("payments.payment_index"))