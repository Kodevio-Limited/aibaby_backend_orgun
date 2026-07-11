# Django Settings Structure (Production-Ready)

This is your existing standard, kept as-is with one addition: a shared
`StandardPagination` class, since your project standard is "always paginate
with a shared StandardPagination class" rather than the framework default.

## Folder Structure

```
config/
├── settings/
│   ├── __init__.py
│   ├── base.py
│   ├── development.py
│   └── production.py
├── urls.py
├── wsgi.py
└── asgi.py
```

## core/pagination.py (new — referenced from settings)

```python
from rest_framework.pagination import LimitOffsetPagination

class StandardPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100
```

## settings/base.py

```python
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_celery_beat',
    # project apps
    'accounts',
    'babies',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/day',
        'anon': '100/day',
    },
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

DATABASES = {
    'default': env.db('DATABASE_URL')
}

CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/0')

# Single image-generation API key — see 03-Implementation-Guide.md
REPLICATE_API_TOKEN = env('REPLICATE_API_TOKEN')
```

## settings/development.py

```python
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True
```

## settings/production.py

```python
from .base import *

DEBUG = False
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
```

## manage.py — point to correct settings

```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
```

Override locally with:
```
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver
```

## The Non-Negotiable Rule

`DEBUG=False` in production, always. A leaked `DEBUG=True` page exposes your
secret key, database credentials, and full stack traces to anyone who
triggers a 500 error.

## Do Not

- Set `DEBUG=True` in production settings, ever
- Use `ALLOWED_HOSTS = ['*']` in production
- Skip `CORS_ALLOWED_ORIGINS` (don't use `CORS_ALLOW_ALL_ORIGINS` in prod)
- Use the framework's default pagination class directly — always go through
  `core.pagination.StandardPagination` so every list endpoint behaves
  identically
