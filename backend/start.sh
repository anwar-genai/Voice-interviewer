#!/bin/sh
set -e
python -m alembic upgrade head
exec uvicorn uvicorn_app:app --host 0.0.0.0 --port 8000
