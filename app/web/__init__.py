# ... (parte Web rimane uguale) ...

    # API
    from .api import api_documents_bp, api_categories_bp

    # Registra con il nuovo prefisso
    app.register_blueprint(api_documents_bp, url_prefix="/api/documents")
    app.register_blueprint(api_categories_bp, url_prefix="/api/categories")