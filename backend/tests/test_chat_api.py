"""
Sprint 7: patient AI chat — consent, safety-first ordering, model output
handling, privacy, limits and access.

`ScriptedLLM` replaces the model (FastAPI dependency override), so each
test controls the model's answer and can assert what the model was sent,
or that it wasn't called at all.
"""

from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from app.agents.llm import LLMError, get_llm
from tests.ai_helpers import assessment, draft
from app.core.config import get_settings
from app.main import app
from tests.factories import make_doctor_user, register_patient


class ScriptedLLM:
    name = "scripted"
    model = "scripted-1"

    def __init__(self, fail: bool = False) -> None:
        self.draft = draft(concern="acne")
        self.fail = fail
        self.calls: list[dict] = []

    async def respond(self, *, instructions, history, references, consultation, user_ref):
        self.calls.append({"instructions": instructions, "history": history, "references": references,
                           "consultation": consultation, "user_ref": user_ref})
        if self.fail:
            raise LLMError("boom")
        return self.draft


@pytest.fixture
def llm() -> Iterator[ScriptedLLM]:
    scripted = ScriptedLLM()
    app.dependency_overrides[get_llm] = lambda: scripted
    yield scripted
    app.dependency_overrides.pop(get_llm, None)


async def _start(client: AsyncClient, patient: dict) -> str:
    resp = await client.post("/api/v1/conversations", headers=patient["headers"], json={"accept_ai_terms": True, "language": "en"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _say(client: AsyncClient, patient: dict, conversation_id: str, content: str):
    return await client.post(f"/api/v1/conversations/{conversation_id}/chat", headers=patient["headers"], json={"content": content})


# --- Consent -------------------------------------------------------------------


async def test_first_conversation_requires_accepting_ai_terms(client: AsyncClient) -> None:
    patient = await register_patient(client)
    refused = await client.post("/api/v1/conversations", headers=patient["headers"], json={})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "consent_required"

    await _start(client, patient)
    # Accepted once: later conversations don't ask again.
    again = await client.post("/api/v1/conversations", headers=patient["headers"], json={})
    assert again.status_code == 201


# --- Normal turns ------------------------------------------------------------------


async def test_demo_mode_conversation_reaches_a_specialty_suggestion(client: AsyncClient) -> None:
    """No override: the offline demo provider answers (local/test default)."""
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    messages = ("Hi", "I have acne on my chin", "6 months, tried a cleanser", "No other symptoms")
    turns = [await _say(client, patient, conversation_id, m) for m in messages]
    assert all(t.status_code == 200 for t in turns)
    assert {t.json()["ai_mode"] for t in turns} == {"demo"}
    assert [t.json()["consultation"]["missing_fields"] for t in turns] == [
        ["concern", "body_area", "duration", "symptoms"], ["duration", "symptoms"], ["symptoms"], [],
    ]
    assert all(t.json()["suggestion"] is None for t in turns[:3])
    assert turns[-1].json()["suggestion"] == {"specialty": "Dermatology", "concern": "acne"}
    assert turns[-1].json()["consultation"]["status"] == "complete"

    history = (await client.get(f"/api/v1/conversations/{conversation_id}", headers=patient["headers"])).json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"] * 4


async def test_reply_metadata_is_traceable(client: AsyncClient, llm: ScriptedLLM) -> None:
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    body = (await _say(client, patient, conversation_id, "I have acne")).json()
    extra = body["assistant_message"]["extra_data"]
    assert extra["kind"] == "reply"
    assert extra["ai"] == {"provider": "scripted", "model": "scripted-1", "prompt_version": extra["ai"]["prompt_version"]}
    assert extra["ai"]["prompt_version"].startswith("chat-")


# --- Safety ----------------------------------------------------------------------


async def test_emergency_never_reaches_the_model(client: AsyncClient, admin_client: AsyncClient, llm: ScriptedLLM) -> None:
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    resp = await _say(client, patient, conversation_id, "I had filler yesterday and the skin turned white and it hurts a lot")
    body = resp.json()

    assert resp.status_code == 200
    assert llm.calls == []  # the model was never asked
    assert "123" in body["assistant_message"]["content"]
    assert body["assistant_message"]["extra_data"]["kind"] == "emergency"
    assert body["safety_level"] == "high" and body["conversation_status"] == "escalated"
    assert body["suggestion"] is None

    events = (await admin_client.get("/api/v1/safety-events?requires_human=true&resolved=false&page_size=100")).json()["items"]
    mine = [e for e in events if e["conversation_id"] == conversation_id]
    assert len(mine) == 1 and mine[0]["red_flags"] == [{"source": "rules", "rule": "skin_colour_after_filler"}]


async def test_emergency_reply_matches_the_patients_language(client: AsyncClient, llm: ScriptedLLM) -> None:
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    body = (await _say(client, patient, conversation_id, "مش قادرة اتنفس بعد الحقن")).json()
    assert "الإسعاف" in body["assistant_message"]["content"] and "123" in body["assistant_message"]["content"]


async def test_caution_is_appended_in_code_and_model_is_told(client: AsyncClient, llm: ScriptedLLM) -> None:
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    body = (await _say(client, patient, conversation_id, "I'm pregnant, is botox safe?")).json()

    assert "pregnancy" in llm.calls[0]["instructions"]
    content = body["assistant_message"]["content"]
    assert content.startswith(llm.draft.reply)
    assert "pregnancy or breastfeeding" in content  # fixed caution, not model text
    assert body["safety_level"] == "medium" and body["conversation_status"] == "active"


async def test_model_high_risk_escalates_and_suppresses_booking(client: AsyncClient, admin_client: AsyncClient, llm: ScriptedLLM) -> None:
    llm.draft = draft("This sounds urgent.", risk_level="high", assessment=assessment(), concern="other",
                      body_area="face", duration="1 day", symptoms=["pain"])
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    body = (await _say(client, patient, conversation_id, "my face feels strange since this morning")).json()

    assert body["conversation_status"] == "escalated" and body["safety_level"] == "high"
    assert body["suggestion"] is None
    assert "123" in body["assistant_message"]["content"]
    events = (await admin_client.get("/api/v1/safety-events?requires_human=true&page_size=100")).json()["items"]
    assert any(e["conversation_id"] == conversation_id and e["red_flags"] == [{"source": "model"}] for e in events)


async def test_model_failure_degrades_gracefully(client: AsyncClient, llm: ScriptedLLM) -> None:
    llm.fail = True
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    resp = await _say(client, patient, conversation_id, "I have acne")
    assert resp.status_code == 200
    assert resp.json()["degraded"] is True
    assert "try again" in resp.json()["assistant_message"]["content"]
    # The patient's message was saved before the model call.
    messages = (await client.get(f"/api/v1/conversations/{conversation_id}", headers=patient["headers"])).json()["messages"]
    assert messages[0]["content"] == "I have acne"


# --- Privacy & context --------------------------------------------------------------


async def test_model_receives_only_message_text_and_an_anonymous_ref(client: AsyncClient, llm: ScriptedLLM) -> None:
    patient = await register_patient(client, full_name="Sara Ahmed")
    conversation_id = await _start(client, patient)
    await _say(client, patient, conversation_id, "I have acne")
    call = llm.calls[0]
    sent = call["instructions"] + " ".join(t.content for t in call["history"]) + call["user_ref"]
    for private in ("Sara", patient["user"]["email"], patient["user"]["phone"], patient["user"]["id"]):
        assert private not in sent
    assert [(t.role, t.content) for t in call["history"]] == [("user", "I have acne")]


async def test_history_sent_to_model_is_capped(client: AsyncClient, llm: ScriptedLLM) -> None:
    settings = get_settings()
    original = settings.chat_history_messages
    settings.chat_history_messages = 4
    try:
        patient = await register_patient(client)
        conversation_id = await _start(client, patient)
        for i in range(4):
            await _say(client, patient, conversation_id, f"message {i}")
        assert len(llm.calls[-1]["history"]) == 4
        assert llm.calls[-1]["history"][-1].content == "message 3"
    finally:
        settings.chat_history_messages = original


# --- Limits & access ------------------------------------------------------------------


async def test_message_length_limit(client: AsyncClient, llm: ScriptedLLM) -> None:
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    too_long = "a" * (get_settings().chat_max_message_chars + 1)
    assert (await _say(client, patient, conversation_id, too_long)).status_code == 422
    assert (await _say(client, patient, conversation_id, "   ")).status_code == 422


async def test_hourly_message_limit(client: AsyncClient, llm: ScriptedLLM) -> None:
    settings = get_settings()
    original = settings.chat_messages_per_hour
    settings.chat_messages_per_hour = 2
    try:
        patient = await register_patient(client)
        conversation_id = await _start(client, patient)
        assert (await _say(client, patient, conversation_id, "one")).status_code == 200
        assert (await _say(client, patient, conversation_id, "two")).status_code == 200
        limited = await _say(client, patient, conversation_id, "three")
        assert limited.status_code == 429 and limited.json()["error"]["code"] == "rate_limited"
    finally:
        settings.chat_messages_per_hour = original


async def test_only_the_owning_patient_can_chat(client: AsyncClient, admin_client: AsyncClient, llm: ScriptedLLM) -> None:
    owner, other = await register_patient(client), await register_patient(client)
    conversation_id = await _start(client, owner)
    _, doctor_headers = await make_doctor_user(admin_client)
    path = f"/api/v1/conversations/{conversation_id}/chat"
    assert (await client.post(path, headers=other["headers"], json={"content": "hi"})).status_code == 404
    assert (await client.post(path, headers=doctor_headers, json={"content": "hi"})).status_code == 403
    assert (await admin_client.post(path, json={"content": "hi"})).status_code == 403
    assert (await client.post(path, json={"content": "hi"})).status_code == 401


async def test_completed_conversation_is_closed(client: AsyncClient, admin_client: AsyncClient, llm: ScriptedLLM) -> None:
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    await admin_client.patch(f"/api/v1/conversations/{conversation_id}", json={"status": "completed"})
    assert (await _say(client, patient, conversation_id, "hello")).status_code == 409


async def test_admin_resolves_safety_events(client: AsyncClient, admin_client: AsyncClient, llm: ScriptedLLM) -> None:
    patient = await register_patient(client)
    conversation_id = await _start(client, patient)
    await _say(client, patient, conversation_id, "I want to kill myself")
    events = (await admin_client.get("/api/v1/safety-events?requires_human=true&resolved=false&page_size=100")).json()["items"]
    event = next(e for e in events if e["conversation_id"] == conversation_id)

    resolved = await admin_client.patch(f"/api/v1/safety-events/{event['id']}", json={"resolved": True, "notes": "Called patient"})
    assert resolved.status_code == 200 and resolved.json()["resolved_at"] and resolved.json()["notes"] == "Called patient"
    assert (await client.get("/api/v1/safety-events", headers=patient["headers"])).status_code == 403
