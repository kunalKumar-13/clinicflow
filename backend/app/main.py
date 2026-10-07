"""ClinicFlow API.

A small appointment-booking service for a clinic. The interesting part is not the
CRUD, it is the booking rule: a doctor cannot be double-booked, and appointments
must fall inside the clinic's working hours. That rule is what the test suite and
the frontend both exercise.
"""
from datetime import date, datetime, time, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import STATUSES, Appointment
from app.schemas import AppointmentCreate, AppointmentOut, AppointmentUpdate, StatsOut

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Appointment booking for a multi-department clinic.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exposes /metrics in the Prometheus text format for the ServiceMonitor to scrape.
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# --------------------------------------------------------------------------- #
#  Booking rules
# --------------------------------------------------------------------------- #

def _within_working_hours(start: datetime, duration: int) -> bool:
    end = start + timedelta(minutes=duration)
    opens = time(hour=settings.OPENING_HOUR)
    closes = time(hour=settings.CLOSING_HOUR)
    if start.time() < opens or end.time() > closes:
        return False
    return start.date() == end.date()


def _clashing_appointment(
    db: Session, doctor: str, start: datetime, duration: int, exclude_id: int | None = None
) -> Appointment | None:
    """Return an existing appointment that overlaps this slot for the same doctor.

    Two intervals overlap when each starts before the other ends. Cancelled
    appointments free their slot, so they are excluded.
    """
    end = start + timedelta(minutes=duration)
    day_start = datetime.combine(start.date(), time.min)
    day_end = day_start + timedelta(days=1)

    stmt = select(Appointment).where(
        Appointment.doctor == doctor,
        Appointment.status != "cancelled",
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at < day_end,
    )
    if exclude_id is not None:
        stmt = stmt.where(Appointment.id != exclude_id)

    for existing in db.scalars(stmt):
        if existing.scheduled_at < end and start < existing.ends_at:
            return existing
    return None


# --------------------------------------------------------------------------- #
#  Service endpoints
# --------------------------------------------------------------------------- #

@app.get("/", tags=["service"])
def root() -> dict:
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["service"])
def health() -> dict:
    """Liveness: the process is up. Deliberately does not touch the database."""
    return {"status": "ok", "version": settings.APP_VERSION, "commit": settings.GIT_SHA}


@app.get("/api/meta", tags=["service"])
def meta() -> dict:
    """Which build is answering. Under /api so it is reachable through the
    Ingress; the UI shows it, so a new deployment is visible in the app itself."""
    return {
        "version": settings.APP_VERSION,
        "commit": settings.GIT_SHA,
        "environment": settings.APP_ENV,
    }


@app.get("/ready", tags=["service"])
def ready(db: Session = Depends(get_db)) -> dict:
    """Readiness: can this instance actually serve traffic? Checks the database."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - only hit when the DB is down
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"database unavailable: {exc.__class__.__name__}",
        ) from exc
    return {"status": "ready", "database": "connected"}


# --------------------------------------------------------------------------- #
#  Appointments
# --------------------------------------------------------------------------- #

@app.get("/api/appointments", response_model=list[AppointmentOut], tags=["appointments"])
def list_appointments(
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    doctor: str | None = None,
    on: date | None = Query(default=None, description="Filter to a single day"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Appointment]:
    stmt = select(Appointment)

    if status_filter:
        if status_filter not in STATUSES:
            raise HTTPException(400, f"unknown status '{status_filter}'")
        stmt = stmt.where(Appointment.status == status_filter)
    if doctor:
        stmt = stmt.where(Appointment.doctor == doctor)
    if on:
        day_start = datetime.combine(on, time.min)
        stmt = stmt.where(
            Appointment.scheduled_at >= day_start,
            Appointment.scheduled_at < day_start + timedelta(days=1),
        )

    stmt = stmt.order_by(Appointment.scheduled_at).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@app.get("/api/appointments/stats", response_model=StatsOut, tags=["appointments"])
def appointment_stats(db: Session = Depends(get_db)) -> StatsOut:
    """Counts for the dashboard cards. Declared before /{id} so the literal path wins."""
    counts = dict(
        db.execute(
            select(Appointment.status, func.count(Appointment.id)).group_by(Appointment.status)
        ).all()
    )

    day_start = datetime.combine(date.today(), time.min)
    day_end = day_start + timedelta(days=1)
    today_rows = list(
        db.scalars(
            select(Appointment).where(
                Appointment.scheduled_at >= day_start,
                Appointment.scheduled_at < day_end,
                Appointment.status != "cancelled",
            )
        )
    )

    busiest = db.execute(
        select(Appointment.doctor, func.count(Appointment.id))
        .where(Appointment.status != "cancelled")
        .group_by(Appointment.doctor)
        .order_by(func.count(Appointment.id).desc())
        .limit(1)
    ).first()

    return StatsOut(
        total=sum(counts.values()),
        scheduled=counts.get("scheduled", 0),
        completed=counts.get("completed", 0),
        cancelled=counts.get("cancelled", 0),
        no_show=counts.get("no_show", 0),
        today=len(today_rows),
        booked_minutes_today=sum(a.duration_minutes for a in today_rows),
        busiest_doctor=busiest[0] if busiest else None,
    )


@app.get("/api/appointments/{appointment_id}", response_model=AppointmentOut, tags=["appointments"])
def get_appointment(appointment_id: int, db: Session = Depends(get_db)) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(404, f"appointment {appointment_id} not found")
    return appointment


@app.post(
    "/api/appointments",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    tags=["appointments"],
)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)) -> Appointment:
    if not _within_working_hours(payload.scheduled_at, payload.duration_minutes):
        raise HTTPException(
            422,
            f"appointment must fall between {settings.OPENING_HOUR:02d}:00 and "
            f"{settings.CLOSING_HOUR:02d}:00 on a single day",
        )

    clash = _clashing_appointment(
        db, payload.doctor, payload.scheduled_at, payload.duration_minutes
    )
    if clash is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{payload.doctor} is already booked at "
            f"{clash.scheduled_at:%Y-%m-%d %H:%M} (appointment {clash.id})",
        )

    appointment = Appointment(**payload.model_dump())
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@app.put("/api/appointments/{appointment_id}", response_model=AppointmentOut, tags=["appointments"])
def update_appointment(
    appointment_id: int, payload: AppointmentUpdate, db: Session = Depends(get_db)
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(404, f"appointment {appointment_id} not found")

    changes = payload.model_dump(exclude_unset=True)

    new_start = changes.get("scheduled_at", appointment.scheduled_at)
    new_duration = changes.get("duration_minutes", appointment.duration_minutes)
    new_doctor = changes.get("doctor", appointment.doctor)

    if {"scheduled_at", "duration_minutes", "doctor"} & changes.keys():
        if not _within_working_hours(new_start, new_duration):
            raise HTTPException(
                422,
                f"appointment must fall between {settings.OPENING_HOUR:02d}:00 and "
                f"{settings.CLOSING_HOUR:02d}:00 on a single day",
            )
        clash = _clashing_appointment(
            db, new_doctor, new_start, new_duration, exclude_id=appointment_id
        )
        if clash is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{new_doctor} is already booked at {clash.scheduled_at:%Y-%m-%d %H:%M}",
            )

    for field, value in changes.items():
        setattr(appointment, field, value)

    db.commit()
    db.refresh(appointment)
    return appointment


@app.delete(
    "/api/appointments/{appointment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["appointments"],
)
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)) -> Response:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(404, f"appointment {appointment_id} not found")
    db.delete(appointment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
