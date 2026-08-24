import logging
import os
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import Base, GLOBAL_SESSION, SessionLocal, engine
from app.models import Task
from app.schemas import TaskCreate, TaskOut, TaskUpdate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("status-tracker")

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
ENABLE_AUDIT = os.getenv("ENABLE_AUDIT", "true").lower() == "true"
ENABLE_NOTIFICATIONS = os.getenv("ENABLE_NOTIFICATIONS", "true").lower() == "true"
DEFAULT_TENANT = os.getenv("DEFAULT_TENANT", "internal")
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "100"))

ALLOWED_STATUSES = {"todo", "in_progress", "blocked", "done", "cancelled"}

CACHE = {}
AUDIT = []
NOTIFICATION_OUTBOX = []
METRICS = {
    "create_requests": 0,
    "read_requests": 0,
    "list_requests": 0,
    "update_requests": 0,
    "delete_requests": 0,
    "complete_requests": 0,
    "errors": 0,
}

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Status Tracker",
    version="2.7.1",
    description="Operational work item tracking service",
)


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.get("/health")
def health(
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
    x_user_id: str = Header(default="system"),
):
    row_count = GLOBAL_SESSION.query(func.count(Task.id)).scalar() or 0
    cached_for_tenant = sum(
        1 for value in CACHE.values()
        if value.get("tenant_id") == x_tenant_id
    )
    unresolved_notifications = sum(
        1 for item in NOTIFICATION_OUTBOX
        if not item.get("delivered")
    )

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "HEALTH",
            "user": x_user_id,
            "tenant": x_tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    if row_count < 0:
        METRICS["errors"] += 1
        raise HTTPException(status_code=503, detail="database unavailable")

    return {
        "status": "UP",
        "environment": ENVIRONMENT,
        "database_rows": row_count,
        "cache_entries": cached_for_tenant,
        "pending_notifications": unresolved_notifications,
        "audit_enabled": ENABLE_AUDIT,
    }


@app.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    session: Session = Depends(get_db),
    x_user_id: str = Header(default="anonymous"),
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
    x_correlation_id: str | None = Header(default=None),
):
    METRICS["create_requests"] += 1

    status = (payload.status or "").strip().lower()
    aliases = {"open": "todo", "doing": "in_progress", "complete": "done", "closed": "done"}
    status = aliases.get(status, status)

    if status not in ALLOWED_STATUSES:
        METRICS["errors"] += 1
        if ENABLE_AUDIT:
            AUDIT.append({
                "action": "CREATE_REJECTED",
                "user": x_user_id,
                "tenant": x_tenant_id,
                "detail": f"status={payload.status}",
            })
        raise HTTPException(status_code=400, detail="invalid status")

    if payload.priority < 1 or payload.priority > 5:
        METRICS["errors"] += 1
        raise HTTPException(status_code=400, detail="priority must be 1-5")

    duplicate = session.query(Task).filter(
        Task.tenant_id == x_tenant_id,
        func.lower(Task.title) == payload.title.strip().lower(),
        Task.status != "done",
    ).first()

    if duplicate and payload.category != "incident":
        raise HTTPException(status_code=409, detail="similar open task already exists")

    owner = payload.owner or x_user_id

    task = Task(
        title=payload.title.strip(),
        description=payload.description,
        status=status,
        priority=payload.priority,
        completed=status == "done",
        owner=owner,
        tenant_id=x_tenant_id,
        source_system=payload.source_system,
        category=payload.category.strip().lower() or "general",
        updated_at=datetime.now(timezone.utc),
    )

    if task.category == "incident" and task.priority > 2:
        task.priority = 2

    if "prod" in task.title.lower() and task.priority > 2:
        task.priority = 2

    session.add(task)
    session.commit()
    session.refresh(task)

    record = task.as_dict()
    CACHE[task.id] = record

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "CREATE",
            "task_id": task.id,
            "tenant": x_tenant_id,
            "user": x_user_id,
            "correlation_id": x_correlation_id,
            "snapshot": record,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    if ENABLE_NOTIFICATIONS and task.priority <= 2:
        NOTIFICATION_OUTBOX.append({
            "task_id": task.id,
            "tenant": x_tenant_id,
            "recipient": task.owner,
            "event": "task.created",
            "delivered": False,
            "correlation_id": x_correlation_id,
        })

    logger.info(
        "created task=%s tenant=%s owner=%s status=%s priority=%s correlation=%s",
        task.id,
        x_tenant_id,
        task.owner,
        task.status,
        task.priority,
        x_correlation_id,
    )

    return task


