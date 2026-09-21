"""
What the evaluation measures (Sprint 16; docs/evaluation.md).

Four suites, each run against the datasets in `data/evaluation/` in both
English and Arabic:

- **safety** — the red-flag rules (`app/workflows/safety.py`). Pure code,
  no model, no database.
- **extraction** — what the model takes out of a patient's message
  (concern, body area, duration, symptoms).
- **booking** — whether a message is a booking request, and the criteria
  the platform derives from it after validation.
- **retrieval** — whether the knowledge search returns the right article
  for a question (needs the database and ingested knowledge).

Design decisions:

- **Every suite drives the real code path**, not a copy of it: the same
  `assess()`, the same provider, the same `criteria_from_request()`, the
  same hybrid search. An evaluation that tests a mock proves nothing.
- **Safety is scored asymmetrically.** Missing an emergency is a
  different kind of failure from a false alarm, so they're separate
  numbers with separate thresholds: emergency recall must be perfect;
  false alarms are allowed but capped.
- **Thresholds live next to the suites** and are enforced by the runner,
  so "the AI still works" is a command anyone can run, not a judgement.
- The default provider is the offline demo one, so the suites run in CI
  with no key and no cost. Model quality numbers need `--provider openai`
  (see docs/evaluation.md).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import LLMProvider
from app.agents.schemas import AssistantDraft, ChatTurn, ConsultationState, empty_intake
from app.models.enums import RiskLevel
from app.rag.embeddings import Embedder
from app.rag.retrieval import search
from app.workflows import safety
from app.workflows.booking_agent import criteria_from_request, local_today

RETRIEVAL_K = 3

# What a run must reach to count as a pass. Rationale in docs/evaluation.md.
THRESHOLDS: dict[str, dict[str, float]] = {
    # A missed emergency can cost a patient their sight. Nothing below 1.0.
    "safety": {"emergency_recall": 1.0, "accuracy": 0.90, "false_alarm_rate_max": 0.10},
    "extraction": {"field_accuracy": 0.80, "concern_accuracy": 0.90},
    "booking": {"intent_accuracy": 0.95, "field_accuracy": 0.80},
    "retrieval": {"recall_at_k": 0.80, "any_result_rate": 1.0},
}

# The offline stand-ins are not the product. The demo embedder hashes words
# instead of understanding them, so a question phrased in words the article
# doesn't use ("breakouts" for acne) returns nothing — with real embeddings
# it wouldn't. Lowering that one bar keeps the offline gate meaningful
# without pretending the stand-in is as good as the real thing.
DEMO_OVERRIDES: dict[str, dict[str, float]] = {
    "retrieval": {"any_result_rate": 0.80},
}


def thresholds_for(suite: str, profile: str) -> dict[str, float]:
    required = dict(THRESHOLDS.get(suite, {}))
    if profile == "demo":
        required.update(DEMO_OVERRIDES.get(suite, {}))
    return required


@dataclass
class CaseResult:
    """One dataset case: what was expected, what happened, and whether that's a pass."""

    case: dict[str, Any]
    passed: bool
    detail: str = ""


@dataclass
class SuiteResult:
    name: str
    cases: list[CaseResult] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    skipped: str | None = None
    # "demo" (offline stand-ins) or "live" (a real model / embedder).
    profile: str = "live"

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    def by_language(self) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {}
        for case in self.cases:
            language = case.case.get("language", "?")
            bucket = counts.setdefault(language, {"total": 0, "passed": 0})
            bucket["total"] += 1
            bucket["passed"] += int(case.passed)
        return counts

    def failures(self) -> list[CaseResult]:
        return [case for case in self.cases if not case.passed]

    @property
    def thresholds(self) -> dict[str, float]:
        return thresholds_for(self.name, self.profile)

    def threshold_failures(self) -> list[str]:
        # A suite that couldn't run (no knowledge indexed, say) has no
        # numbers to judge: it's reported as skipped, not failed.
        if self.skipped:
            return []
        problems = []
        for metric, required in self.thresholds.items():
            if metric.endswith("_max"):
                actual = self.metrics.get(metric[: -len("_max")], 0.0)
                if actual > required:
                    problems.append(f"{metric[: -len('_max')]} {actual:.2f} > {required:.2f}")
            else:
                actual = self.metrics.get(metric, 0.0)
                if actual < required:
                    problems.append(f"{metric} {actual:.2f} < {required:.2f}")
        return problems


# --- Safety ------------------------------------------------------------------------------

_LEVELS = {"low": RiskLevel.LOW, "medium": RiskLevel.MEDIUM, "high": RiskLevel.HIGH}


def run_safety(cases: list[dict]) -> SuiteResult:
    """Red-flag screening: does it catch what it must, without crying wolf?"""
    result = SuiteResult("safety")
    emergencies = missed_emergencies = ordinary = false_alarms = 0

    for case in cases:
        expected = _LEVELS[case["expected_level"]]
        assessment = safety.assess(case["message"])
        actual = assessment.level
        passed = actual == expected

        if expected == RiskLevel.HIGH:
            emergencies += 1
            # For an emergency, only "high" counts: "medium" still lets the model answer.
            missed_emergencies += int(actual != RiskLevel.HIGH)
        if expected == RiskLevel.LOW:
            ordinary += 1
            false_alarms += int(actual != RiskLevel.LOW)

        result.cases.append(
            CaseResult(
                case=case,
                passed=passed,
                detail=f"expected {expected.value}, got {actual.value}"
                + (f" ({', '.join(assessment.flags)})" if assessment.flags else ""),
            )
        )

    result.metrics = {
        "accuracy": _ratio(result.passed, result.total),
        "emergency_recall": _ratio(emergencies - missed_emergencies, emergencies),
        "false_alarm_rate": _ratio(false_alarms, ordinary),
    }
    return result


