"""Application settings, read from the environment.

Everything that differs between a laptop, a Docker Compose stack and a Kubernetes
cluster is injected here rather than hard-coded, which is what makes the same
image runnable in all three places.
"""
import os


class Settings:
    APP_NAME: str = "ClinicFlow API"
    APP_VERSION: str = os.getenv("APP_VERSION", "0.1.0")

    # Baked into the image at build time by CI, so a running pod can say exactly
    # which commit it was built from. "local" when built outside the pipeline.
    GIT_SHA: str = os.getenv("GIT_SHA", "local")
    # Where this instance is running: docker-compose, kind, eks...
    APP_ENV: str = os.getenv("APP_ENV", "local")

    # Postgres in compose and in the cluster; SQLite is used by the test suite so
    # that tests never touch a real database.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://clinicflow:clinicflow@localhost:5432/clinicflow",
    )

    # The clinic's working day. Appointments outside this window are rejected.
    OPENING_HOUR: int = int(os.getenv("OPENING_HOUR", "8"))
    CLOSING_HOUR: int = int(os.getenv("CLOSING_HOUR", "20"))

    # Comma separated list, used by the frontend dev server during local work.
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")


settings = Settings()
