import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DB_URL",
        "mssql+pyodbc://sigos:Sigos_Dev_2026!@localhost:1433/sigos"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    LOGIN_RATE_LIMIT_MAX = 5
    LOGIN_RATE_LIMIT_WINDOW = 300  # 5 minutes


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    JWT_SECRET_KEY = "test-secret"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
