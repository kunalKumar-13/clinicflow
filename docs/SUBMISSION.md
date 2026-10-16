# Capstone submission evidence

Where each item in the grading rubric is satisfied, and where to see it.
Screenshots in [`docs/screenshots/`](screenshots/) were captured automatically
by the pipeline (headless Chromium against the running system) or of public
GitHub pages. The terminal screenshots (`pytest -v`, `docker compose`, Trivy,
`terraform plan`, `kubectl`, `helm list`, `curl /metrics`, troubleshooting) are
the job output of that run, rendered as images; lines are copied as they are,
and the few cuts (image build output, Trivy's per-package table) are marked. Text output from the same pipeline run (test results, Terraform
plan, cluster state) is committed in [`docs/evidence/`](evidence/). None of it
is mocked up.

The pipeline also writes these results to each run's summary page. GitHub only
shows job summaries and logs to signed-in users, which is why the same output is
committed here as well.

**Repository:** https://github.com/kunalKumar-13/clinicflow
**Green pipeline run:** https://github.com/kunalKumar-13/clinicflow/actions/runs/38914556570 (every screenshot and evidence file below is from this run)
**Container images:** [clinicflow-backend](https://github.com/kunalKumar-13/clinicflow/pkgs/container/clinicflow-backend) · [clinicflow-frontend](https://github.com/kunalKumar-13/clinicflow/pkgs/container/clinicflow-frontend)

---

## M1 — Application (10)

| Criterion | Evidence |
|---|---|
| FastAPI responds to `/health` | [`backend/app/main.py`](../backend/app/main.py); checked inside the pod by the deploy job |
| 4+ REST endpoints (GET, POST, PUT, DELETE) | list, get, create, update, delete, stats and meta under `/api`, plus `/health`, `/ready` and `/metrics` |
| PostgreSQL table managed by Alembic | [`backend/alembic/versions/0001_create_appointments.py`](../backend/alembic/versions/0001_create_appointments.py); the pipeline runs `alembic upgrade head` on every push |
| Frontend renders and calls the API | [`frontend/src/main.jsx`](../frontend/src/main.jsx) |
| Responsive, usable UI | desktop: ![app](screenshots/app-docker-compose.png) phone width (390px): ![mobile](screenshots/app-mobile.png) |

## M2 — Testing (10)

| Criterion | Evidence |
|---|---|
| `pytest` runs without errors | ![pytest -v](screenshots/pytest-v.png) 14 passed; full output in [`evidence/pytest-output.txt`](evidence/pytest-output.txt); locally `cd backend && pytest -v` |
| 5+ tests over 3+ endpoints | 14 tests over 10 routes in [`backend/tests/test_api.py`](../backend/tests/test_api.py) |
| Test database, not production | [`backend/tests/conftest.py`](../backend/tests/conftest.py): a throwaway SQLite file, schema rebuilt around every test |
| `pytest.ini` / `conftest.py` | [`backend/pytest.ini`](../backend/pytest.ini), [`backend/tests/conftest.py`](../backend/tests/conftest.py) |

## M3 — Git and GitHub (5)

| Criterion | Evidence |
|---|---|
| Public repository | https://github.com/kunalKumar-13/clinicflow |
| Meaningful commit messages, 10+ commits | ![commits](screenshots/commit-history.png) |
| `.gitignore` excludes `.env`, `__pycache__`, `node_modules`, `.venv` | [`.gitignore`](../.gitignore) |

## M4 — Docker (10)

| Criterion | Evidence |
|---|---|
| `backend/Dockerfile` builds | built on every push by the "Build, scan and push" job |
| Frontend multi-stage (Node build, Nginx runtime) | [`frontend/Dockerfile`](../frontend/Dockerfile) |
| Images run as non-root | backend uid 10001, frontend uid 101; the Compose job prints `id` from both containers |
| `docker compose up --build` starts all three | ![docker compose up](screenshots/docker-compose-up.png) [`evidence/compose-ps.txt`](evidence/compose-ps.txt): postgres, backend and frontend up, from the pipeline's Compose job; the desktop screenshot above is `localhost:3000` from that stack (its sidebar says `docker-compose`) |

## M5 — CI/CD (15)

| Criterion | Evidence |
|---|---|
| Workflow in `.github/workflows/` | [`ci-cd.yml`](../.github/workflows/ci-cd.yml); a green run: ![run](screenshots/pipeline-run.png) |
| Triggers on push to `main` | `on: push: branches: [main]` |
| `pytest` runs and fails the build on failure | "Tests and lint" job; `set -o pipefail` so a failing test cannot be masked |
| Frontend built in the pipeline | "Build the frontend" step |
| Docker images for both | "Build backend image", "Build frontend image" |
| Pushed to GHCR | ![ghcr](screenshots/ghcr-backend.png) |
| Tags use the commit SHA | every image is tagged with the first 12 characters of the commit SHA; `main` is a moving tag alongside, never `latest` |

## M6 — DevSecOps (5)

| Criterion | Evidence |
|---|---|
| Trivy scans both images in CI | "Trivy report" and "Trivy gate" steps for backend and frontend |
| Fails on HIGH or CRITICAL | gate uses `severity: HIGH,CRITICAL`, `exit-code: 1`; images are pushed only after it passes |
| Scan output from a run | ![trivy](screenshots/trivy-scan.png) |
| Explaining a finding | below |

**What Trivy scanned and what it found.** Trivy scans each built image for known
vulnerabilities in two layers: the operating-system packages of the base image
(Debian for the backend, Alpine for the frontend) and the application's own
dependencies (the Python packages in the backend).

The gate failed the very first time it ran, on the backend, with six HIGH
findings in the Python dependencies. One example is **CVE-2025-62727 in
Starlette 0.41.3**: a denial of service in how Starlette's `FileResponse` merges
the byte ranges of an HTTP `Range` header, where a crafted header with many
overlapping ranges makes the server do quadratic work on a single request.
Starlette is the web framework under FastAPI. In this particular API the
practical exposure was low, because it never serves files, but the gate
deliberately blocks fixable HIGH findings without trying to judge reachability
case by case: that judgement is easy to get wrong, and the upgrade was cheap.
The fix was FastAPI 0.142.2 with Starlette 1.7.0. In the same run,
python-multipart 0.0.20 was flagged three times (including CVE-2026-24486); the
app never parses form data, so it was removed rather than upgraded.

The next run failed on the frontend instead: 42 fixable HIGH/CRITICAL findings
in the Alpine base image's OpenSSL, expat, libpng and c-ares, nothing in the app
itself. Moving to the nginx 1.30 stable base and adding an `apk upgrade` at
build time cleared them. Both images now pass the gate. It ignores
vulnerabilities with no released fix, because a gate that fails on things
nobody can patch only teaches people to turn it off.

## M7 — Terraform (15)

| Criterion | Evidence |
|---|---|
| Valid HCL in `terraform/` | [`terraform/`](../terraform); `fmt -check` and `validate` pass on every push |
| `terraform init` | "Init" step |
| `terraform plan` non-empty, no errors | ![terraform plan](screenshots/terraform-plan.png) [`evidence/terraform-plan.txt`](evidence/terraform-plan.txt): **22 to add** (VPC, 2 public + 2 private subnets, IGW, NAT, route tables, IAM roles, EKS cluster, node group); the plan line is also a public annotation on the run page |
| VPC with 2+ public subnets | `aws_subnet.public` (count 2) in [`main.tf`](../terraform/main.tf) |
| EKS with a node group | `aws_eks_cluster.this`, `aws_eks_node_group.this` |
| `terraform destroy` | not run: see below |
| `terraform.tfvars.example`, no credentials | [`terraform.tfvars.example`](../terraform/terraform.tfvars.example); state and real tfvars are git-ignored |

The plan runs in CI **without an AWS account**: the AWS provider's start-up
credential check is skipped through a throwaway override file with dummy keys,
and the availability zones are passed in so no AWS lookup is needed. Creating
new resources does not require reading anything back from AWS, so the plan is
complete. It was **not applied**, so there is no AWS console screenshot and no
`destroy` output; applying needs a real AWS account and costs money while the
cluster runs.

## M8 — Kubernetes and Helm (15)

| Criterion | Evidence |
|---|---|
| `k8s/namespace.yaml` | [`k8s/namespace.yaml`](../k8s/namespace.yaml), applied by the deploy job |
| Helm chart with `Chart.yaml`, `values.yaml`, templates | [`helm/clinicflow/`](../helm/clinicflow) |
| `helm upgrade --install` succeeds | ![helm list](screenshots/helm-list.png) |
| Backend and frontend at 2+ replicas, ClusterIP Services, Ingress, HPA | ![kubectl get pods, svc, ingress, hpa](screenshots/kubectl-get-pods-svc.png) full text in [`evidence/cluster-state.txt`](evidence/cluster-state.txt) |
| Ingress: `/` to frontend, `/api` to backend | [`templates/ingress.yaml`](../helm/clinicflow/templates/ingress.yaml) |
| All pods Running | [`evidence/cluster-state.txt`](evidence/cluster-state.txt); the deploy job also fails if any backend pod restarts |
| App through the Ingress | ![ingress](screenshots/app-via-ingress.png) |

The cluster is a two-node kind cluster created inside the pipeline, not EKS.

## M9 — Observability (10)

| Criterion | Evidence |
|---|---|
| `/metrics` in Prometheus format | ![curl /metrics](screenshots/curl-metrics.png) |
| Prometheus scraping the app | ![targets](screenshots/prometheus-targets.png) |
| Grafana installed and accessible | kube-prometheus-stack release and the Grafana pod in [`evidence/cluster-state.txt`](evidence/cluster-state.txt) |
| A panel with live application metrics | ![grafana](screenshots/grafana-dashboard.png) |

## Troubleshooting

[`troubleshooting/`](../troubleshooting) has two manifests that are broken on
purpose. The deploy job applies each one to the running cluster, diagnoses it
with the same commands you would use by hand, fixes it, and checks the fix
worked. The step fails if any of those checks fail. Transcript:
[`evidence/troubleshooting.txt`](evidence/troubleshooting.txt).

| Fault | What you see | How it was found | Fix | Proof it worked |
|---|---|---|---|---|
| Image tag that does not exist | `ErrImagePull` / `ImagePullBackOff`, no logs | `kubectl describe pod`, Events: `...:does-not-exist: not found` | point the Deployment at the tag the working backend runs | rollout completes, pod `Running` |
| Service selector does not match the pods | Service has a ClusterIP but `ENDPOINTS <none>` | `kubectl get pods --show-labels` vs `kubectl describe svc`: `app=clinic-api` vs `app=clinic-api-v2` | patch the selector | an endpoint appears, `curl http://broken-service` returns `HTTP 200` |

![broken image](screenshots/troubleshooting-broken-image.png)
![broken service](screenshots/troubleshooting-broken-service.png)

## No secrets in the repository

No AWS keys or other credentials are committed: Terraform state and real
`terraform.tfvars` are git-ignored, and the CI plan uses obvious placeholder keys
(`plan-only-not-a-real-key`) that AWS would reject. The pipeline creates a random Grafana admin password and
a random Postgres password for every run, masks them in the logs, and passes them
at install time; the Helm chart refuses to install without `postgres.password`.

A [gitleaks](https://github.com/gitleaks/gitleaks) scan of the full history
(`gitleaks git .`) reports no leaks. One early commit (`0714c86`) had the
password of the CI-only demo Grafana inline in a `curl` command; it is fixed and
the finding is listed in [`.gitleaksignore`](../.gitleaksignore) with the reason.
The Docker Compose file keeps local development credentials for the database on
`localhost`, as is usual for a laptop-only stack.

## M10 — Documentation and demo (5)

| Criterion | Evidence |
|---|---|
| `README.md` explaining the app | [`README.md`](../README.md) |
| Recorded walkthrough | [`demo/ClinicFlow-demo.mp4`](demo/ClinicFlow-demo.mp4): commit `3cc58be` bumps the version to 0.2.0, [run 38908997070](https://github.com/kunalKumar-13/clinicflow/actions/runs/38908997070) tests, scans, pushes and deploys it, and the app through the Ingress then shows v0.2.0 and that commit |
| Live demo: commit, pipeline, deployment updates | push any change to `main`: the pipeline tests it, scans it, pushes `:<sha>` images and redeploys them. The app's sidebar shows the commit it was built from, so the new SHA is visible in the running app, and it matches the deployed image tag on the package page |