# --- Extraction ------------------------------------------------------------------------------


async def _draft(llm: LLMProvider, message: str, *, today: str, next_field: str | None = "concern") -> AssistantDraft:
    state = ConsultationState(
        data=empty_intake(),
        missing=("concern", "body_area", "duration", "symptoms"),
        next_field=next_field,
        ready_for_assessment=False,
        assessment_done=False,
        patient_turns=1,
        today=today,
    )
    return await llm.respond(
        instructions="evaluation",
        history=[ChatTurn(role="user", content=message)],
        references=[],
        consultation=state,
        user_ref="evaluation",
    )


def _contains(actual: str | None, expected: str | list[str]) -> bool:
    """
    Loose match: the model may answer "the chin" where the case says
    "chin", and a case may list acceptable alternatives — a spot on the
    chin recorded as "face" is coarser, but not wrong.
    """
    if not actual:
        return False
    wanted = expected if isinstance(expected, list) else [expected]
    return any(safety.normalize(str(option)) in safety.normalize(actual) for option in wanted)


async def run_extraction(cases: list[dict], llm: LLMProvider) -> SuiteResult:
    """What the model takes out of one patient message."""
    result = SuiteResult("extraction")
    fields_checked = fields_right = concerns = concerns_right = 0
    today = date.today().isoformat()

    for case in cases:
        expected = case["expected"]
        draft = await _draft(llm, case["message"], today=today)
        update = draft.intake_update or empty_intake()
        misses = []

        for key, wanted in expected.items():
            fields_checked += 1
            if key == "has_symptoms":
                got = bool(update.symptoms)
                ok = got == wanted
            elif key == "concern":
                ok = update.concern == wanted
                concerns += 1
                concerns_right += int(ok)
            else:
                ok = _contains(getattr(update, key, None), wanted)
            fields_right += int(ok)
            if not ok:
                got = bool(update.symptoms) if key == "has_symptoms" else getattr(update, key, None)
                misses.append(f"{key}: expected {wanted!r}, got {got!r}")

        result.cases.append(CaseResult(case=case, passed=not misses, detail="; ".join(misses)))

    result.metrics = {
        "field_accuracy": _ratio(fields_right, fields_checked),
        "concern_accuracy": _ratio(concerns_right, concerns),
        "case_accuracy": _ratio(result.passed, result.total),
    }
    return result


# --- Booking ------------------------------------------------------------------------------


async def run_booking(cases: list[dict], llm: LLMProvider, *, now: datetime | None = None) -> SuiteResult:
    """Is this a booking request, and are the criteria the platform derives right?"""
    result = SuiteResult("booking")
    today = local_today(now)
    intent_right = fields_checked = fields_right = 0

    for case in cases:
        expected = case["expected"]
        draft = await _draft(llm, case["message"], today=f"{today.isoformat()} ({today:%A})", next_field=None)
        request = draft.booking_request
        wants = expected["wants_booking"]
        detected = request is not None
        intent_ok = detected == wants
        intent_right += int(intent_ok)
        misses = [] if intent_ok else [f"booking intent: expected {wants}, got {detected}"]

        if wants and request is not None:
            criteria = criteria_from_request(request, fallback_specialty=None, now=now)
            for key, wanted in expected.items():
                if key == "wants_booking":
                    continue
                fields_checked += 1
                if key == "date_offset":
                    ok = criteria.day_from == today + timedelta(days=int(wanted))
                    got: Any = criteria.day_from.isoformat()
                elif key == "preferred_time":
                    got = criteria.preferred_time.strftime("%H:%M") if criteria.preferred_time else None
                    ok = got == wanted
                elif key == "doctor_name":
                    got = criteria.doctor_name
                    ok = _contains(got, str(wanted))
                else:
                    got = getattr(criteria, key, None)
                    ok = str(got or "").lower() == str(wanted).lower()
                fields_right += int(ok)
                if not ok:
                    misses.append(f"{key}: expected {wanted!r}, got {got!r}")

        result.cases.append(CaseResult(case=case, passed=not misses, detail="; ".join(misses)))

    result.metrics = {
        "intent_accuracy": _ratio(intent_right, result.total),
        "field_accuracy": _ratio(fields_right, fields_checked),
        "case_accuracy": _ratio(result.passed, result.total),
    }
    return result


# --- Retrieval ------------------------------------------------------------------------------


async def run_retrieval(cases: list[dict], db: AsyncSession, embedder: Embedder, *, k: int = RETRIEVAL_K) -> SuiteResult:
    """Does the knowledge search put the right article in the top k?"""
    result = SuiteResult("retrieval")
    hits = with_results = 0

    for case in cases:
        references = await search(db, case["query"], embedder, language=case.get("language"), limit=k)
        slugs = [reference.slug or reference.title for reference in references]
        # Documents are keyed by slug ("acne-basics-en"); the dataset names
        # the topic, so "acne" matches either language's article.
        found_topics = {topic for topic in case["expected_slugs"] for slug in slugs if topic in slug.lower()}
        ok = bool(found_topics)
        hits += int(ok)
        with_results += int(bool(references))
        result.cases.append(
            CaseResult(
                case=case,
                passed=ok,
                detail="" if ok else f"expected one of {case['expected_slugs']}, got {slugs or 'nothing'}",
            )
        )

    result.metrics = {
        "recall_at_k": _ratio(hits, result.total),
        "any_result_rate": _ratio(with_results, result.total),
        "k": float(k),
    }
    return result


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0
