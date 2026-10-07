# Demo script and likely questions

About ten minutes, following the order of the course's final-demo checklist.
Everything here runs from the repository and a browser; no AWS account needed.

---

## Before you start

- Open three browser tabs:
  1. the repository: https://github.com/kunalKumar-13/clinicflow
  2. the Actions tab: https://github.com/kunalKumar-13/clinicflow/actions
  3. the package page: https://github.com/kunalKumar-13/clinicflow/pkgs/container/clinicflow-backend
- Have the repository open in your editor.
- Pick a small, visible change for the live commit. The easiest is the app
  version in `docker-compose.yml` and `helm/clinicflow/Chart.yaml` (`appVersion`),
  or a heading in `frontend/src/main.jsx`.

---

## The demo, in order

### 1. The application (1 min)

Show [`docs/screenshots/app-via-ingress.png`](screenshots/app-via-ingress.png),
or the live app if you have Docker on the demo machine (`docker compose up --build`,
then http://localhost:3000).

> "ClinicFlow is an appointment desk for a clinic. Reception books patients in
> with a doctor. The interesting rule is that a doctor can't be double-booked:
> two appointments overlap when each starts before the other ends."

Point at the sidebar: version, commit, where it's running. You will come back to
that commit at the end.

### 2. The API (1 min)

Open `backend/app/main.py`, show `_clashing_appointment`. If the backend is
running, open http://localhost:8000/docs and book the same doctor twice: the
second returns **409 Conflict**.

### 3. The database (30 s)

`backend/alembic/versions/0001_create_appointments.py`: one table, created by a
migration, not by hand. Mention the indexes on `doctor`, `scheduled_at`, `status`,
which are what the list and stats queries filter on.

### 4. Tests (1 min)

```bash
cd backend
pytest -v
```

14 tests. Point out the clash tests and that they run on a throwaway SQLite
database, never the real one.

### 5. Git and the live commit (start it now, it takes ~12 minutes)

Make your small change, then:

```bash
git add -A
git commit -m "Bump version for the demo"
git push
```

Switch to the Actions tab and show the run starting. Carry on while it runs.

### 6. CI pipeline (1 min)

Open `.github/workflows/ci-cd.yml` and walk the jobs: test, terraform, build
(scan, then push), compose, deploy.

> "Tests run first. If they fail, nothing gets built, so a broken image can
> never reach the registry."

### 7. Docker (30 s)

`frontend/Dockerfile`: Node builds the bundle, only the static output goes into
the Nginx image. Both images run as non-root (the Compose job prints `id` from
each container).

### 8. Security scan (1 min)

The Trivy gate. Tell the story from [`SUBMISSION.md`](SUBMISSION.md#m6--devsecops-5):
the gate failed the first run on six HIGH CVEs in the Python dependencies, then
on 42 in the frontend's base image, and both were fixed.

### 9. Registry (30 s)

The package page: every image tagged with a commit SHA. No `latest`.

### 10. Terraform (1 min)

`terraform/main.tf`: VPC, two public and two private subnets across two AZs, NAT,
EKS with a managed node group. Show the "Terraform plan" section on a run's summary
page: 22 resources. Be upfront that it is planned, not applied.

### 11. Kubernetes and Helm (1 min)

On the run summary page: `kubectl get pods` (2 backend, 2 frontend, Postgres, all
Running), `kubectl get svc`, `helm list`.

### 12. Ingress (30 s)

`helm/clinicflow/templates/ingress.yaml`: `/api` to the backend, `/` to the
frontend, one hostname.

### 13. HPA (30 s)

`kubectl get hpa` in the run summary: current CPU against the 70% target, min 2,
max 6 replicas. The CPU figure is low because the demo traffic is light; that
low number is itself the answer to "is the HPA getting metrics?" (without
Metrics Server it would read `<unknown>`).

### 14. Monitoring (1 min)

[`prometheus-targets.png`](screenshots/prometheus-targets.png): both backend pods
are scrape targets, both UP.
[`grafana-dashboard.png`](screenshots/grafana-dashboard.png): request rate, p95
latency, error rate, pods ready, CPU.

### 15. Failure simulation (1 min)

```bash
kubectl apply -f troubleshooting/broken-service.yaml
kubectl get endpoints broken-service -n clinicflow    # empty
kubectl get pods --show-labels -n clinicflow          # the labels don't match
```

If you have no cluster on hand, explain from the file: a Service selects pods by
label, so a selector typo gives a Service with a ClusterIP and zero endpoints.

### Back to the live commit

When the run you started in step 5 finishes, open its summary page. The
"deployed images" line shows the new commit SHA as the image tag, and the
deploy job's screenshot of the app shows the same SHA in the sidebar. That is
the whole point: commit to running container, traceable end to end.

---

## Questions you are likely to get

**Why both `/health` and `/ready`?**
Liveness (`/health`) only asks whether the process is alive, so it never touches
the database. If it did, a short database outage would make Kubernetes restart
every backend pod at once. Readiness (`/ready`) does check the database; a pod
failing it is taken out of the Service but not killed.

**Why tag images with the commit SHA instead of `latest`?**
`latest` moves, so you can't tell what is actually running. A SHA tag maps every
running pod to exactly one commit, which is what makes a rollback or an
investigation possible.

**Why does the Trivy gate ignore unfixed CVEs?**
A vulnerability with no released fix can't be fixed by this project. Failing on
it would block every build until upstream ships a patch, and people would end up
disabling the scanner. Fixable HIGH/CRITICAL findings still fail the build.

**Two backend replicas both run migrations on start. What stops them clashing?**
A Postgres advisory lock in `backend/alembic/env.py`. The first replica takes
the lock and migrates; the second waits, then finds nothing left to do. Before
that, one replica could lose the race and restart. The pipeline now fails if a
backend pod restarts, so that can't silently come back.

**Why is `/api` listed before `/` in the Ingress?**
Both are prefixes and `/` matches everything. Listing the more specific rule
first (and the controller preferring the longest match) is what keeps API calls
from landing on the frontend and getting `index.html` back.

**What does the HPA need to work?**
Resource requests on the pods (set in `values.yaml`) and a metrics source
(Metrics Server). Without either, it shows `<unknown>` and never scales.

**Why `serviceMonitorSelectorNilUsesHelmValues: false`?**
Without it, Prometheus only picks up ServiceMonitors carrying its own Helm
release label, and silently ignores the application's.

**How did you run `terraform plan` without AWS?**
The AWS provider normally calls STS on start-up to check credentials. Creating
new resources doesn't need anything read back from AWS, so with that check
skipped (via a throwaway override with dummy keys) and the availability zones
passed in, the plan completes. Nothing can be applied that way, since the keys
aren't real.

**Why was the p95 latency first showing ~95 ms for everything?**
The default histogram buckets started at 0.1 s. Every request was faster than
that, so `histogram_quantile()` just interpolated 95% of the way through the
first bucket. Buckets now start at 5 ms, and the p95 reflects real latency.

**What would you change for production?**
Use a managed database (RDS) instead of Postgres in the cluster, which
`values-prod.yaml` already switches off; keep Terraform state in S3 with
locking; deploy with Argo CD instead of from the pipeline; and put the Postgres
password in a real secret store instead of `values.yaml`.
