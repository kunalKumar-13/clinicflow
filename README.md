# ClinicFlow

An appointment desk for a multi-department clinic. Reception staff book patients
in with a doctor, the system refuses to double-book that doctor or to put a
patient outside clinic hours, and the dashboard shows the day at a glance:
how many patients are booked, how much chair time that adds up to, and who the
busiest doctor is.

It is built as the final DevOps capstone: the application itself is small on
purpose, and the work is in taking it from a laptop to a monitored Kubernetes
cluster through a tested, scanned, automated pipeline.

**Kunal Kumar · Roll No. 24BCS10027**

---

## What it does

| | |
|---|---|
| **Book** | patient, phone, doctor, department, date/time, duration, reason |
| **Prevent clashes** | a doctor cannot have two overlapping appointments; a cancelled one frees its slot |
| **Enforce hours** | appointments must start and end between 08:00 and 20:00 on one day |
| **Track status** | scheduled, completed, cancelled, no-show |
| **Dashboard** | today's bookings, chair time, counts by status, busiest doctor, search and filters |
| **Build info** | the sidebar shows the version, commit and environment serving the page, so a new deployment is visible in the app itself |

The clash rule is the part worth looking at. Two appointments overlap when each
starts before the other ends, so the check is
`existing.start < new.end AND new.start < existing.end`, limited to the same
doctor on the same day and ignoring cancelled bookings. It lives in
[`backend/app/main.py`](backend/app/main.py) and is covered by three tests.

---

## Architecture

```
  Browser
     |
     v
  Ingress (nginx)  ── /api ──>  FastAPI backend  ──>  PostgreSQL
     |                              |
     └── /  ──> React frontend      └── /metrics ──> Prometheus ──> Grafana
               (served by Nginx)
```

```
git push
   └── GitHub Actions
         ├── test       pytest (14 tests), ruff, Alembic migration check, frontend build
         ├── terraform  fmt, init, validate
         ├── build      docker build -> Trivy scan -> push to GHCR, tagged with the commit SHA
         └── deploy     kind cluster -> ingress-nginx + metrics-server -> helm upgrade --install
                        -> kubectl get pods/svc -> smoke test through the Ingress
```

| Layer | Tool |
|---|---|
| Frontend | React 18 + Vite, served by Nginx |
| Backend | FastAPI, SQLAlchemy 2, Pydantic 2 |
| Database | PostgreSQL 16, schema managed by Alembic |
| Tests | pytest + FastAPI TestClient on an isolated SQLite database |
| Containers | Docker, multi-stage frontend build, both images run as non-root |
| CI/CD | GitHub Actions, images in GitHub Container Registry |
| Security | Trivy image scanning |
| Infrastructure | Terraform: AWS VPC (2 public + 2 private subnets) and EKS |
| Orchestration | Kubernetes, packaged as a Helm chart, Ingress, HPA |
| Observability | Prometheus (`/metrics`), Grafana dashboard |

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | liveness: the process is up (does not touch the database) |
| `GET` | `/ready` | readiness: checks the database connection |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/appointments` | list, with `?status=`, `?doctor=`, `?on=YYYY-MM-DD` filters |
| `GET` | `/api/appointments/{id}` | one appointment |
| `POST` | `/api/appointments` | book (409 on a clash, 422 outside hours) |
| `PUT` | `/api/appointments/{id}` | partial update, re-checks clashes if the time or doctor changes |
| `DELETE` | `/api/appointments/{id}` | remove |
| `GET` | `/api/appointments/stats` | dashboard counts |
| `GET` | `/api/meta` | which build is answering: version, commit SHA, environment |

Interactive docs at `/docs` once the backend is running.

Why both `/health` and `/ready`: if liveness checked the database, a short
database outage would make Kubernetes restart every healthy backend pod at once.
So liveness only asks "is the process alive", and readiness asks "can it serve
right now" — a pod that fails readiness is taken out of the Service without
being killed.

---

## Run it

### Everything, with Docker

```bash
docker compose up --build
```

- App: http://localhost:3000
- API docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics

The backend waits for Postgres to pass its healthcheck and then applies the
migration before starting, so the first `up` works without any manual steps.

### Backend only

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL='postgresql+psycopg://clinicflow:clinicflow@localhost:5432/clinicflow'
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend only

```bash
cd frontend
npm install
npm run dev                         # http://localhost:5173, /api proxied to :8000
```

---

## Tests

```bash
cd backend
pytest
```

14 tests, hitting ten of the API's eleven routes (everything except the root info
page). They run against a throwaway SQLite file created in
the temp directory, never the real database, and the schema is dropped and
recreated around every test so no test can leak state into another.

What they cover: health, readiness and metrics; creating an appointment; the
clash rule (same doctor rejected, different doctor allowed, cancelled slot
reusable); the working-hours rule; validation of unknown departments; listing
and filtering; 404 on a missing record; update; delete; and the stats counts.

---

## CI/CD

[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) runs on every push
and pull request to `main`.

1. **test** — ruff, pytest, an Alembic `upgrade head` against a scratch database,
   and a production build of the frontend. If any of this fails, nothing is built.
2. **terraform** — `fmt -check`, `init -backend=false`, `validate`.
3. **build** — builds both images, scans them with Trivy, and only then pushes
   them to GHCR as `clinicflow-backend:<sha>` and `clinicflow-frontend:<sha>`.
   Tagging with the commit SHA rather than `latest` means every running pod can
   be traced back to the exact commit it was built from.
4. **deploy** — creates a two-node kind cluster, installs ingress-nginx and
   Metrics Server, side-loads the images that were just pushed, runs
   `helm upgrade --install`, prints the pods, services, ingress and Helm release,
   then smoke-tests the API through the Ingress and checks `/metrics`.

### Security scanning

Each image is scanned twice. The first pass prints the full Trivy report and
never fails, so the log always shows what was found. The second pass is the
gate: it fails the pipeline on any **HIGH or CRITICAL vulnerability that has a
fix available**, and nothing is pushed if it fails.

`ignore-unfixed` is a deliberate choice. A CVE in a base-image package with no
released patch cannot be fixed by this project, and a gate that fails on things
nobody can act on just teaches people to switch the gate off.

---

## Kubernetes and Helm

```bash
kubectl apply -f k8s/namespace.yaml
helm upgrade --install clinicflow ./helm/clinicflow \
  -n clinicflow -f helm/clinicflow/values-dev.yaml

