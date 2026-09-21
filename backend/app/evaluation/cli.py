"""
Run the AI evaluation (Sprint 16; docs/evaluation.md).

    python -m app.evaluation.cli run                    # every suite
    python -m app.evaluation.cli run --suite safety     # one suite
    python -m app.evaluation.cli run --report out.json  # machine-readable report
    python -m app.evaluation.cli check                  # validate the datasets only

Exits non-zero when a threshold isn't met, so it can gate a release.

By default it uses whatever AI provider is configured (`AI_PROVIDER`,
"demo" locally). The demo provider is rule-based, so a demo run measures
the platform's own layers — red-flag rules, criteria validation,
retrieval — rather than a model's judgement. Use `AI_PROVIDER=openai` for
that (costs money, needs a key).
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app.agents.llm import get_llm
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal
from app.evaluation import datasets, report
from app.evaluation.suites import SuiteResult, run_booking, run_extraction, run_retrieval, run_safety
from app.rag.embeddings import get_embedder
from app.rag.retrieval import index_is_empty


async def run(suites: list[str]) -> tuple[list[SuiteResult], str, str]:
    llm = get_llm()
    embedder = get_embedder()
    results: list[SuiteResult] = []
    # Which bar to hold each suite to: the offline stand-ins can't be judged
    # by the same numbers as a real model (see suites.DEMO_OVERRIDES).
    profiles = {
        "safety": "live",  # pure platform code, no stand-in involved
        "extraction": "demo" if llm.name == "demo" else "live",
        "booking": "demo" if llm.name == "demo" else "live",
        "retrieval": "demo" if "demo" in embedder.model else "live",
    }

    for suite in suites:
        cases = datasets.load(suite)
        if suite == "safety":
            results.append(run_safety(cases))
        elif suite == "extraction":
            results.append(await run_extraction(cases, llm))
        elif suite == "booking":
            results.append(await run_booking(cases, llm))
        elif suite == "retrieval":
            async with AsyncSessionLocal() as db:
                if await index_is_empty(db):
                    skipped = SuiteResult("retrieval")
                    skipped.skipped = "no approved knowledge indexed (run: python -m app.rag.cli ingest --approve …)"
                    results.append(skipped)
                else:
                    results.append(await run_retrieval(cases, db, embedder))
        results[-1].profile = profiles[suite]
    return results, llm.name, llm.model


def check_datasets(suites: list[str]) -> list[str]:
    problems = []
    for suite in suites:
        try:
            cases = datasets.load(suite)
        except (FileNotFoundError, ValueError) as exc:
            problems.append(str(exc))
            continue
        problems.extend(datasets.check_coverage(suite, cases))
        print(f"{suite:<12} {len(cases):>3} cases  ({', '.join(sorted(datasets.languages(cases)))})")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the AI features against the saved datasets")
    parser.add_argument("command", choices=["run", "check"])
    parser.add_argument("--suite", choices=[*datasets.SUITES, "all"], default="all")
    parser.add_argument("--report", type=Path, help="Write a JSON report here")
    parser.add_argument("--quiet", action="store_true", help="Only the summary lines, no failing cases")
    args = parser.parse_args()

    configure_logging()
    suites = list(datasets.SUITES) if args.suite == "all" else [args.suite]

    if args.command == "check":
        problems = check_datasets(suites)
        for problem in problems:
            print(f"✗ {problem}")
        sys.exit(1 if problems else 0)

    results, provider, model = asyncio.run(run(suites))
    print(report.summarise(results, provider=provider, model=model, show_failures=not args.quiet))
    if args.report:
        report.write(results, args.report, provider=provider, model=model)
        print(f"\nReport written to {args.report}")

    sys.exit(1 if any(result.threshold_failures() for result in results) else 0)


if __name__ == "__main__":
    main()
