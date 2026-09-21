"""Sprint 16: the evaluation harness — datasets, metrics, thresholds, and the suites themselves."""

import json
from pathlib import Path

import pytest

from app.agents.demo_llm import DemoProvider
from app.evaluation import datasets, report
from app.evaluation.suites import (
    DEMO_OVERRIDES,
    THRESHOLDS,
    CaseResult,
    SuiteResult,
    run_booking,
    run_extraction,
    run_safety,
    thresholds_for,
)


# --- The datasets themselves ------------------------------------------------------------------


def test_every_suite_has_a_valid_bilingual_dataset() -> None:
    for suite in datasets.SUITES:
        cases = datasets.load(suite)
        assert cases, f"{suite} dataset is empty"
        assert datasets.check_coverage(suite, cases) == [], f"{suite} dataset has gaps"
        # Both languages, not one token case in the other.
        counts = {language: sum(1 for case in cases if case["language"] == language) for language in ("en", "ar")}
        assert min(counts.values()) >= 4, f"{suite}: thin language coverage {counts}"


def test_the_safety_dataset_covers_the_cases_that_matter() -> None:
    cases = datasets.load("safety")
    levels = [case["expected_level"] for case in cases]
    # Emergencies in both languages, and enough ordinary messages to measure false alarms.
    assert levels.count("high") >= 10
    assert levels.count("low") >= 10
    emergencies = {case["language"] for case in cases if case["expected_level"] == "high"}
    assert emergencies == {"en", "ar"}


def test_a_malformed_dataset_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "safety.jsonl").write_text('{"message": "hi"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        datasets.load("safety", tmp_path)

    (tmp_path / "safety.jsonl").write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        datasets.load("safety", tmp_path)

    with pytest.raises(FileNotFoundError):
        datasets.load("safety", tmp_path / "nowhere")


def test_missing_languages_are_reported(tmp_path: Path) -> None:
    cases = [{"message": "acne", "expected_level": "low", "language": "en"}]
    problems = datasets.check_coverage("safety", cases)
    assert any("ar" in problem for problem in problems)
    assert any("high" in problem for problem in problems)


# --- Metrics and thresholds --------------------------------------------------------------------


def test_safety_scores_misses_and_false_alarms_separately() -> None:
    cases = [
        # A real emergency the rules catch.
        {"message": "I can't breathe and my face is swelling", "expected_level": "high", "language": "en"},
        # An ordinary question they must leave alone.
        {"message": "How much does botox cost?", "expected_level": "low", "language": "en"},
        # An emergency worded so the rules can't see it: a miss, by construction.
        {"message": "something feels very wrong since yesterday", "expected_level": "high", "language": "en"},
    ]
    result = run_safety(cases)
    assert result.total == 3
    assert result.metrics["emergency_recall"] == 0.5  # one of two emergencies caught
    assert result.metrics["false_alarm_rate"] == 0.0
    assert "emergency_recall 0.50 < 1.00" in " ".join(result.threshold_failures())


def test_a_missed_emergency_always_fails_the_run() -> None:
    """The one number that has no acceptable shortfall."""
    assert THRESHOLDS["safety"]["emergency_recall"] == 1.0
    assert "emergency_recall" not in DEMO_OVERRIDES.get("safety", {})

    result = SuiteResult("safety", metrics={"emergency_recall": 0.99, "accuracy": 1.0, "false_alarm_rate": 0.0})
    assert result.threshold_failures()


def test_thresholds_are_relaxed_only_for_the_offline_stand_ins() -> None:
    live = thresholds_for("retrieval", "live")
    demo = thresholds_for("retrieval", "demo")
    assert demo["any_result_rate"] < live["any_result_rate"]
    # Safety is platform code: the same bar either way.
    assert thresholds_for("safety", "demo") == thresholds_for("safety", "live")


def test_a_maximum_threshold_fails_when_exceeded() -> None:
    noisy = SuiteResult("safety", metrics={"emergency_recall": 1.0, "accuracy": 1.0, "false_alarm_rate": 0.5})
    assert any("false_alarm_rate" in problem for problem in noisy.threshold_failures())
    quiet = SuiteResult("safety", metrics={"emergency_recall": 1.0, "accuracy": 1.0, "false_alarm_rate": 0.0})
    assert quiet.threshold_failures() == []


def test_results_break_down_by_language() -> None:
    result = SuiteResult(
        "safety",
        cases=[
            CaseResult({"language": "en"}, True),
            CaseResult({"language": "ar"}, False),
            CaseResult({"language": "ar"}, True),
        ],
    )
    assert result.by_language() == {"en": {"total": 1, "passed": 1}, "ar": {"total": 2, "passed": 1}}
    assert len(result.failures()) == 1


# --- The suites, against the real code ----------------------------------------------------------


def test_the_safety_suite_passes_on_the_shipped_rules() -> None:
    """The rules must clear every case in the dataset — this is the release gate."""
    result = run_safety(datasets.load("safety"))
    assert result.threshold_failures() == [], [f.detail for f in result.failures()]
    assert result.metrics["emergency_recall"] == 1.0
    assert result.metrics["false_alarm_rate"] == 0.0


async def test_the_extraction_and_booking_suites_run_against_the_demo_provider() -> None:
    llm = DemoProvider()

    extraction = await run_extraction(datasets.load("extraction"), llm)
    extraction.profile = "demo"
    assert extraction.total > 0
    assert extraction.threshold_failures() == [], [f.detail for f in extraction.failures()]

    booking = await run_booking(datasets.load("booking"), llm)
    booking.profile = "demo"
    assert booking.metrics["intent_accuracy"] == 1.0
    assert booking.threshold_failures() == [], [f.detail for f in booking.failures()]


# --- Reporting ------------------------------------------------------------------------------


def test_the_report_carries_the_numbers_and_the_failures(tmp_path: Path) -> None:
    results = [run_safety(datasets.load("safety")[:4])]
    path = tmp_path / "report.json"
    report.write(results, path, provider="demo", model="demo-rules-v5")

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["provider"] == "demo"
    suite = saved["suites"][0]
    assert suite["name"] == "safety"
    assert suite["total"] == 4
    assert "emergency_recall" in suite["metrics"]
    assert "thresholds" in suite and "by_language" in suite

    summary = report.summarise(results, provider="demo", model="demo-rules-v5")
    assert "safety" in summary
    assert "RESULT:" in summary


def test_the_summary_says_which_thresholds_failed() -> None:
    failing = SuiteResult("safety", metrics={"emergency_recall": 0.5, "accuracy": 0.5, "false_alarm_rate": 0.0})
    failing.cases = [CaseResult({"language": "en", "message": "help"}, False, "expected high, got low")]
    summary = report.summarise([failing], provider="demo", model="demo")
    assert "RESULT: FAILED" in summary
    assert "emergency_recall" in summary
    assert "expected high, got low" in summary


def test_a_skipped_suite_is_shown_as_skipped() -> None:
    skipped = SuiteResult("retrieval")
    skipped.skipped = "no approved knowledge indexed"
    summary = report.summarise([skipped], provider="demo", model="demo")
    assert "skipped" in summary
    # A skipped suite has nothing to fail on, so it can't fail the run.
    assert "RESULT: PASSED" in summary
