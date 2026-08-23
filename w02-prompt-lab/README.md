# Local Prompt Portfolio and Model Comparison

This is a clean-room, working example of the `w02-prompt-lab` project. The program has the following workflow:

0. Runs a three prompt-driven tasks against two local Ollama models, validates structured outputs,

1. It scores them deterministically against synthetic gold labels, records token usage and latency

2. Generates a comparison report.

It is **not** the program's official starter repository or canonical corpus. The cases and gold labels in this repository were purposefully and independently authored from the assignment specification.

## Architecture

The Python harness runs inside a Linux devcontainer. Ollama runs natively on the Mac so it can use Apple Metal acceleration.

```text
VS Code -> Linux devcontainer -> http://host.docker.internal:11434 -> Ollama on macOS
                                                               |-> mistral:7b
                                                               `-> qwen3:8b
```

## One-time Mac setup

1. Install Docker Desktop, VS Code, the Dev Containers extension, and Ollama.
2. Start Docker Desktop and the Ollama application.
3. Pull the models:

   ```bash
   ollama pull mistral:7b
   ollama pull qwen3:8b
   ```

4. Verify the Mac-side service:

   ```bash
   curl http://localhost:11434/api/tags
   ```

## Open in the Linux devcontainer

1. Unzip this project on the Mac.
2. Open the extracted folder in VS Code.
3. Run **Dev Containers: Reopen in Container** from the Command Palette.
4. Wait for `uv sync --frozen` to finish.
5. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

6. Verify that the container can reach Ollama on the Mac:

   ```bash
   curl http://host.docker.internal:11434/api/tags
   ```

## Quality checks

Run these inside the devcontainer:

```bash
uv run pytest
uv run ruff check .
uv run mypy src tests
```

These checks do not make model calls.

## Smoke run

Run one case from each task against both models:

```bash
uv run promptlab --run-id smoke-01 --limit 1
```

Run one complete task:

```bash
uv run promptlab --run-id triage-01 --task triage
```

## Full comparison

The default executes all 36 cases against both models: 72 primary model/case executions,
plus any bounded schema repairs.

```bash
uv run promptlab --run-id local-comparison-01
```

Outputs are written to:

```text
runs/local-comparison-01/usage.jsonl
runs/local-comparison-01/outputs.jsonl
runs/local-comparison-01/scores.jsonl
reports/comparison.md
docs/model-decision.md
```

`runs/` is ignored by Git. The report and decision document are deliberately tracked.

## Useful selections

```bash
# One task, both models
uv run promptlab --run-id extraction-01 --task extraction

# One configured model, all tasks
uv run promptlab --run-id mistral-01 --model mistral

# Two cases per task for a fast demo
uv run promptlab --run-id demo-01 --limit 2
```

Model selections are the logical names `mistral` and `qwen`; their concrete Ollama tags are configured in `.env`.

## What is deterministic

The models interpret language and return structured objects. Python determines:

- schema validity and bounded repair;
- routing, escalation, evidence, citation, PII, and human-boundary scores;
- which document version applies on a review date;
- token, latency, attempt, and repair accounting;
- report aggregation and the evidence-based recommendation.

The prompts never ask a model to decide which version is current. They ask only for version and effective-date extraction; `promptlab.rules.select_current_version` makes the decision.

## Local cost semantics

Local Ollama inference has a recorded provider charge of `$0.00`. Token counts, latency, failed attempts, and repairs are still recorded. The report explicitly excludes electricity, hardware acquisition, and engineering labor from the zero marginal provider cost Obviously I'm not buying you a computer or paying your electrical bill..

## Reproducibility note

For a serious comparison, record `ollama list` and `ollama show <model>` output with the run.

Ollama tags can change; a model digest is stronger evidence than a friendly tag alone.

Author: David Kolesar