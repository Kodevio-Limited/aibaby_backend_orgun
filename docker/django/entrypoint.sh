#!/bin/sh

set -e

if [ "$1" = "gunicorn" ]; then

    echo "Waiting for PostgreSQL..."

    while ! nc -z db 5432; do
        sleep 1
    done

    echo "Database Ready"

    mkdir -p logs

    python manage.py migrate

    python manage.py collectstatic --noinput

fi

exec "$@"
