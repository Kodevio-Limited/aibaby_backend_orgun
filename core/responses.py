from rest_framework.response import Response


def success_response(data=None, message=None, code='SUCCESS', status=200):
    payload = {'data': data if data is not None else {}, 'code': code}
    if message is not None:
        payload['message'] = message
    return Response(payload, status=status)


def error_response(detail, code='error', status=400, message=None):
    resolved_message = message if message is not None else detail
    payload = {'detail': detail, 'message': resolved_message, 'data': {}, 'code': code}
    return Response(payload, status=status)