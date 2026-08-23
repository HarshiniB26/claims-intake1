from promptlab.corpus import load_cases, validate_corpus


def test_each_task_has_twelve_cases_and_matching_gold() -> None:
    assert validate_corpus() == {
        "triage": 12,
        "summarization": 12,
        "extraction": 12,
    }


def test_case_ids_are_unique_across_corpus() -> None:
    ids: list[str] = []
    for task in ("triage", "summarization", "extraction"):
        ids.extend(case.id for case, _gold in load_cases(task))
    assert len(ids) == len(set(ids))

