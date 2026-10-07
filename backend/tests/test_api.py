"""API tests for ClinicFlow.

Covers the service endpoints and the full appointment lifecycle, including the two
rules that make this more than a CRUD wrapper: a doctor cannot be double-booked,
and appointments must sit inside the clinic's working hours.
"""


# --------------------------------------------------------------------------- #
#  Service endpoints
# --------------------------------------------------------------------------- #

def test_health_reports_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_checks_the_database(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_meta_reports_the_build_serving_the_request(client):
    response = client.get("/api/meta")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"version", "commit", "environment"}
    assert body["commit"]  # never empty: "local" outside CI, the SHA inside it


def test_metrics_endpoint_is_prometheus_formatted(client):
    client.get("/health")  # generate at least one request to count
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


# --------------------------------------------------------------------------- #
#  Creating appointments
# --------------------------------------------------------------------------- #

def test_create_appointment_returns_201_and_the_record(client, booking):
    response = client.post("/api/appointments", json=booking)
    assert response.status_code == 201

    body = response.json()
    assert body["id"] > 0
    assert body["patient_name"] == "Ananya Rao"
    assert body["status"] == "scheduled"
    assert body["doctor"] == "Dr. Mehta"


def test_double_booking_the_same_doctor_is_rejected(client, booking):
    assert client.post("/api/appointments", json=booking).status_code == 201

    # same doctor, overlapping by 15 minutes
    overlapping = {**booking, "patient_name": "Rahul Verma", "scheduled_at": "2027-03-15T10:15:00"}
    response = client.post("/api/appointments", json=overlapping)

    assert response.status_code == 409
    assert "already booked" in response.json()["detail"]


def test_a_different_doctor_may_take_the_same_slot(client, booking):
    assert client.post("/api/appointments", json=booking).status_code == 201

    other_doctor = {**booking, "doctor": "Dr. Iyer", "patient_name": "Rahul Verma"}
    assert client.post("/api/appointments", json=other_doctor).status_code == 201


def test_appointment_outside_working_hours_is_rejected(client, booking):
    after_hours = {**booking, "scheduled_at": "2027-03-15T22:00:00"}
    response = client.post("/api/appointments", json=after_hours)

    assert response.status_code == 422
    assert "08:00" in response.json()["detail"]


def test_unknown_department_fails_validation(client, booking):
    response = client.post("/api/appointments", json={**booking, "department": "Astrology"})
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
#  Reading, updating, deleting
# --------------------------------------------------------------------------- #

def test_list_returns_created_appointments_and_filters_by_status(client, booking):
    client.post("/api/appointments", json=booking)
    client.post(
        "/api/appointments",
        json={**booking, "doctor": "Dr. Iyer", "scheduled_at": "2027-03-15T11:00:00"},
    )

    assert len(client.get("/api/appointments").json()) == 2
    assert len(client.get("/api/appointments?status=completed").json()) == 0
    assert len(client.get("/api/appointments?doctor=Dr.%20Iyer").json()) == 1


def test_get_by_id_returns_404_for_a_missing_appointment(client):
    response = client.get("/api/appointments/4242")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_update_changes_status_and_frees_the_slot(client, booking):
    created = client.post("/api/appointments", json=booking).json()

    updated = client.put(f"/api/appointments/{created['id']}", json={"status": "cancelled"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "cancelled"

    # a cancelled appointment no longer blocks the slot
    replacement = {**booking, "patient_name": "Rahul Verma"}
    assert client.post("/api/appointments", json=replacement).status_code == 201


def test_delete_removes_the_appointment(client, booking):
    created = client.post("/api/appointments", json=booking).json()

    assert client.delete(f"/api/appointments/{created['id']}").status_code == 204
    assert client.get(f"/api/appointments/{created['id']}").status_code == 404


# --------------------------------------------------------------------------- #
#  Dashboard statistics
# --------------------------------------------------------------------------- #

def test_stats_counts_by_status(client, booking):
    client.post("/api/appointments", json=booking)
    second = client.post(
        "/api/appointments",
        json={**booking, "doctor": "Dr. Iyer", "scheduled_at": "2027-03-15T12:00:00"},
    ).json()
    client.put(f"/api/appointments/{second['id']}", json={"status": "completed"})

    stats = client.get("/api/appointments/stats").json()

    assert stats["total"] == 2
    assert stats["scheduled"] == 1
    assert stats["completed"] == 1
    assert stats["busiest_doctor"] in ("Dr. Mehta", "Dr. Iyer")
