from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from promptlab.config import PROJECT_ROOT
from promptlab.schemas import TaskName


class CaseSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    task: TaskName
    source: str


class GoldLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    task: TaskName
    expected_queue: str | None = None
    expected_escalation: bool | None = None
    expected_status: str | None = None
    recoverable_fields: list[str] = []
    version_group: str | None = None
    expected_current_case_id: str | None = None
    as_of: str | None = None
    metadata: dict[str, Any] = {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Expected an object at {path}:{line_number}")
        rows.append(value)
    return rows


def load_cases(task: TaskName) -> list[tuple[CaseSource, GoldLabel]]:
    cases_path = PROJECT_ROOT / "cases" / f"{task}.jsonl"
    gold_path = PROJECT_ROOT / "cases" / "gold" / f"{task}.jsonl"
    cases = [CaseSource.model_validate(row) for row in _read_jsonl(cases_path)]
    gold = [GoldLabel.model_validate(row) for row in _read_jsonl(gold_path)]
    gold_by_id = {label.id: label for label in gold}

    if len(gold_by_id) != len(gold):
        raise ValueError(f"Duplicate gold label ids in {gold_path}")
    if {case.id for case in cases} != set(gold_by_id):
        raise ValueError(f"Case and gold ids do not match for {task}")
    if any(case.task != task for case in cases) or any(label.task != task for label in gold):
        raise ValueError(f"Task mismatch in {task} corpus")
    return [(case, gold_by_id[case.id]) for case in cases]


def validate_corpus() -> dict[TaskName, int]:
    counts: dict[TaskName, int] = {}
    for task in ("triage", "summarization", "extraction"):
        counts[task] = len(load_cases(task))
    return counts

