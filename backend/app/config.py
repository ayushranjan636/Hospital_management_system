import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""
    
    # Paths
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

    # Security keys
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-key")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    # Database (SQLite - no setup needed!)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(INSTANCE_DIR, 'hospital.db')}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_RESET_DB_ON_STARTUP = str(os.getenv("AUTO_RESET_DB_ON_STARTUP", "True")).lower() == "true"

    # Redis (for caching and Celery jobs)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Cache settings
    CACHE_TYPE = "SimpleCache"
    # CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes

    # Celery (background jobs)
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # Email settings (for notifications)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = str(os.getenv("MAIL_USE_TLS", "True")).lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "your-email@gmail.com")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "your-app-password").replace(" ", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "hms@hospital.local")

