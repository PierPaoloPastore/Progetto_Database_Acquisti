"""Routes for payments and batch processing."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.services import payment_service

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("/", methods=["GET"], endpoint="payment_index")
def payment_index():
    overdue = payment_service.get_overdue_payments()
    unpaid = payment_service.get_all_unpaid_payments()

    return render_template(
        "payments/index.html",
        overdue=overdue,
        unpaid=unpaid,
    )


@payments_bp.route("/batch", methods=["POST"], endpoint="batch_payment")
def batch_payment():
    file = request.files.get("file")

    payment_ids = request.form.getlist("payment_ids")
    amounts = request.form.getlist("amounts")
    method = request.form.get("method")
    notes = request.form.get("notes")

    allocations = []
    for payment_id, amount in zip(payment_ids, amounts):
        try:
            allocations.append({"id": int(payment_id), "amount": float(amount)})
        except (TypeError, ValueError):
            continue

    try:
        payment_service.create_batch_payment(file=file, allocations=allocations, method=method, notes=notes)
        flash("Pagamento cumulativo registrato con successo.", "success")
    except Exception as exc:  # pragma: no cover - flash only
        flash(f"Errore durante il pagamento cumulativo: {exc}", "danger")

    return redirect(url_for("payments.payment_index"))
