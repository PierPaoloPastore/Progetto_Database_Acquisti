"""
Pacchetto principale dell'applicazione Flask.
"""

from flask import Flask, jsonify
from config import DevConfig
from .extensions import init_extensions

def create_app(config_class=DevConfig) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_class)
    init_extensions(app)

    from .middleware.auth_stub import init_auth_stub
    init_auth_stub(app)

    _register_blueprints(app)

    app.logger.info("Applicazione Flask inizializzata.")

    @app.route("/health")
    def healthcheck():
        return jsonify({"status": "ok"}), 200

    return app


def _register_blueprints(app: Flask) -> None:
    # Web
    from .web.routes_main import main_bp
    
    # FIX: Usiamo il nuovo routes_documents invece di invoices
    from .web.routes_documents import documents_bp
    
    from .web.routes_suppliers import suppliers_bp
    from .web.routes_categories import categories_bp
    from .web.routes_import import import_bp
    from .web.routes_export import export_bp
    from .web.routes_settings import settings_bp
    from .web.routes_payments import payments_bp

    app.register_blueprint(main_bp)
    
    # FIX: Prefisso URL /documents
    app.register_blueprint(documents_bp, url_prefix="/documents")
    
    app.register_blueprint(suppliers_bp, url_prefix="/suppliers")
    app.register_blueprint(categories_bp, url_prefix="/categories")
    app.register_blueprint(import_bp, url_prefix="/import")
    app.register_blueprint(export_bp, url_prefix="/export")
    app.register_blueprint(settings_bp)
    app.register_blueprint(payments_bp)

    # API
    from .api import api_documents_bp, api_categories_bp

    # Registra con il nuovo prefisso
    app.register_blueprint(api_documents_bp, url_prefix="/api/documents")
    app.register_blueprint(api_categories_bp, url_prefix="/api/categories")