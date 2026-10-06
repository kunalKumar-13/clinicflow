#!/bin/sh
# Apply database migrations, then hand over to the process given as CMD.
#
# Running migrations here (rather than in a separate Job) keeps the local compose
# story simple. In the Helm chart the same image is used, and the migration is
# idempotent, so a rolling update re-runs it harmlessly.
set -e

echo "[entrypoint] waiting for the database..."
for i in $(seq 1 30); do
  if python -c "
import sys
from sqlalchemy import create_engine, text
from app.config import settings
try:
    create_engine(settings.DATABASE_URL).connect().execute(text('SELECT 1'))
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    echo "[entrypoint] database is up"
    break
  fi
  if [ "$i" = "30" ]; then
    echo "[entrypoint] database did not become ready in time" >&2
    exit 1
  fi
  sleep 2
done

echo "[entrypoint] running migrations"
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
