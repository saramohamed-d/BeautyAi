"""Turning suite results into something a person reads and a CI job can gate on (Sprint 16)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.evaluation.suites import SuiteResult

BAR_WIDTH = 24


def to_dict(results: list[SuiteResult], *, provider: str, model: str) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "suites": [
            {
                "name": result.name,
                "skipped": result.skipped,
                "total": result.total,
                "passed": result.passed,
                "metrics": result.metrics,
                "profile": result.profile,
                "thresholds": result.thresholds,
                "threshold_failures": result.threshold_failures(),
                "by_language": result.by_language(),
                "failures": [
                    {
                        "input": failure.case.get("message") or failure.case.get("query"),
                        "language": failure.case.get("language"),
                        "detail": failure.detail,
                    }
                    for failure in result.failures()
                ],
            }
            for result in results
        ],
    }


def write(results: list[SuiteResult], path: Path, *, provider: str, model: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(results, provider=provider, model=model), indent=2, ensure_ascii=False))


def summarise(results: list[SuiteResult], *, provider: str, model: str, show_failures: bool = True) -> str:
    """A short report: the numbers, which thresholds failed, and what failed."""
    profiles = {result.profile for result in results}
    note = " — offline stand-ins, see docs/evaluation.md" if profiles == {"demo"} else ""
    lines = [f"AI evaluation — provider: {provider} ({model}){note}", ""]

    for result in results:
        if result.skipped:
            lines.append(f"{result.name:<12} skipped — {result.skipped}")
            continue
        share = result.passed / result.total if result.total else 0.0
        filled = round(share * BAR_WIDTH)
        languages = " ".join(
            f"{language}:{counts['passed']}/{counts['total']}" for language, counts in sorted(result.by_language().items())
        )
        lines.append(
            f"{result.name:<12} {'█' * filled}{'░' * (BAR_WIDTH - filled)} "
            f"{result.passed:>3}/{result.total:<3} ({share:.0%})   {languages}"
        )
        metrics = "  ".join(f"{name}={value:.2f}" for name, value in result.metrics.items())
        lines.append(f"{'':<12} {metrics}")
        for problem in result.threshold_failures():
            lines.append(f"{'':<12} ✗ below threshold: {problem}")
        lines.append("")

    if show_failures:
        for result in results:
            failures = result.failures()
            if not failures:
                continue
            lines.append(f"{result.name} — {len(failures)} case(s) failed:")
            for failure in failures[:10]:
                text = failure.case.get("message") or failure.case.get("query") or ""
                lines.append(f"  [{failure.case.get('language', '?')}] {text[:70]}")
                lines.append(f"      {failure.detail}")
            if len(failures) > 10:
                lines.append(f"  … and {len(failures) - 10} more (see the JSON report)")
            lines.append("")

    failed = [problem for result in results for problem in result.threshold_failures()]
    lines.append("RESULT: FAILED — " + "; ".join(failed) if failed else "RESULT: PASSED — every threshold met")
    return "\n".join(lines)
