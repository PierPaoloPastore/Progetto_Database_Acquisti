"""
Route per la gestione dei Pagamenti.
"""
from __future__ import annotations
from datetime import date, datetime
from flask import Blueprint, request, redirect, url_for, flash, render_template

from app.services.payment_service import (
    add_payment, 
    delete_payment, 
    list_payments_by_document,
    list_overdue_payments_for_ui
)

payments_bp = Blueprint("payments", __name__)

@payments_bp.route("/", methods=["GET"])
def inbox_view():
    """
    Mostra la dashboard dei pagamenti (Scadenzario / Inbox).
    """
    # Recupera le fatture scadute usando il service aggiornato con UoW
    overdue_invoices = list_overdue_payments_for_ui()
    
    return render_template(
        "payments/inbox.html",
        overdue_invoices=overdue_invoices,
        today=date.today()  # <--- CORREZIONE: Passiamo la data odierna al template
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