# Pruebas de integracion y unitarias del modulo, cubriendo permisos, validaciones y casos limite.
import os

import pytest

from app import create_app
from app.config import TestConfig, Config
from app.extensions import db


# Ejecuta la logica de negocio solicitada; recibe sin parametros; interactua con la base de datos; devuelve el valor correspondiente.
@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        try:
            from seeds.seed_catalogs import seed
            seed()
        except Exception:
            pass
        yield application
        db.session.remove()
        db.drop_all()


# client: fixture de pytest que devuelve un cliente de prueba para la app Flask.
@pytest.fixture
def client(app):
    return app.test_client()


# Ejecuta la logica de negocio solicitada; recibe sin parametros; interactua con la base de datos; accede al sistema de archivos; devuelve el valor correspondiente.
@pytest.fixture
def sqlserver_app():
    url = os.getenv("TEST_DB_URL")
    if not url:
# SqlServerTestConfig: configuracion de la aplicacion con parametros leidos del entorno.
        pytest.skip("TEST_DB_URL no definido; omitiendo tests SQL Server")
    class SqlServerTestConfig(Config):
        SQLALCHEMY_DATABASE_URI = url
        TESTING = True
        JWT_SECRET_KEY = "test-secret"
        JWT_ACCESS_TOKEN_EXPIRES = __import__("datetime").timedelta(minutes=5)
    application = create_app(SqlServerTestConfig)
    with application.app_context():
        db.create_all()
        try:
            from seeds.seed_catalogs import seed
            seed()
        except Exception:
            pass
        yield application
        db.session.remove()
        db.drop_all()

# sqlserver_client: fixture de pytest que devuelve un cliente de prueba para la app conectada a SQL Server.
@pytest.fixture
def sqlserver_client(sqlserver_app):
    return sqlserver_app.test_client()
