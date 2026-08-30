# w02-prompt-lab

Week 2 of the Associate FDE program. A harness that runs three prompt-driven tasks against two models over a fixed case set, scores the outputs deterministically against gold labels, and produces a comparison report.

This is a new repository. It does not extend Week 1's `claims-intake`, which stays parked until Week 4.

## Getting started

Open the repository in the devcontainer. The image arrives with the toolchain installed and the dependencies pinned, so there is no install step anywhere this week.

```
uv sync
cp .env.example .env
```

Populate `.env` from the credentials issued to you and from your own Azure OpenAI deployment. Then confirm both providers are reachable from inside the container before Day 1's assignment, not during it.

`.env` is ignored. Every assignment this week carries an acceptance criterion that scores zero for the criterion if a credential appears in a diff.

## Conventions

Six things about this repository are deliberate. Each of them looks like a mistake until you know why.

**Prompt files live in `src/promptlab/prompts/`.** Assignments write these paths in short form, as `prompts/summarize.v1.md`. That is the same directory written two ways, not a second one at the repository root.

**`prompts.py` sits beside `prompts/`, and that is intentional.** The module is the prompt registry. The directory holds the prompt text. Python resolves `promptlab.prompts` to the module rather than the directory, but only because the directory carries no `__init__.py`. Do not add one. Doing so breaks every import in the package.

**The gold set defines what gets scored.** `cases/` holds the source material and `cases/gold/{task}/` holds the labels. The runner iterates the gold labels rather than listing `cases/`, so a document without a gold label is never scored. `cases/extract/` deliberately holds more documents than the extraction gold set covers.

**`runs/` is ignored.** Records append there during a run. Evidence that belongs in a pull request is copied deliberately into `docs/`, which means you choose what you are showing rather than committing whatever accumulated.

**`examples/` and `cases/` never mix.** Nothing in `examples/` is ever scored. Nothing in `cases/` is ever shown to a model as an example. The example documents are written so their surface details appear nowhere in `cases/`, which is what makes example leakage into an output detectable by search. Once a scored case has been used as an example, every measurement taken against it for the rest of the week is worthless, and nothing in this repository will tell you it happened.

**Unimplemented modules ship as stubs.** Signatures and docstrings are present and bodies raise `NotImplementedError`. Every path named in an assignment is therefore already true, and you are never guessing at a file name. Fill the bodies in. Do not rename the files.

## Your Azure deployment

You create your own deployment in the Azure portal. The name is your choice and goes in `.env` as `AZURE_OPENAI_DEPLOYMENT`. The model version and the API version are not your choice; both are pinned for the cohort and are given to you. If they vary across the room then nobody's Day 5 comparison can be read against anybody else's.

The deployment name is not the model's name. It routes your call to an instance running inside your Azure resource. This is why `config.MODELS` reads the Azure entry from the environment while the Anthropic entry is a literal, and it is the layer Day 2 Article 1 covers when it discusses pinning a model identifier.

## Checks

```
uv run ruff check .
uv run mypy
uv run pytest
```

All three run in CI on every pull request. The test suite makes no network calls and passes with empty credentials, which CI enforces by running it that way. A test that needs a key to pass is a test that will fail for the person reviewing your work.

## Layout

```
w02-prompt-lab/
  .devcontainer/
  .github/workflows/
  cases/
    triage/            twelve customer messages
    summarize/         twelve dispute handling procedures
    extract/           KYC review policies, of which twelve are scored
    gold/{task}/       one label per scored case
  docs/                supplied inputs and your committed evidence
  examples/            four boundary documents, never scored
  reports/
  runs/                ignored
  scripts/             read-only reference calls
  src/promptlab/
    adapters/          all provider knowledge lives here and nowhere else
    prompts/           prompt text, versioned, never edited after it produces a result
  tests/
```
