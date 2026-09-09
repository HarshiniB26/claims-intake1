# Claims Intake Service

Accepts a first notice of loss from the claims portal, checks it against the
policy master and the rules in `docs/api-contract.md`, and either records the
notification and returns a claim reference or refuses with a specific code.

The HTTP surface is `POST /notifications`. Success is `201` with
`claim_reference` and `status: recorded`. Every refusal uses the envelope in
contract section 5 (`code`, `message`, `detail`) and the status in section 6.

## Where things are

| Path | What it holds |
| --- | --- |
| `docs/api-contract.md` | What the service accepts, returns, and refuses. The authority. |
| `docs/requirements-brief.md` | Work items and acceptance criteria. |
| `docs/payload-triage.md` | Classification of the edge payloads. |
| `data/` | Synthetic policies and notification payloads. |
| `src/claims/` | Models, repository, rules, and HTTP routes. |
| `tests/` | Unit tests for objects and rules. Integration tests hit HTTP. |
| `Dockerfile` | Image that runs the service. |

## Working in this repository

You are already inside the lab Linux container. Confirm it:

```
uname -sm     # often Linux aarch64
pwd           # /workspaces/claims-intake
```

Python, `uv`, and the project dependencies are already installed. Do not install
anything. If a tool you need is missing, report it rather than working around it.

## Run the service

From this folder (`/workspaces/claims-intake`):

```
uv run uvicorn claims.api.routes:app --host 0.0.0.0 --port 8000
```

POST a notification:

```
curl -s -X POST http://127.0.0.1:8000/notifications \
  -H "Content-Type: application/json" \
  -d '{"policy_number":"MOT-4471","loss_date":"2026-04-02","claim_type":"collision","estimated_amount":"4200.00"}'
```

A valid body returns `201` and a `claim_reference` like `CLM-2026-000001`. Sample
payloads are in `data/fnol_valid.json`, `data/fnol_invalid.json`, and
`data/fnol_edge.json`.

## Run the tests

From the same folder:

```
uv run pytest
uv run ruff check .
uv run mypy src tests
```

`uv run pytest tests/integration` runs only the HTTP tests.

## Container image

This lab container does not ship the `docker` CLI (`docker: command not found`).
That is a gap in the lab image, not an install step. Build and run the image on a
machine that already has Docker (for example a host laptop).

The `Dockerfile` in this folder copies `src/` and `data/`, installs from
`uv.lock` with `uv sync --frozen --no-dev`, and starts uvicorn on port 8000.

From this folder, on a machine that has Docker:

```
docker buildx build --platform linux/amd64 -t claims-intake .
docker run --rm -p 8000:8000 claims-intake
```

Then use the same `curl` as above against `http://127.0.0.1:8000/notifications`.

### Why `--platform linux/amd64`

Docker builds for the CPU of the machine you are standing on unless you say
otherwise. This lab environment reports `Linux aarch64` (ARM). A Mac with Apple
silicon is ARM as well. Most of the places this image would actually run — a
cloud VM, many CI runners, a typical Linux server — are `linux/amd64`
(Intel/AMD 64-bit).

If you omit the flag, you get an ARM image. That image will not start on an
amd64 host, or it will fail in a way that looks like an application bug. The
flag is not “because the command needs it.” It is so the bits inside the image
match the machine that will run them, even when that machine is not the one
doing the build.

## Data

Everything in `data/` is synthetic and was authored for this program. It contains
no real client data and no named clients.