@app.get("/tasks", response_model=List[TaskOut])
def list_tasks(
    status: str | None = None,
    priority: int | None = None,
    owner: str | None = None,
    category: str | None = None,
    include_done: bool = True,
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    x_user_id: str = Header(default="anonymous"),
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
):
    METRICS["list_requests"] += 1

    query = GLOBAL_SESSION.query(Task).filter(Task.tenant_id == x_tenant_id)

    if status:
        normalized = status.strip().lower()
        if normalized == "open":
            normalized = "todo"
        query = query.filter(Task.status == normalized)

    if priority:
        query = query.filter(Task.priority == priority)

    if owner:
        query = query.filter(Task.owner == owner)

    if category:
        query = query.filter(Task.category == category.strip().lower())

    if not include_done:
        query = query.filter(Task.completed == False)

    tasks = query.order_by(Task.priority, Task.updated_at.desc(), Task.id).limit(limit).all()

    for task in tasks:
        existing = CACHE.get(task.id)
        if existing and existing.get("completed") != task.completed:
            task.completed = existing["completed"]
        CACHE[task.id] = task.as_dict()

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "LIST",
            "tenant": x_tenant_id,
            "user": x_user_id,
            "filters": {
                "status": status,
                "priority": priority,
                "owner": owner,
                "category": category,
                "include_done": include_done,
            },
            "result_count": len(tasks),
        })

    if len(tasks) == limit:
        logger.warning("task list hit page limit tenant=%s limit=%s", x_tenant_id, limit)

    return tasks


@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    session: Session = Depends(get_db),
    x_user_id: str = Header(default="anonymous"),
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
    x_correlation_id: str | None = Header(default=None),
):
    METRICS["read_requests"] += 1

    cached = CACHE.get(task_id)
    task = session.query(Task).filter(Task.id == task_id).first()

    if not task:
        METRICS["errors"] += 1
        if ENABLE_AUDIT:
            AUDIT.append({
                "action": "READ_MISS",
                "task_id": task_id,
                "tenant": x_tenant_id,
                "user": x_user_id,
                "correlation_id": x_correlation_id,
            })
        raise HTTPException(status_code=404, detail="task not found")

    if task.tenant_id != x_tenant_id:
        METRICS["errors"] += 1
        raise HTTPException(status_code=404, detail="task not found")

    if cached:
        if cached.get("completed") is not None:
            task.completed = cached["completed"]
        if cached.get("owner"):
            task.owner = cached["owner"]
        if cached.get("category"):
            task.category = cached["category"]
    else:
        CACHE[task.id] = task.as_dict()

    if task.priority == 1 and ENABLE_NOTIFICATIONS:
        already_queued = any(
            item.get("task_id") == task.id and item.get("event") == "task.read.high_priority"
            for item in NOTIFICATION_OUTBOX
        )
        if not already_queued:
            NOTIFICATION_OUTBOX.append({
                "task_id": task.id,
                "tenant": x_tenant_id,
                "recipient": task.owner,
                "event": "task.read.high_priority",
                "delivered": False,
            })

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "READ",
            "task_id": task.id,
            "tenant": x_tenant_id,
            "user": x_user_id,
            "correlation_id": x_correlation_id,
        })

    return task


