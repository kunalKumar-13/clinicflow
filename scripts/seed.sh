#!/usr/bin/env bash
# Books a realistic day at the clinic through the public API, so the dashboard,
# the metrics and the screenshots all show real data rather than an empty table.
#
#   ./scripts/seed.sh http://localhost:8000                 # straight at the API
#   ./scripts/seed.sh http://localhost clinicflow.local     # through the Ingress
#
# Appointments go in for today (UTC) so the "Today" and "Chair time" cards fill
# up. One deliberate double-booking is included, and the script checks that the
# API rejects it with 409, so the seed doubles as a check of the clash rule.
set -euo pipefail

BASE="${1:-http://localhost:8000}"
HOST_HEADER="${2:-}"
TODAY="$(date -u +%Y-%m-%d)"

# python3 on Linux and macOS; on Windows `python3` is often only the Microsoft
# Store stub, so fall back to `python` if python3 cannot actually run.
PY=python3
"$PY" -c "" >/dev/null 2>&1 || PY=python

curl_api() {
  if [ -n "$HOST_HEADER" ]; then
    curl -sS -H "Host: $HOST_HEADER" -H 'Content-Type: application/json' "$@"
  else
    curl -sS -H 'Content-Type: application/json' "$@"
  fi
}

book() {  # book <name> <phone> <doctor> <department> <HH:MM> <minutes> <reason>
  local body
  body=$(printf '{"patient_name":"%s","patient_phone":"%s","doctor":"%s","department":"%s","scheduled_at":"%sT%s:00","duration_minutes":%s,"reason":"%s"}' \
    "$1" "$2" "$3" "$4" "$TODAY" "$5" "$6" "$7")
  curl_api -o /dev/null -w '%{http_code}' -X POST "$BASE/api/appointments" -d "$body"
}

echo "seeding $BASE for $TODAY"

declare -a ROWS=(
  "Ananya Rao|9876543210|Dr. Mehta|Cardiology|09:00|30|Routine follow-up"
  "Rahul Verma|9812345670|Dr. Mehta|Cardiology|09:30|45|Chest pain review"
  "Priya Nair|9900112233|Dr. Iyer|Dermatology|10:00|20|Skin rash"
  "Arjun Singh|9822334455|Dr. Kapoor|Orthopaedics|10:30|30|Knee pain"
  "Meera Joshi|9811223344|Dr. Iyer|Dermatology|11:00|20|Acne consultation"
  "Kabir Das|9877665544|Dr. Rao|Paediatrics|11:30|30|Vaccination"
  "Sneha Pillai|9833445566|Dr. Kapoor|Orthopaedics|12:00|45|Post-surgery review"
  "Vikram Shah|9844556677|Dr. Mehta|Cardiology|14:00|30|ECG results"
  "Ishita Banerjee|9855667788|Dr. Rao|Paediatrics|14:30|30|Fever"
  "Rohan Gupta|9866778899|Dr. Sen|ENT|15:00|20|Ear infection"
  "Kavya Reddy|9877889900|Dr. Sen|ENT|15:30|20|Sinus follow-up"
  "Aditya Kulkarni|9888990011|Dr. Bose|General Medicine|16:00|30|Annual check-up"
)

ok=0
for row in "${ROWS[@]}"; do
  IFS='|' read -r name phone doctor dept time mins reason <<<"$row"
  code=$(book "$name" "$phone" "$doctor" "$dept" "$time" "$mins" "$reason")
  if [ "$code" = "201" ]; then ok=$((ok+1)); else echo "  unexpected $code for $name"; fi
done
echo "booked $ok of ${#ROWS[@]}"

# The clash rule: Dr. Mehta is already booked 09:00-09:30.
clash=$(book "Double Booked" "9000000000" "Dr. Mehta" "Cardiology" "09:15" "30" "should be rejected")
echo "double-booking Dr. Mehta at 09:15 -> HTTP $clash (expected 409)"
[ "$clash" = "409" ] || { echo "clash rule did not fire" >&2; exit 1; }

# Move a few through their lifecycle so every status shows up on the dashboard.
ids=$(curl_api "$BASE/api/appointments" | "$PY" -c "import json,sys; print(' '.join(str(a['id']) for a in json.load(sys.stdin)))")
set -- $ids
[ $# -ge 4 ] && {
  curl_api -o /dev/null -X PUT "$BASE/api/appointments/$1" -d '{"status":"completed"}'
  curl_api -o /dev/null -X PUT "$BASE/api/appointments/$2" -d '{"status":"completed"}'
  curl_api -o /dev/null -X PUT "$BASE/api/appointments/$3" -d '{"status":"cancelled"}'
  curl_api -o /dev/null -X PUT "$BASE/api/appointments/$4" -d '{"status":"no_show"}'
}

echo "stats:"
curl_api "$BASE/api/appointments/stats"
echo
