import os
from datetime import timedelta


class ProductionConfig:
    SQLALCHEMY_DATABASE_URI = os.environ["DB_URL"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False

    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    LOGIN_RATE_LIMIT_MAX = 5
    LOGIN_RATE_LIMIT_WINDOW = 300

    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/uploads")

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "json")
