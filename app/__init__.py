"""
Pacchetto principale dell'applicazione Flask.

Espone la factory function create_app().
"""

from flask import Flask, jsonify

from config import DevConfig
from .extensions import init_extensions


def create_app(config_class=DevConfig) -> Flask:
    """
    Factory function per creare e configurare l'app Flask.

    :param config_class: classe di configurazione da usare (DevConfig, ProdConfig, ecc.)
    :return: istanza configurata di Flask
    """
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static",
    )

    # Carica configurazione
    app.config.from_object(config_class)

    # Inizializza estensioni (db, logging, ecc.)
    init_extensions(app)

    # Middleware auth stub (inserisce g.current_user fittizio)
    from .middleware.auth_stub import init_auth_stub
    init_auth_stub(app)

    # Registrazione blueprint web/API
    _register_blueprints(app)

    # Log di avvio app
    app.logger.info(
        "Applicazione Flask inizializzata.",
        extra={"component": "app_factory", "env": app.config.get("ENV")},
    )

    # Endpoint semplice per verificare che l'app sia attiva
    @app.route("/health")
    def healthcheck():
        """
        Endpoint di health-check.

        Utile per test manuali o per probe di container/orchestratori.
        """
        return jsonify({"status": "ok"}), 200

    return app


def _register_blueprints(app: Flask) -> None:
    """
    Registra tutti i blueprint dell'applicazione.

    Web (HTML):
    - main_bp: dashboard / homepage
    - invoices_bp: elenco/dettaglio fatture
    - suppliers_bp: elenco/dettaglio fornitori
    - categories_bp: gestione categorie
    - import_bp: esecuzione import XML
    - export_bp: export CSV
    - settings_bp: gestione impostazioni

    API (JSON):
    - api_invoices_bp   -> /api/invoices/...
    - api_categories_bp -> /api/categories/...
    """
    # Web
    from .web.routes_main import main_bp
    from .web.routes_invoices import invoices_bp
    from .web.routes_suppliers import suppliers_bp
    from .web.routes_categories import categories_bp
    from .web.routes_import import import_bp
    from .web.routes_export import export_bp
    # Gestione impostazioni utente
    from .web.routes_settings import settings_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(invoices_bp, url_prefix="/invoices")
    app.register_blueprint(suppliers_bp, url_prefix="/suppliers")
    app.register_blueprint(categories_bp, url_prefix="/categories")
    app.register_blueprint(import_bp, url_prefix="/import")
    app.register_blueprint(export_bp, url_prefix="/export")
    app.register_blueprint(settings_bp)

    # API
    from .api import api_invoices_bp, api_categories_bp

    app.register_blueprint(api_invoices_bp, url_prefix="/api/invoices")
    app.register_blueprint(api_categories_bp, url_prefix="/api/categories")
