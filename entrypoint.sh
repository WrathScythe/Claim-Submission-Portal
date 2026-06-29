#!/bin/bash
# Entrypoint script to initialise the database and start the app
set -e

echo "Waiting for PostgreSQL to be ready..."
until python -c "import psycopg2; psycopg2.connect(host='db', port=5432, user='claimuser', password='claimpass', dbname='claimdb')" 2>/dev/null; do
    echo "PostgreSQL not ready, retrying in 2s..."
    sleep 2
done
echo "PostgreSQL is ready."

echo "Initialising database..."
python -c "from app import app, init_database; app.app_context().push(); init_database()"

echo "Starting application..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
