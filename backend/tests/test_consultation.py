"""
Sprint 9: the consultation checklist (app/workflows/consultation.py) —
the platform, not the model, decides what to ask next and when a
preliminary assessment counts.
"""

from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from app.agents.llm import get_llm
from app.agents.schemas import AssistantDraft
from app.main import app
from app.workflows.consultation import MAX_INTAKE_TURNS, merge
from tests.ai_helpers import assessment, draft, intake
from tests.factories import register_patient


class SequenceLLM:
    """Returns scripted answers in order (repeating the last), recording what it was sent."""

    name, model = "scripted", "scripted-1"

    def __init__(self, *drafts: AssistantDraft) -> None:
        self.drafts, self.calls = list(drafts), []

    async def respond(self, *, instructions, history, references, consultation, user_ref):
        self.calls.append({"state": consultation, "instructions": instructions})
        return self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]


@pytest.fixture
def script() -> Iterator[callable]:
    def install(*drafts: AssistantDraft) -> SequenceLLM:
        llm = SequenceLLM(*drafts)
        app.dependency_overrides[get_llm] = lambda: llm
        return llm

    yield install
    app.dependency_overrides.pop(get_llm, None)


async def _start(client: AsyncClient) -> tuple[dict, str]:
    patient = await register_patient(client)
    conversation = (await client.post("/api/v1/conversations", headers=patient["headers"], json={"accept_ai_terms": True})).json()
    return patient, conversation["id"]


async def _say(client: AsyncClient, patient: dict, conversation_id: str, content: str) -> dict:
    resp = await client.post(f"/api/v1/conversations/{conversation_id}/chat", headers=patient["headers"], json={"content": content})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _intake(client: AsyncClient, patient: dict, conversation_id: str) -> dict | None:
    items = (await client.get(f"/api/v1/intakes?conversation_id={conversation_id}", headers=patient["headers"])).json()["items"]
    return items[0] if items else None


# --- Unit: merging ----------------------------------------------------------------


def test_merge_keeps_known_values_and_combines_lists() -> None:
    known = intake(concern="acne", body_area="face", symptoms=["itching"], tried=["cleanser"])
    merged = merge(known, intake(body_area=None, symptoms=["pain", "itching"], tried=[], duration="2 months"))
    assert merged.concern == "acne" and merged.body_area == "face"  # null never erases
    assert merged.symptoms == ["itching", "pain"]  # combined, no duplicates
    assert merged.tried == ["cleanser"]  # an empty list doesn't erase either
    assert merged.duration == "2 months"


def test_empty_symptom_list_is_an_answer() -> None:
    from app.workflows.consultation import missing_fields

    assert "symptoms" in missing_fields(intake(concern="acne", body_area="face", duration="1 month"))
    assert missing_fields(intake(concern="acne", body_area="face", duration="1 month", symptoms=[])) == ()


# --- Flow ------------------------------------------------------------------------


async def test_questions_follow_the_fixed_order_and_details_are_saved(client: AsyncClient, script) -> None:
    llm = script(draft(concern="acne", body_area="face"), draft(duration="3 months"), draft())
    patient, conversation_id = await _start(client)

    first = await _say(client, patient, conversation_id, "I have acne on my face")
    assert llm.calls[0]["state"].next_field == "concern"
    assert first["consultation"]["missing_fields"] == ["duration", "symptoms"]

    await _say(client, patient, conversation_id, "about 3 months")
    assert llm.calls[1]["state"].next_field == "duration"
    await _say(client, patient, conversation_id, "hmm")
    assert llm.calls[2]["state"].next_field == "symptoms"

    saved = await _intake(client, patient, conversation_id)
    assert saved["status"] == "in_progress" and saved["concern"] == "acne" and saved["body_area"] == "face"
    assert saved["structured_data"]["data"]["duration"] == "3 months"
    assert saved["missing_fields"] == ["symptoms"]


async def test_premature_assessment_is_dropped(client: AsyncClient, script) -> None:
    script(draft("It's probably acne, see a dermatologist.", assessment=assessment(), concern="acne"))
    patient, conversation_id = await _start(client)
    turn = await _say(client, patient, conversation_id, "I have acne")
    assert turn["suggestion"] is None
    assert turn["assistant_message"]["extra_data"]["assessment"] is None
    assert turn["consultation"]["status"] == "in_progress"
    assert (await _intake(client, patient, conversation_id))["structured_data"]["assessment"] is None


