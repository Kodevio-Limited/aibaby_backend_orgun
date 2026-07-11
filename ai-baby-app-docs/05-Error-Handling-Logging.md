# Error Handling & Logging

This is your existing standard, unchanged.

## Custom Exception Handler (Consistent Error Format)

```python
# core/exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        logger.error(f'API Error: {exc}', exc_info=True, extra={'context': context})
        custom_response = {
            'detail': response.data.get('detail', str(exc)),
            'code': getattr(exc, 'default_code', 'error'),
        }
        response.data = custom_response

    return response
```

## Response Format (Consistent Across API)

- Success: `{"data": {...}, "message": "optional"}`
- Error: `{"detail": "error message", "code": "ERROR_CODE"}`

All examples in `02-API-Documentation.md` follow this shape.

## Logging Configuration (Production)

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}
```

## Sentry Integration (Recommended for Production)

```bash
pip install sentry-sdk
```

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=env('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    environment='production',
)
```

For this project specifically: also wrap the Celery generation task so a
failed image-generation call reports to Sentry with the `BabyImage.id` as
context — that's where failures will actually happen (bad provider
response, no face detected, network timeout to Replicate).

## Health Check Endpoint (Required for Deploy Scripts)

```python
# core/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection

class HealthCheckView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return Response({'status': 'healthy'}, status=200)
        except Exception as e:
            return Response({'status': 'unhealthy', 'error': str(e)}, status=503)
```

```python
# urls.py
path('api/health/', HealthCheckView.as_view()),
```

## Do Not

- Let default Django error pages leak in production (`DEBUG=False` handles
  this, but verify)
- Log sensitive data (passwords, tokens, OTP codes, full credit card
  numbers)
- Skip the health check endpoint (your CI/CD deploy script needs it)
