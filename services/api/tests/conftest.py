import os

import pytest

from app import create_app
from app.config import TestConfig, Config
from app.extensions import db


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


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sqlserver_app():
    url = os.getenv("TEST_DB_URL")
    if not url:
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

@pytest.fixture
def sqlserver_client(sqlserver_app):
    return sqlserver_app.test_client()
