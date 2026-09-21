"""
Sprint 7: OpenAIProvider request shape and error handling, without
network access (the SDK client is replaced by a stub).
"""

import uuid
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.agents.llm import AssistantDraft, ChatTurn, LLMError, OpenAIProvider
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
