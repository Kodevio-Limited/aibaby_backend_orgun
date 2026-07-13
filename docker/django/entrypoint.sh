#!/bin/sh

echo "Waiting for PostgreSQL..."

while ! nc -z db 5432; do
    sleep 1
done

echo "Database Ready"

python manage.py migrate

python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers 4 \
      --timeout 120
