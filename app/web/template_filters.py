"""
Registrazione filtri Jinja per la UI.
"""

from __future__ import annotations

from flask import Flask

from app.services.formatting_service import format_amount, format_int, format_number


def register_template_filters(app: Flask) -> None:
    app.add_template_filter(format_amount, "format_amount")
    app.add_template_filter(format_number, "format_number")
    app.add_template_filter(format_int, "format_int")