kubectl get pods -n clinicflow
kubectl get svc  -n clinicflow
helm list -n clinicflow
```

The chart ([`helm/clinicflow`](helm/clinicflow)) deploys:

- backend and frontend Deployments, 2 replicas each, both running as non-root
- ClusterIP Services for both
- an Ingress routing `/api` to the backend and `/` to the frontend
- an HPA scaling the backend from 2 to 6 replicas at 70% CPU
- PostgreSQL with a PersistentVolumeClaim (demo only; `values-prod.yaml` turns it
  off in favour of a managed database)
- a ServiceMonitor for Prometheus, enabled in `values-prod.yaml`

Liveness, readiness and startup probes are all set; the startup probe gives the
migration time to finish on a cold start before liveness begins counting.

To see the HPA react, generate load and watch it:

```bash
kubectl port-forward svc/clinicflow-clinicflow-backend 8000:8000 -n clinicflow &
./scripts/load-test.sh 8000 90
kubectl get hpa -n clinicflow -w
```

### Troubleshooting exercises

[`troubleshooting/`](troubleshooting) has two manifests that are broken on purpose:

- `broken-image.yaml` — a tag that does not exist, giving `ImagePullBackOff`.
  There are no container logs because the container never starts, so the
  evidence is only in `kubectl describe pod`.
- `broken-service.yaml` — a Service whose selector does not match its pods. It
  gets a ClusterIP and looks healthy, but `kubectl get endpoints` is empty.

---

## Terraform

[`terraform/`](terraform) describes the AWS side: a VPC in `ap-south-1` with two
public and two private subnets across two availability zones, an internet
gateway, a NAT gateway, and an EKS cluster with a managed node group in the
private subnets. Public subnets carry the `kubernetes.io/role/elb` tag so AWS
load balancers know where they may be placed.

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
aws eks update-kubeconfig --region ap-south-1 --name clinicflow-dev
terraform destroy
```

Nodes default to `t3.medium` SPOT instances to keep a demo cluster cheap. No
credentials are stored in the repository: state files and real `tfvars` are
ignored, and AWS access comes from `aws configure` or environment variables.

The pipeline validates this code on every push. It is not applied automatically,
because an EKS cluster costs money while it runs.

---

## Monitoring

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f monitoring/prometheus-values.yaml

helm upgrade --install clinicflow ./helm/clinicflow -n clinicflow \
  --set serviceMonitor.enabled=true

kubectl port-forward svc/monitoring-grafana 3001:80 -n monitoring
```

[`monitoring/grafana-dashboard.json`](monitoring/grafana-dashboard.json) has
panels for request rate by endpoint, p95 latency, 5xx rate, ready backend pods,
and backend CPU (the input the HPA scales on).

One setting matters more than it looks:
`serviceMonitorSelectorNilUsesHelmValues: false`. Without it, Prometheus only
picks up ServiceMonitors that carry its own release label and silently ignores
the application's.

---

## Repository layout

```
.
├── backend/              FastAPI app, Alembic migrations, tests, Dockerfile
├── frontend/             React app, Nginx config, multi-stage Dockerfile
├── docker-compose.yml    full local stack
├── helm/clinicflow/      Helm chart (dev and prod values)
├── k8s/                  namespace and cluster bootstrap manifests
├── terraform/            AWS VPC + EKS
├── monitoring/           Prometheus values, Grafana dashboard
├── troubleshooting/      deliberately broken manifests
├── scripts/              load generator for the HPA demo
└── .github/workflows/    CI/CD pipeline
```
