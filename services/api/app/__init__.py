from flask import Flask

from app.config import get_config_class
from app.extensions import db, migrate


# -*- coding: utf-8 -*-
# create_app: fabrica de la aplicacion. Sin argumento, la configuracion se elige con SIGOS_ENV
# (development por defecto). Una clase se instancia para leer el entorno en este momento.
def create_app(config_object=None):
    app = Flask(__name__)
    config = config_object or get_config_class()
    if isinstance(config, type):
        config = config()
    app.config.from_object(config)
    app.config.setdefault("ENV_NAME", "development")

    if not app.config.get("TESTING"):
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise RuntimeError("DB_URL environment variable is required")
        if not app.config.get("JWT_SECRET_KEY"):
            raise RuntimeError("JWT_SECRET_KEY environment variable is required")

    from app.logging_config import setup_logging
    setup_logging(app)

# Aplica la configuracion solicitada; recibe response; sin efectos secundarios adicionales; devuelve el valor correspondiente.
    @app.after_request
    def apply_utf8_charset(response):
        ct = response.headers.get("Content-Type", "")
        if "charset" not in ct:
            if ct.startswith("text/") or ct == "application/json":
                response.headers["Content-Type"] = ct + "; charset=utf-8"
        return response

    # Todas las respuestas de la API (datos, archivos de evidencia, firmas) son por usuario: ningun cliente ni
    # proxy debe guardarlas. Asi otra cuenta en el mismo equipo no puede ver respuestas de la sesion anterior.
    @app.after_request
    def apply_no_store(response):
        from flask import request
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, private, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            vary = response.headers.get("Vary", "")
            if "Authorization" not in vary:
                response.headers["Vary"] = (vary + ", Authorization").lstrip(", ")
        return response

    db.init_app(app)
    migrate.init_app(app, db)

    from app.health.routes import blueprint as health_blueprint
    app.register_blueprint(health_blueprint, url_prefix="/api/v1")

    from app.identity.routes import blueprint as identity_blueprint
    app.register_blueprint(identity_blueprint, url_prefix="/api/v1")

    from app.workorders.routes import blueprint as workorders_blueprint
    app.register_blueprint(workorders_blueprint, url_prefix="/api/v1")

    from app.materials.routes import blueprint as materials_blueprint
    app.register_blueprint(materials_blueprint, url_prefix="/api/v1")

    from app.evidence.routes import blueprint as evidence_blueprint
    app.register_blueprint(evidence_blueprint, url_prefix="/api/v1")

    from app.sync.routes import blueprint as sync_blueprint
    app.register_blueprint(sync_blueprint, url_prefix="/api/v1")

    from app.notifications.routes import blueprint as notifications_blueprint
    app.register_blueprint(notifications_blueprint, url_prefix="/api/v1")

    from app.dashboard.routes import blueprint as dashboard_blueprint
    app.register_blueprint(dashboard_blueprint, url_prefix="/api/v1")

    from app.technicians.routes import blueprint as technicians_blueprint
    app.register_blueprint(technicians_blueprint, url_prefix="/api/v1")

    from app.catalogs.routes import blueprint as catalogs_blueprint
    app.register_blueprint(catalogs_blueprint, url_prefix="/api/v1")

    from app.calendar.routes import blueprint as calendar_blueprint
    app.register_blueprint(calendar_blueprint, url_prefix="/api/v1")

    from app.settings.routes import blueprint as settings_blueprint
    app.register_blueprint(settings_blueprint, url_prefix="/api/v1")

    from app.reportes.routes import blueprint as reportes_blueprint
    app.register_blueprint(reportes_blueprint, url_prefix="/api/v1")

    from app.exports.routes import blueprint as exports_blueprint
    app.register_blueprint(exports_blueprint, url_prefix="/api/v1")

    from app.tecnico.routes import blueprint as tecnico_blueprint
    app.register_blueprint(tecnico_blueprint, url_prefix="/api/v1/tecnico")

    return app
