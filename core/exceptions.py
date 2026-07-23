import logging
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def _extract_detail(data, fallback):
    if isinstance(data, dict):
        if 'detail' in data:
            return _extract_detail(data['detail'], fallback)
        if data:
            first_value = next(iter(data.values()))
            return _extract_detail(first_value, fallback)
        return fallback

    if isinstance(data, list):
        if not data:
            return fallback
        return _extract_detail(data[0], fallback)

    text = str(data).strip()
    return text or fallback


def _safe_log_context(context):
    request = context.get('request') if isinstance(context, dict) else None
    view = context.get('view') if isinstance(context, dict) else None
    return {
        'method': getattr(request, 'method', None),
        'path': getattr(request, 'path', None),
        'view': view.__class__.__name__ if view else None,
    }


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        safe_context = _safe_log_context(context)
        if response.status_code >= 500:
            logger.error('API server error: %s', exc, exc_info=True, extra=safe_context)
        else:
            logger.warning('API client error: %s', exc, extra=safe_context)

        detail = _extract_detail(response.data, str(exc))
        custom_response = {
            'detail': detail,
            'message': detail,
            'data': {},
            'code': getattr(exc, 'default_code', 'error'),
        }
        response.data = custom_response

    return response
