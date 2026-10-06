"""Test fixtures.

The suite runs against a throwaway SQLite file, never the Postgres the app uses in
Docker or in the cluster. DATABASE_URL is set before the app package is imported,
because the engine is created at import time.
"""
import os
import tempfile
from pathlib import Path

import pytest

TEST_DB = Path(tempfile.gettempdir()) / "clinicflow_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    """Every test starts from an empty schema, so tests cannot leak into each other."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def booking() -> dict:
    """A valid appointment payload, at a fixed future date to keep tests deterministic."""
    return {
        "patient_name": "Ananya Rao",
        "patient_phone": "9876543210",
        "doctor": "Dr. Mehta",
        "department": "Cardiology",
        "scheduled_at": "2027-03-15T10:00:00",
        "duration_minutes": 30,
        "reason": "Routine follow-up",
    }
