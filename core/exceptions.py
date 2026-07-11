import logging
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        logger.error(f'API Error: {exc}', exc_info=True, extra={'context': context})
        data = response.data
        if isinstance(data, dict):
            detail = data.get('detail', str(exc))
        elif isinstance(data, list):
            detail = str(data[0]) if data else str(exc)
        else:
            detail = str(exc)
        custom_response = {
            'detail': detail,
            'code': getattr(exc, 'default_code', 'error'),
        }
        response.data = custom_response

    return response