async def test_complete_checklist_accepts_the_assessment_once(client: AsyncClient, script) -> None:
    final = assessment(suggested_specialty="Aesthetic Medicine", summary="May be related to early signs of ageing.")
    llm = script(
        draft(concern="anti_aging", body_area="forehead", duration="1 year"),
        draft("Summary ...", assessment=final, symptoms=[]),
        draft("Another answer", assessment=assessment(suggested_specialty="Dermatology")),
    )
    patient, conversation_id = await _start(client)
    await _say(client, patient, conversation_id, "Fine lines on my forehead for a year")
    done = await _say(client, patient, conversation_id, "No other symptoms")

    assert done["consultation"]["status"] == "complete" and done["consultation"]["missing_fields"] == []
    assert done["suggestion"] == {"specialty": "Aesthetic Medicine", "concern": "anti_aging"}
    assert done["assistant_message"]["extra_data"]["assessment"]["summary"] == final.summary
    saved = await _intake(client, patient, conversation_id)
    assert saved["status"] == "complete" and saved["structured_data"]["assessment"]["suggested_specialty"] == "Aesthetic Medicine"

    later = await _say(client, patient, conversation_id, "Thanks, one more question")
    assert llm.calls[-1]["state"].assessment_done is True
    assert later["suggestion"] is None  # a second assessment is ignored...
    saved = await _intake(client, patient, conversation_id)
    assert saved["structured_data"]["assessment"]["suggested_specialty"] == "Aesthetic Medicine"  # ...and never overwrites


async def test_turn_limit_allows_an_assessment_with_details_missing(client: AsyncClient, script) -> None:
    llm = script(draft("Could you tell me more?", assessment=assessment()))
    patient, conversation_id = await _start(client)
    turns = [await _say(client, patient, conversation_id, "I don't know") for _ in range(MAX_INTAKE_TURNS)]
    assert all(t["suggestion"] is None for t in turns[:-1])
    assert llm.calls[-1]["state"].ready_for_assessment is True
    assert turns[-1]["suggestion"] == {"specialty": "Dermatology", "concern": None}


async def test_pregnancy_from_safety_rules_is_recorded_and_told_to_the_model(client: AsyncClient, script) -> None:
    llm = script(draft(concern="pigmentation"))
    patient, conversation_id = await _start(client)
    await _say(client, patient, conversation_id, "I'm pregnant and have brown patches")
    assert llm.calls[0]["state"].data.pregnancy_or_breastfeeding is True
    assert any("pregnant" in note for note in llm.calls[0]["state"].notes)
    assert (await _intake(client, patient, conversation_id))["structured_data"]["data"]["pregnancy_or_breastfeeding"] is True


async def test_urgent_assessment_raises_the_safety_level(client: AsyncClient, script) -> None:
    script(draft(assessment=assessment(urgency="urgent"), concern="other", body_area="arm", duration="2 days", symptoms=["spreading"]))
    patient, conversation_id = await _start(client)
    turn = await _say(client, patient, conversation_id, "A patch on my arm spreading for 2 days")
    assert turn["safety_level"] == "medium"
    assert turn["assistant_message"]["extra_data"]["assessment"]["urgency"] == "urgent"


async def test_emergencies_create_no_intake(client: AsyncClient, script) -> None:
    llm = script(draft())
    patient, conversation_id = await _start(client)
    turn = await _say(client, patient, conversation_id, "I can't breathe after my filler")
    assert turn["consultation"] is None and llm.calls == []
    assert await _intake(client, patient, conversation_id) is None


async def test_demo_consultation_in_arabic(client: AsyncClient) -> None:
    """No override: the offline demo provider runs the whole checklist."""
    patient, conversation_id = await _start(client)
    await _say(client, patient, conversation_id, "عندي حبوب في وشي")
    await _say(client, patient, conversation_id, "بقالها سنتين")
    done = await _say(client, patient, conversation_id, "مفيش أعراض تانية")
    assert done["consultation"]["status"] == "complete"
    assert done["suggestion"]["specialty"] == "Dermatology"
    summary = done["assistant_message"]["extra_data"]["assessment"]["summary"]
    assert "حب الشباب" in summary and "مش تشخيص" in summary
