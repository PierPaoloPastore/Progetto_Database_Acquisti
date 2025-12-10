from __future__ import annotations

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, send_file, url_for,
)

from app.repositories import get_payment_document
from app.services import payment_service

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("/payments/inbox", methods=["GET"])
def inbox_view():
    # FIX: Filtra per 'partial' invece di 'partially_assigned' e rimuove 'error'
    documents = payment_service.get_payment_inbox(
        ["pending_review", "partial", "imported"]
    )
    return render_template("payments/inbox.html", documents=documents)


@payments_bp.route("/payments/upload", methods=["POST"])
def upload_documents():
    files = request.files.getlist("files")
    if not files:
        flash("Nessun file caricato.", "warning")
        return redirect(url_for("payments.inbox_view"))

    payment_service.upload_payment_documents(files)
    flash("Documenti di pagamento caricati correttamente.", "success")
    return redirect(url_for("payments.inbox_view"))


@payments_bp.route("/payments/<int:document_id>/review", methods=["GET"])
def review_view(document_id: int):
    try:
        context = payment_service.review_payment_document(document_id)
    except ValueError:
        abort(404)

    return render_template(
        "payments/review.html",
        document=context["document"],
        candidate_invoices=context["candidate_invoices"],
    )


@payments_bp.route("/payments/<int:document_id>/assign", methods=["POST"])
def assign_payment(document_id: int):
    invoice_ids = request.form.getlist("invoice_id")
    assignments = []
    
    if not invoice_ids:
        flash("Nessuna fattura selezionata.", "warning")
        return redirect(url_for("payments.review_view", document_id=document_id))

    for invoice_id in invoice_ids:
        amount_value = request.form.get(f"amount_{invoice_id}")
        if not amount_value:
            continue
        assignments.append(
            {
                "invoice_id": int(invoice_id),
                "amount": amount_value,
                "paid_date": request.form.get(f"paid_date_{invoice_id}") or None,
                "notes": request.form.get(f"notes_{invoice_id}") or None,
                "payment_method": request.form.get(f"payment_method_{invoice_id}") or None,
            }
        )

    try:
        document = payment_service.assign_payments_to_invoices(document_id, assignments)
    except ValueError:
        abort(404)

    # FIX: Controlla lo stato 'partial'
    if document.status == "partial":
        flash("Pagamenti parzialmente assegnati. Completa le associazioni.", "warning")
        return redirect(url_for("payments.review_view", document_id=document_id))

    flash("Pagamenti registrati e documenti aggiornati.", "success")
    return redirect(url_for("payments.inbox_view"))


@payments_bp.route("/payments/<int:document_id>/file", methods=["GET"])
def serve_payment_file(document_id: int):
    document = get_payment_document(document_id)
    if document is None: abort(404)
    return send_file(document.file_path, download_name=document.file_name)