"""SQLAlchemy models.

One table, `appointments`. The columns are deliberately plain types so the same
model works on Postgres in the cluster and on SQLite in the test suite.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

STATUSES = ("scheduled", "completed", "cancelled", "no_show")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    patient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    doctor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(60), nullable=False)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    @property
    def ends_at(self) -> datetime:
        from datetime import timedelta

        return self.scheduled_at + timedelta(minutes=self.duration_minutes)
