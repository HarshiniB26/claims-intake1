# Status Tracker Service

Internal API used to track operational work items across teams and source systems.

## Capabilities

- Create, read, update, and delete work items
- Complete and reopen tasks
- Tenant-aware requests
- Owner and category filtering
- Audit trail
- Runtime metrics
- Notification outbox
- Local Docker support

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```bash
pytest -v
```

Run the terminal smoke test:

```bash
./curl_tests.sh
```

## Headers

Most task endpoints accept:

```text
X-User-Id
X-Tenant-Id
X-Correlation-Id
```

The local default tenant is `internal`.
