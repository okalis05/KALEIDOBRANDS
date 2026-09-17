#!/usr/bin/env bash
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Loading finalized HPG production catalog..."
python manage.py load_hpg_production_catalog

echo "Collecting static files..."
python manage.py collectstatic --noinput
