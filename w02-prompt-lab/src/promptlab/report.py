from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median

from promptlab.records import OutputRecord, ScoreRecord, UsageRecord
from promptlab.schemas import TaskName


def _fmt_decimal(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.000001'))}"


def _task_recommendation(
    task: TaskName, models: list[str], scores: list[ScoreRecord]
) -> tuple[str, str]:
    ranked: list[tuple[tuple[int, float], str]] = []
    for model in models:
        rows = [row for row in scores if row.task == task and row.model_name == model]
        by_metric: dict[str, list[ScoreRecord]] = defaultdict(list)
        for row in rows:
            by_metric[row.metric].append(row)

        safety = 1
        boundary = by_metric.get("human_boundary_compliance", [])
        leakage = by_metric.get("pii_leakage", [])
        if boundary and sum(row.numerator for row in boundary) < sum(
            row.denominator for row in boundary
        ):
            safety = 0
        if leakage and sum(row.numerator for row in leakage) > 0:
            safety = 0

        rates: list[float] = []
        for metric_rows in by_metric.values():
            denominator = sum(row.denominator for row in metric_rows)
            if denominator == 0:
                continue
            numerator = sum(row.numerator for row in metric_rows)
            rate = numerator / denominator
            if metric_rows[0].lower_is_better:
                rate = 1.0 - rate
            rates.append(rate)
        ranked.append(((safety, sum(rates) / len(rates) if rates else 0.0), model))

    ranked.sort(reverse=True)
    winner = ranked[0][1]
    return winner, (
        f"{winner} is recommended for {task} because it ranked highest after safety "
        "failures were considered before aggregate quality."
    )


def write_reports(
    *,
    run_id: str,
    models: list[str],
    usage: list[UsageRecord],
    outputs: list[OutputRecord],
    scores: list[ScoreRecord],
    report_path: Path,
    decision_path: Path,
) -> None:
    lines = [
        "# Local Model Comparison",
        "",
        f"Run identifier: `{run_id}`",
        "",
        "This report was generated from the run records. The narrative and corpus are part of a "
        "clean-room prototype, not the missing official course repository.",
        "",
        "## Method",
        "",
        "All selected cases were run sequentially at temperature `0.0`. Quality was scored "
        "against synthetic gold labels. Local Ollama inference has zero marginal provider charge; "
        "the cost figures exclude hardware, electricity, and engineering labor.",
        "",
    ]

    recommendations: list[tuple[TaskName, str, str]] = []
    for task in ("triage", "summarization", "extraction"):
        task_outputs = [row for row in outputs if row.task == task]
        if not task_outputs:
            continue
        lines.extend([f"## {task.title()}", ""])
        task_metrics = sorted({row.metric for row in scores if row.task == task})
        header = ["Model", "Prompt", *task_metrics, "Cost/case", "Repairs", "Latency"]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        for model in models:
            model_outputs = [row for row in task_outputs if row.model_name == model]
            if not model_outputs:
                continue
            prompt_versions = sorted({row.prompt_version for row in model_outputs})
            metric_cells: list[str] = []
            for metric in task_metrics:
                metric_rows = [
                    row
                    for row in scores
                    if row.task == task and row.model_name == model and row.metric == metric
                ]
                numerator = sum(row.numerator for row in metric_rows)
                denominator = sum(row.denominator for row in metric_rows)
                metric_cells.append(f"{numerator}/{denominator}")

            model_usage = [
                row for row in usage if row.task == task and row.model_name == model
            ]
            cost = sum((row.cost_usd for row in model_usage), Decimal("0"))
            attempted_cases = len({row.case_id for row in model_outputs})
            cost_per_case = cost / attempted_cases if attempted_cases else Decimal("0")
            repairs = sum(row.repairs for row in model_outputs)

            case_latency: dict[str, float] = defaultdict(float)
            for usage_row in model_usage:
                case_latency[usage_row.case_id] += usage_row.latency_ms
            observations = list(case_latency.values())
            if observations:
                latency = (
                    f"median {median(observations):.0f} ms; max {max(observations):.0f} ms; "
                    f"n={len(observations)}"
                )
            else:
                latency = "n=0"
            table_row = [
                model,
                ", ".join(prompt_versions),
                *metric_cells,
                _fmt_decimal(cost_per_case),
                f"{repairs}/{attempted_cases}",
                latency,
            ]
            lines.append("| " + " | ".join(table_row) + " |")
        lines.append("")
        winner, rationale = _task_recommendation(task, models, scores)
        recommendations.append((task, winner, rationale))

    lines.extend(
        [
            "## Limits",
            "",
            "- The corpus is synthetic and contains only twelve cases per task.",
            "- This is a development corpus, not a blind holdout or real-client validation set.",
            "- Local model tags can change; retain model digests with material comparison "
            "evidence.",
            "- Temperature zero reduces variation but does not guarantee identical generations.",
            "- Latency depends on model loading, Mac workload, and hardware configuration.",
            "- Zero provider cost excludes hardware, electricity, maintenance, and engineering "
            "labor.",
            "- Gold labels were authored once and have not undergone independent adjudication.",
            "",
            "## Recommendation",
            "",
        ]
    )
    for task, _winner, rationale in recommendations:
        lines.append(f"- **{task}:** {rationale}")
    lines.extend(
        [
            "",
            "Use these recommendations only for this corpus and these recorded model artifacts. "
            "Re-run the comparison when a model digest, prompt version, corpus, or operational "
            "constraint changes.",
            "",
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    decision_lines = [
        "# Model Decision Record",
        "",
        f"Evidence run: `{run_id}`",
        "",
        "## Decision",
        "",
    ]
    for task, winner, _rationale in recommendations:
        prompts = sorted(
            {
                row.prompt_version
                for row in outputs
                if row.task == task and row.model_name == winner
            }
        )
        decision_lines.append(
            f"- Use **{winner}** for **{task}** with prompt version(s) "
            f"`{', '.join(prompts)}` under the prototype constraints."
        )
    decision_lines.extend(
        [
            "",
            "## Evidence",
            "",
            "The generated tables in `reports/comparison.md` are the controlling evidence. Every "
            "row names the prompt version and derives its counts, costs, repairs, and latency from "
            "the run records.",
            "",
            "## Rejected alternatives",
            "",
            "Models that ranked lower after safety-first ordering were rejected for the applicable "
            "task. A single universal model was not assumed when task-specific evidence differed.",
            "",
            "## Review triggers",
            "",
            "- Either Ollama model digest changes.",
            "- A prompt or scorer version changes.",
            "- Human-boundary or PII-leakage performance regresses.",
            "- Production-like or independently adjudicated cases become available.",
            "- Hardware, latency, cost, or deployment constraints change.",
            "",
        ]
    )
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text("\n".join(decision_lines), encoding="utf-8")
