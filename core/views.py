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
