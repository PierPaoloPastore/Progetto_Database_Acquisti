"""
Route principali dell'applicazione (dashboard, home, ecc.).
"""

from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """
    Dashboard / homepage iniziale.

    In questa fase mostra solo un placeholder, poi sarà sostituita
    da una dashboard vera (statistiche, ultimi import, scadenze, ecc.).
    """
    return render_template("dashboard.html")
