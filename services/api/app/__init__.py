from flask import Flask

from app.config import Config
from app.extensions import db, migrate


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

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

    return app

