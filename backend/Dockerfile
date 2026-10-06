# ClinicFlow backend image.
#
# Single stage is enough for a Python service: there is no compile step whose
# tooling we need to leave behind. What matters here is that dependencies are
# installed before the source is copied (so code edits do not bust the pip layer)
# and that the container does not run as root.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Take any Debian security patches released since the base image was published,
# then add curl (used by the healthcheck) and libpq (needed by psycopg).
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends curl libpq5 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Non-root user. Created after the copies so the files are owned correctly.
RUN useradd --create-home --uid 10001 clinic \
 && chown -R clinic:clinic /app
USER clinic

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
