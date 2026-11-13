from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-only-secret-key-change-me"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "pipelines",
]

MIDDLEWARE = [
    "pipelines.middleware.NoCacheStaticMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {"context_processors": ["pipelines.context.static_version"]},
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        # Wait instead of erroring if another thread is writing.
        "OPTIONS": {"timeout": 20},
    }
}

USE_TZ = True
TIME_ZONE = "UTC"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Bump this when JS changes so browsers load the new files.
STATIC_VERSION = "3"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# How many tasks can run at the same time (across all runs).
TASK_WORKERS = 4
# How many pipeline runs can be processed at the same time.
RUN_WORKERS = 2
