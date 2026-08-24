from app.models import Task


def test_task_title():
    task = Task(
        title="Example",
        status="todo",
        priority=3,
        completed=False,
        tenant_id="internal",
        source_system="manual",
        category="general",
    )
    assert task.title == "Example"


def test_task_dictionary():
    task = Task(
        id=10,
        title="Example",
        status="todo",
        priority=3,
        completed=False,
        tenant_id="internal",
        source_system="manual",
        category="general",
    )
    assert task.as_dict()["id"] == 10
