import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework.authtoken", "corsheaders", "notifications",
]
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages"]},
}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": dj_database_url.parse(
    os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    conn_max_age=600)}
USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.TokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
CORS_ALLOWED_ORIGINS = [o for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Provider config
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "postmark").lower()
POSTMARKAPP_TOKEN = os.getenv("POSTMARKAPP_TOKEN", "")
POSTMARK_FROM_EMAIL = os.getenv("POSTMARK_FROM_EMAIL", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "")
ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID", "")
ONESIGNAL_REST_API_KEY = os.getenv("ONESIGNAL_REST_API_KEY", "")

# ---------------- Logging ----------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "True" if DEBUG else "False") == "True"
LOG_DIR = BASE_DIR / "logs"
_handlers = ["console"]
_file_handlers = {}
if LOG_TO_FILE:
    LOG_DIR.mkdir(exist_ok=True)
    _handlers.append("file")
    _file_handlers = {
        "file": {"class": "logging.handlers.RotatingFileHandler", "filename": LOG_DIR / "app.log",
                 "maxBytes": 5_000_000, "backupCount": 3, "formatter": "verbose", "encoding": "utf-8"},
        "errors": {"class": "logging.handlers.RotatingFileHandler", "filename": LOG_DIR / "errors.log",
                   "maxBytes": 5_000_000, "backupCount": 3, "formatter": "verbose", "level": "WARNING", "encoding": "utf-8"},
    }
    _handlers.append("errors")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"verbose": {"format": "{asctime} | {levelname:<7} | {name} | {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}, **_file_handlers},
    "loggers": {
        "notifications": {"handlers": _handlers, "level": LOG_LEVEL, "propagate": False},
        "requests_log": {"handlers": _handlers, "level": LOG_LEVEL, "propagate": False},
        "django.request": {"handlers": _handlers, "level": "ERROR", "propagate": False},
    },
}