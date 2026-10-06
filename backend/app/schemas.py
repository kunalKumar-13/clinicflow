"""Pydantic schemas: the shape of what goes in and what comes out.

Validation lives here so the route handlers stay thin and the API returns a
useful 422 instead of a 500 when a client sends nonsense.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import STATUSES

DEPARTMENTS = (
    "General Medicine",
    "Cardiology",
    "Dermatology",
    "Orthopaedics",
    "Paediatrics",
    "ENT",
)


class AppointmentBase(BaseModel):
    patient_name: str = Field(min_length=2, max_length=120)
    patient_phone: str = Field(min_length=7, max_length=20)
    doctor: str = Field(min_length=2, max_length=120)
    department: str
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=10, le=240)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("department")
    @classmethod
    def known_department(cls, v: str) -> str:
        if v not in DEPARTMENTS:
            raise ValueError("department must be one of: " + ", ".join(DEPARTMENTS))
        return v

    @field_validator("patient_phone")
    @classmethod
    def phone_digits(cls, v: str) -> str:
        cleaned = v.replace(" ", "").replace("-", "").lstrip("+")
        if not cleaned.isdigit():
            raise ValueError("patient_phone must contain digits only")
        return v


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    """Every field optional: this is a partial update."""

    patient_name: str | None = Field(default=None, min_length=2, max_length=120)
    patient_phone: str | None = Field(default=None, min_length=7, max_length=20)
    doctor: str | None = Field(default=None, min_length=2, max_length=120)
    department: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=10, le=240)
    status: str | None = None
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def known_status(cls, v: str | None) -> str | None:
        if v is not None and v not in STATUSES:
            raise ValueError("status must be one of: " + ", ".join(STATUSES))
        return v

    @field_validator("department")
    @classmethod
    def known_department(cls, v: str | None) -> str | None:
        if v is not None and v not in DEPARTMENTS:
            raise ValueError("department must be one of: " + ", ".join(DEPARTMENTS))
        return v


class AppointmentOut(AppointmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
    updated_at: datetime


class StatsOut(BaseModel):
    total: int
    scheduled: int
    completed: int
    cancelled: int
    no_show: int
    today: int
    booked_minutes_today: int
    busiest_doctor: str | None
