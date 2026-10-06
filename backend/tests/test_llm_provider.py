"""
OpenAIProvider (Sprint 7) and OllamaProvider request shape and error handling, without
network access (the SDK client is replaced by a stub).
"""

import json
import uuid
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.agents.llm import AssistantDraft, ChatTurn, LLMError, OllamaProvider, OpenAIProvider
from app.agents.schemas import empty_intake
from app.rag.types import Reference
from app.workflows.consultation import build_state
from tests.ai_helpers import draft

DRAFT = draft("Hi")
STATE = build_state(empty_intake(), patient_turns=1, assessment_done=False)
REFERENCE = Reference(
    chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), slug="acne-basics-en", title="Acne: the basics",
    heading="What acne is",
    content="Acne happens when pores clog.", language="en", source="BeautyAI editorial draft", url=None,
    score=0.03, similarity=0.5,
)


class StubResponses:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result, self.error, self.kwargs = result, error, None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.result


def _provider(stub: StubResponses) -> OpenAIProvider:
    provider = OpenAIProvider(api_key="test-key", model="test-model", timeout=5)
    provider._client = SimpleNamespace(responses=stub)
    return provider


async def test_request_uses_structured_output_without_provider_storage() -> None:
    stub = StubResponses(result=SimpleNamespace(output_parsed=DRAFT, status="completed"))
    history = [ChatTurn(role="user", content="I have acne"), ChatTurn(role="assistant", content="Since when?")]

    assert await _provider(stub).respond(instructions="RULES", history=history, references=[], consultation=STATE, user_ref="abc123") == DRAFT
    sent = stub.kwargs
    assert sent["model"] == "test-model"
    assert sent["instructions"] == "RULES"
    *turns, state = sent["input"]
    assert turns == [{"role": "user", "content": "I have acne"}, {"role": "assistant", "content": "Since when?"}]
    assert state["role"] == "developer" and "Ask next about: concern" in state["content"]
    assert sent["text_format"] is AssistantDraft
    assert sent["store"] is False
    assert sent["safety_identifier"] == "abc123"


async def test_references_go_in_a_separate_developer_message() -> None:
    stub = StubResponses(result=SimpleNamespace(output_parsed=DRAFT, status="completed"))
    history = [ChatTurn(role="user", content="I have acne")]
    await _provider(stub).respond(instructions="RULES", history=history, references=[REFERENCE], consultation=STATE, user_ref="x")

    assert stub.kwargs["instructions"] == "RULES"  # unchanged, so it stays cacheable
    *turns, state, library = stub.kwargs["input"]
    assert turns == [{"role": "user", "content": "I have acne"}]
    assert state["role"] == "developer" and state["content"].startswith("Consultation state")
    assert library["role"] == "developer"
    assert "[1] Acne: the basics — What acne is" in library["content"]
    assert "Acne happens when pores clog." in library["content"]


async def test_refusal_or_empty_output_is_an_llm_error() -> None:
    stub = StubResponses(result=SimpleNamespace(output_parsed=None, status="incomplete"))
    with pytest.raises(LLMError):
        await _provider(stub).respond(instructions="", history=[], references=[], consultation=STATE, user_ref="x")


async def test_api_errors_become_llm_errors() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    stub = StubResponses(error=openai.APITimeoutError(request=request))
    with pytest.raises(LLMError):
        await _provider(stub).respond(instructions="", history=[], references=[], consultation=STATE, user_ref="x")


# --- OllamaProvider ----------------------------------------------------------------------


def _ollama(handler) -> OllamaProvider:
    provider = OllamaProvider(base_url="http://ollama.test", model="qwen2.5:3b", timeout=5, num_ctx=4096)
    provider._client = httpx.AsyncClient(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    return provider


async def test_ollama_sends_the_draft_schema_and_parses_the_reply() -> None:
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": DRAFT.model_dump_json()}})

    history = [ChatTurn(role="user", content="I have acne")]
    result = await _ollama(handler).respond(
        instructions="RULES", history=history, references=[REFERENCE], consultation=STATE, user_ref="abc123"
    )

    assert result == DRAFT
    assert sent["model"] == "qwen2.5:3b"
    assert sent["format"] == AssistantDraft.model_json_schema()
    assert sent["stream"] is False
    assert sent["messages"][0] == {"role": "system", "content": "RULES"}
    assert sent["messages"][1] == {"role": "user", "content": "I have acne"}
    assert "Ask next about: concern" in sent["messages"][2]["content"]
    assert "Acne: the basics" in sent["messages"][3]["content"]
    # Only message text is sent, never the user reference.
    assert "abc123" not in json.dumps(sent)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="model not found"),
        httpx.Response(200, json={"message": {"content": "not json"}}),
        httpx.Response(200, json={"message": {"content": '{"reply": "hi"}'}}),
    ],
)
async def test_ollama_failures_become_llm_errors(response: httpx.Response) -> None:
    with pytest.raises(LLMError):
        await _ollama(lambda request: response).respond(
            instructions="RULES", history=[], references=[], consultation=STATE, user_ref="abc123"
        )


async def test_ollama_unreachable_is_an_llm_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMError):
        await _ollama(handler).respond(instructions="RULES", history=[], references=[], consultation=STATE, user_ref="x")


@pytest.mark.parametrize(
    ("message", "language", "keeps_dialect_guidance"),
    [("I have acne on my cheeks", "English", False), ("عندي حبوب في وشي", "Arabic", True)],
)
async def test_ollama_pins_the_reply_language(message: str, language: str, keeps_dialect_guidance: bool) -> None:
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": DRAFT.model_dump_json()}})

    rules = "RULES\n\nLanguage: reply in the patient's language. In Arabic, use Egyptian Arabic.\n\nMORE"
    await _ollama(handler).respond(
        instructions=rules, history=[ChatTurn(role="user", content=message)], references=[], consultation=STATE, user_ref="x"
    )

    system = sent["messages"][0]["content"]
    assert ("Egyptian Arabic" in system) is keeps_dialect_guidance
    assert system.startswith("RULES") and system.endswith("MORE")
    assert f"Write `reply` in {language}" in sent["messages"][-1]["content"]
