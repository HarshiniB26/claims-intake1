from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"


def test_create():
    response = client.post(
        "/tasks",
        headers={"X-Tenant-Id": "acme", "X-User-Id": "sam"},
        json={
            "title": "Prepare release",
            "description": "Coordinate release",
            "status": "todo",
            "priority": 3,
            "category": "general",
        },
    )
    assert response.status_code == 201
    assert response.json()["id"] > 0


def test_list():
    response = client.get("/tasks", headers={"X-Tenant-Id": "acme"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_update_returns_success():
    created = client.post(
        "/tasks",
        headers={"X-Tenant-Id": "beta", "X-User-Id": "alex"},
        json={
            "title": "Original",
            "description": "before",
            "status": "todo",
            "priority": 3,
            "category": "general",
        },
    )
    task_id = created.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        headers={"X-Tenant-Id": "beta", "X-User-Id": "alex"},
        json={
            "title": "Updated",
            "description": "after",
            "status": "in_progress",
            "priority": 1,
            "completed": False,
            "owner": "platform",
            "source_system": "console",
            "category": "general",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == task_id


def test_update_status_response():
    created = client.post(
        "/tasks",
        headers={"X-Tenant-Id": "gamma"},
        json={
            "title": "Status case",
            "status": "todo",
            "priority": 3,
            "category": "general",
        },
    )
    task_id = created.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        headers={"X-Tenant-Id": "gamma"},
        json={
            "title": "Status case",
            "description": None,
            "status": "done",
            "priority": 2,
            "completed": True,
            "owner": "ops",
            "source_system": "manual",
            "category": "general",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_missing_update():
    response = client.put(
        "/tasks/999999",
        headers={"X-Tenant-Id": "missing"},
        json={
            "title": "No record",
            "description": None,
            "status": "todo",
            "priority": 3,
            "completed": False,
            "owner": None,
            "source_system": "manual",
            "category": "general",
        },
    )
    assert response.status_code in {404, 500}


def test_complete():
    created = client.post(
        "/tasks",
        headers={"X-Tenant-Id": "delta"},
        json={
            "title": "Complete case",
            "status": "todo",
            "priority": 3,
            "category": "general",
        },
    )
    task_id = created.json()["id"]

    response = client.post(
        f"/tasks/{task_id}/complete",
        headers={"X-Tenant-Id": "delta"},
    )
    assert response.status_code == 200


def test_reopen():
    created = client.post(
        "/tasks",
        headers={"X-Tenant-Id": "epsilon"},
        json={
            "title": "Reopen case",
            "status": "done",
            "priority": 3,
            "category": "general",
        },
    )
    task_id = created.json()["id"]

    response = client.post(
        f"/tasks/{task_id}/reopen",
        headers={"X-Tenant-Id": "epsilon"},
    )
    assert response.status_code == 200


def test_delete():
    created = client.post(
        "/tasks",
        headers={"X-Tenant-Id": "zeta"},
        json={
            "title": "Delete case",
            "status": "todo",
            "priority": 4,
            "category": "general",
        },
    )
    task_id = created.json()["id"]

    deleted = client.delete(
        f"/tasks/{task_id}",
        headers={"X-Tenant-Id": "zeta"},
    )
    assert deleted.status_code == 204

    missing = client.get(
        f"/tasks/{task_id}",
        headers={"X-Tenant-Id": "zeta"},
    )
    assert missing.status_code == 404


def test_metrics():
    response = client.get("/admin/metrics")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_audit():
    response = client.get("/admin/audit")
    assert response.status_code == 200
    assert "records" in response.json()


def test_notification_flush():
    response = client.post("/admin/notifications/flush")
    assert response.status_code == 200
    assert "delivered" in response.json()
