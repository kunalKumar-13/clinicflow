#!/usr/bin/env bash
# Generates enough CPU load on the backend to make the HPA scale up.
#
#   kubectl port-forward svc/clinicflow-clinicflow-backend 8000:8000 -n clinicflow &
#   ./scripts/load-test.sh 8000 60
#
# A plain health check is too cheap to move CPU, so this hammers the stats
# endpoint, which actually queries and aggregates.
set -euo pipefail

PORT="${1:-8000}"
SECONDS_TO_RUN="${2:-60}"
CONCURRENCY="${3:-8}"
BASE="http://localhost:${PORT}"

echo "load: ${CONCURRENCY} workers against ${BASE} for ${SECONDS_TO_RUN}s"
echo "watch it scale in another terminal:  kubectl get hpa -n clinicflow -w"

end=$(( $(date +%s) + SECONDS_TO_RUN ))
for _ in $(seq 1 "$CONCURRENCY"); do
  (
    while [ "$(date +%s)" -lt "$end" ]; do
      curl -s -o /dev/null "${BASE}/api/appointments/stats" || true
      curl -s -o /dev/null "${BASE}/api/appointments" || true
    done
  ) &
done
wait
echo "load finished"
