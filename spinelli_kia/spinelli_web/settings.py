"""Django settings for the Spinelli Kia final prototype (local demo).

The problem-domain classes (models.py) and the data layer (store.py, schema.sql) are our own,
as designed in Milestones 5 and 7, so Django's ORM and its database are not used:
Django only provides the web pages (HCI layer). Sessions are kept in signed cookies.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "demo-only-key-not-for-production-btm495-team23"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = ["django.contrib.staticfiles", "portal"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "spinelli_web.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request", "portal.common.chrome"]},
}]
WSGI_APPLICATION = "spinelli_web.wsgi.application"
DATABASES = {}
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
LANGUAGE_CODE = "en"
TIME_ZONE = "America/Toronto"
USE_I18N = False
USE_TZ = False
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