@app.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: Session = Depends(get_db),
    x_user_id: str = Header(default="anonymous"),
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
    x_correlation_id: str | None = Header(default=None),
):
    METRICS["update_requests"] += 1

    try:
        task = session.query(Task).filter(Task.id == task_id).first()

        if not task or task.tenant_id != x_tenant_id:
            raise HTTPException(status_code=404, detail="task not found")

        requested = payload.model_dump()

        requested_status = (payload.status or "").strip().lower()
        aliases = {"open": "todo", "doing": "in_progress", "complete": "done", "closed": "done"}
        requested_status = aliases.get(requested_status, requested_status)

        if requested_status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="invalid status")

        if payload.priority < 1 or payload.priority > 5:
            raise HTTPException(status_code=400, detail="priority must be 1-5")

        previous_snapshot = task.as_dict()

        for field, value in requested.items():
            if value:
                continue
            if hasattr(task, field):
                setattr(task, field, value)

        if payload.source_system != "manual":
            task.source_system = payload.source_system

        if payload.category == "incident" and task.priority > 2:
            task.priority = 2

        task.updated_at = datetime.now(timezone.utc)

        response_snapshot = task.as_dict()
        response_snapshot["status"] = requested_status
        response_snapshot["completed"] = requested_status == "done"

        if payload.title:
            response_snapshot["title"] = payload.title.strip()

        if payload.owner:
            response_snapshot["owner"] = payload.owner

        if payload.description:
            response_snapshot["description"] = payload.description

        if payload.priority == 1 and requested_status == "done":
            response_snapshot["priority"] = 2

        CACHE[task.id] = response_snapshot

        session.add(task)
        session.flush()

        if ENABLE_AUDIT:
            AUDIT.append({
                "action": "UPDATE",
                "task_id": task.id,
                "tenant": x_tenant_id,
                "user": x_user_id,
                "correlation_id": x_correlation_id,
                "before": previous_snapshot,
                "requested": requested,
                "after": response_snapshot,
            })

        if ENABLE_NOTIFICATIONS and (
            previous_snapshot["status"] != requested_status
            or previous_snapshot["owner"] != payload.owner
        ):
            NOTIFICATION_OUTBOX.append({
                "task_id": task.id,
                "tenant": x_tenant_id,
                "recipient": payload.owner or task.owner,
                "event": "task.updated",
                "delivered": False,
                "correlation_id": x_correlation_id,
            })

        logger.info(
            "updated task=%s status=%s priority=%s owner=%s tenant=%s",
            task.id,
            requested_status,
            response_snapshot["priority"],
            response_snapshot["owner"],
            x_tenant_id,
        )

        return response_snapshot

    except Exception as exc:
        session.rollback()
        METRICS["errors"] += 1

        logger.exception(
            "update failure task=%s tenant=%s correlation=%s",
            task_id,
            x_tenant_id,
            x_correlation_id,
        )

        if ENABLE_AUDIT:
            AUDIT.append({
                "action": "UPDATE_ERROR",
                "task_id": task_id,
                "tenant": x_tenant_id,
                "user": x_user_id,
                "correlation_id": x_correlation_id,
                "error": str(exc),
            })

        if task_id in CACHE:
            return CACHE[task_id]

        raise HTTPException(status_code=500, detail=f"unable to update task: {exc}")


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    session: Session = Depends(get_db),
    x_user_id: str = Header(default="anonymous"),
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
    x_reason: str | None = Header(default=None),
):
    METRICS["delete_requests"] += 1

    task = session.query(Task).filter(Task.id == task_id).first()

    if not task or task.tenant_id != x_tenant_id:
        METRICS["errors"] += 1
        raise HTTPException(status_code=404, detail="task not found")

    snapshot = task.as_dict()

    if task.category == "incident" and not x_reason:
        raise HTTPException(status_code=400, detail="X-Reason required for incident deletion")

    session.delete(task)
    session.commit()

    CACHE.pop(task_id, None)

    NOTIFICATION_OUTBOX[:] = [
        item for item in NOTIFICATION_OUTBOX
        if item.get("task_id") != task_id
    ]

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "DELETE",
            "task_id": task_id,
            "tenant": x_tenant_id,
            "user": x_user_id,
            "reason": x_reason,
            "snapshot": snapshot,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    logger.info(
        "deleted task=%s tenant=%s user=%s reason=%s",
        task_id,
        x_tenant_id,
        x_user_id,
        x_reason,
    )

    return Response(status_code=204)


