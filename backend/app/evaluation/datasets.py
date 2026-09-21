"""
Loading and checking the evaluation datasets (Sprint 16).

The datasets are hand-written JSONL under `data/evaluation/`, one file
per suite. They're part of the repository, reviewed like code: a change
to what the platform is expected to do should show up in a diff.
"""

import json
from pathlib import Path

SUITES = ("safety", "extraction", "booking", "retrieval")
# Every suite must exercise both languages: the platform is bilingual, and
# a suite that quietly became English-only would flatter the numbers.
REQUIRED_LANGUAGES = {"en", "ar"}

_REQUIRED_KEYS = {
    "safety": ("message", "expected_level", "language"),
    "extraction": ("message", "expected", "language"),
    "booking": ("message", "expected", "language"),
    "retrieval": ("query", "expected_slugs", "language"),
}


def default_dataset_dir() -> Path:
    # backend/app/evaluation/datasets.py -> repository root -> data/evaluation
    return Path(__file__).resolve().parents[3] / "data" / "evaluation"


def load(suite: str, directory: Path | None = None) -> list[dict]:
    path = (directory or default_dataset_dir()) / f"{suite}.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"No dataset for suite '{suite}' at {path}")
    cases = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} line {number}: {exc}") from exc
        missing = [key for key in _REQUIRED_KEYS[suite] if key not in case]
        if missing:
            raise ValueError(f"{path.name} line {number}: missing {', '.join(missing)}")
        cases.append(case)
    if not cases:
        raise ValueError(f"{path.name} has no cases")
    return cases


def languages(cases: list[dict]) -> set[str]:
    return {case.get("language", "?") for case in cases}


def check_coverage(suite: str, cases: list[dict]) -> list[str]:
    """Complaints about the dataset itself, rather than about the platform."""
    problems = []
    missing = REQUIRED_LANGUAGES - languages(cases)
    if missing:
        problems.append(f"{suite}: no cases in {', '.join(sorted(missing))}")
    if suite == "safety":
        levels = {case["expected_level"] for case in cases}
        for level in ("high", "medium", "low"):
            if level not in levels:
                problems.append(f"safety: no '{level}' cases")
    return problems
