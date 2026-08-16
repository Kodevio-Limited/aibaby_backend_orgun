from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True

# Dev: don't let task dispatch hang retrying an unreachable broker. If Redis isn't
# running locally, fail fast and let the service layer run the task synchronously.
# Use localhost so a missing Redis fails instantly (the .env value points at the
# docker-internal hostname 'redis', which times out on DNS locally).
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_BROKER_CONNECTION_RETRY = False
CELERY_BROKER_CONNECTION_MAX_RETRIES = 0
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
CELERY_TASK_IGNORE_RESULT = True
CELERY_RESULT_BACKEND = 'cache+memory://'
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'max_retries': 0,
    'socket_connect_timeout': 1,
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