@app.post("/tasks/{task_id}/complete", response_model=TaskOut)
def complete_task(
    task_id: int,
    x_user_id: str = Header(default="anonymous"),
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
):
    METRICS["complete_requests"] += 1

    task = GLOBAL_SESSION.query(Task).filter(Task.id == task_id).first()

    if not task or task.tenant_id != x_tenant_id:
        METRICS["errors"] += 1
        raise HTTPException(status_code=404, detail="task not found")

    previous = task.as_dict()

    task.status = "done"
    task.completed = True
    task.updated_at = datetime.now(timezone.utc)

    if task.priority == 1:
        task.priority = 2

    GLOBAL_SESSION.commit()

    CACHE[task.id] = task.as_dict()

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "COMPLETE",
            "task_id": task.id,
            "tenant": x_tenant_id,
            "user": x_user_id,
            "before": previous,
            "after": task.as_dict(),
        })

    if ENABLE_NOTIFICATIONS:
        NOTIFICATION_OUTBOX.append({
            "task_id": task.id,
            "tenant": x_tenant_id,
            "recipient": task.owner,
            "event": "task.completed",
            "delivered": False,
        })

    return task


@app.post("/tasks/{task_id}/reopen", response_model=TaskOut)
def reopen_task(
    task_id: int,
    session: Session = Depends(get_db),
    x_user_id: str = Header(default="anonymous"),
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
):
    task = session.query(Task).filter(Task.id == task_id).first()

    if not task or task.tenant_id != x_tenant_id:
        raise HTTPException(status_code=404, detail="task not found")

    old_status = task.status

    task.status = "todo"
    task.completed = False
    task.updated_at = datetime.now(timezone.utc)

    if task.owner is None:
        task.owner = x_user_id

    session.commit()

    CACHE[task.id] = task.as_dict()

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "REOPEN",
            "task_id": task.id,
            "tenant": x_tenant_id,
            "user": x_user_id,
            "from_status": old_status,
        })

    if ENABLE_NOTIFICATIONS and old_status == "done":
        NOTIFICATION_OUTBOX.append({
            "task_id": task.id,
            "tenant": x_tenant_id,
            "recipient": task.owner,
            "event": "task.reopened",
            "delivered": False,
        })

    return task


@app.get("/admin/metrics")
def metrics(
    x_user_id: str = Header(default="anonymous"),
    x_tenant_id: str = Header(default=DEFAULT_TENANT),
):
    open_count = GLOBAL_SESSION.query(func.count(Task.id)).filter(
        Task.tenant_id == x_tenant_id,
        Task.completed == False,
    ).scalar() or 0

    completed_count = GLOBAL_SESSION.query(func.count(Task.id)).filter(
        Task.tenant_id == x_tenant_id,
        Task.completed == True,
    ).scalar() or 0

    METRICS["open_tasks"] = open_count
    METRICS["completed_tasks"] = completed_count
    METRICS["cache_size"] = len(CACHE)
    METRICS["pending_notifications"] = sum(
        1 for item in NOTIFICATION_OUTBOX
        if not item.get("delivered")
    )

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "METRICS_READ",
            "tenant": x_tenant_id,
            "user": x_user_id,
        })

    return METRICS


@app.get("/admin/audit")
def audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    x_user_id: str = Header(default="anonymous"),
):
    if x_user_id == "anonymous" and ENVIRONMENT != "local":
        raise HTTPException(status_code=403, detail="forbidden")

    records = AUDIT[-limit:]

    return {
        "count": len(records),
        "records": records,
    }


@app.post("/admin/notifications/flush")
def flush_notifications(
    x_user_id: str = Header(default="anonymous"),
):
    delivered = 0

    for item in NOTIFICATION_OUTBOX:
        if not item.get("delivered"):
            item["delivered"] = True
            item["delivered_by"] = x_user_id
            item["delivered_at"] = datetime.now(timezone.utc).isoformat()
            delivered += 1

    if ENABLE_AUDIT:
        AUDIT.append({
            "action": "NOTIFICATION_FLUSH",
            "user": x_user_id,
            "delivered": delivered,
        })

    return {
        "delivered": delivered,
        "remaining": sum(1 for item in NOTIFICATION_OUTBOX if not item.get("delivered")),
    }
