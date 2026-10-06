"""
Language-model access for the patient chat.

Everything outside this module talks to `LLMProvider`, so changing
provider (or adding one) touches only this file. Two implementations:

- OpenAIProvider: the real model. Uses structured output, so the reply
  always arrives as an AssistantDraft (never free text to parse), with
  `store=False` (the provider keeps no copy of the conversation) and a
  hashed user id for the provider's abuse monitoring. No names, phone
  numbers or other profile data are ever sent, only message text.
- OllamaProvider: a local model through Ollama (free, no tokens to run
  out of), for local development and demos.
- DemoProvider (agents/demo_llm.py): deterministic and offline, for
  local development and tests. Refused outside local/test by config.
"""

import hashlib
import re
from functools import lru_cache
from typing import Protocol

from app.agents.schemas import AssistantDraft, ChatTurn, ConsultationState
from app.core.config import get_settings
from app.core.logging import get_logger
from app.prompts.chat import consultation_block, references_block
from app.rag.types import Reference

# Re-exported for existing imports.
__all__ = ["AssistantDraft", "ChatTurn", "LLMError", "LLMProvider", "OllamaProvider", "OpenAIProvider", "get_llm", "anonymous_user_ref"]

logger = get_logger(__name__)

MAX_REPLY_CHARS = 1500


class LLMError(Exception):
    """The model couldn't produce a usable answer (timeout, API error, refusal, bad output)."""


class LLMProvider(Protocol):
    name: str
    model: str

    async def respond(
        self,
        *,
        instructions: str,
        history: list[ChatTurn],
        references: list[Reference],
        consultation: ConsultationState,
        user_ref: str,
    ) -> AssistantDraft: ...


def anonymous_user_ref(user_id: object) -> str:
    """Stable, non-reversible id for the provider's abuse monitoring."""
    return hashlib.sha256(f"beautyai:{user_id}".encode()).hexdigest()[:32]


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=1)

    async def respond(
        self,
        *,
        instructions: str,
        history: list[ChatTurn],
        references: list[Reference],
        consultation: ConsultationState,
        user_ref: str,
    ) -> AssistantDraft:
        import openai

        messages = [{"role": turn.role, "content": turn.content} for turn in history]
        # Per-turn context goes in developer messages, so `instructions` stays
        # identical across turns (better prompt caching) and platform context
        # stays clearly separate from both the rules and the patient's words.
        messages.append({"role": "developer", "content": consultation_block(consultation)})
        if references:
            messages.append({"role": "developer", "content": references_block(references)})
        try:
            response = await self._client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=messages,
                text_format=AssistantDraft,
                store=False,
                safety_identifier=user_ref,
                max_output_tokens=800,
            )
        except openai.OpenAIError as exc:
            logger.warning("llm.error", provider=self.name, error=type(exc).__name__)
            raise LLMError(str(exc)) from exc

        draft = response.output_parsed
        if draft is None:  # refusal or incomplete output
            logger.warning("llm.no_parsed_output", provider=self.name, status=response.status)
            raise LLMError("The model returned no usable answer")
        return draft


_ARABIC = re.compile(r"[\u0600-\u06ff]")
# The system prompt's "Language: ..." paragraph (up to the next blank line).
_LANGUAGE_RULE = re.compile(r"^Language:.*?(?=\n\n|\Z)", re.MULTILINE | re.DOTALL)


class OllamaProvider:
    """
    A local model served by Ollama (https://ollama.com) — free, no API key,
    no token budget. Uses Ollama's native /api/chat with the AssistantDraft
    JSON schema as `format`, so the reply is still structured output.

    Local models are much slower than a hosted API (seconds per reply on a
    laptop GPU), so give it a generous AI_TIMEOUT_SECONDS.
    """

    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float, num_ctx: int) -> None:
        import httpx

        self.model = model
        self._num_ctx = num_ctx
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)
        self._schema = AssistantDraft.model_json_schema()

    async def respond(
        self,
        *,
        instructions: str,
        history: list[ChatTurn],
        references: list[Reference],
        consultation: ConsultationState,
        user_ref: str,
    ) -> AssistantDraft:
        import httpx
        from pydantic import ValidationError

        latest = next((turn.content for turn in reversed(history) if turn.role == "user"), "")
        language = "Arabic" if _ARABIC.search(latest) else "English"
        if language == "English":
            # Small local models read the Egyptian-Arabic guidance as "always answer in Arabic".
            instructions = _LANGUAGE_RULE.sub("Language: reply in English.", instructions)

        messages = [{"role": "system", "content": instructions}]
        messages += [{"role": turn.role, "content": turn.content} for turn in history]
        messages.append({"role": "system", "content": consultation_block(consultation)})
        if references:
            messages.append({"role": "system", "content": references_block(references)})
        # ...and drift into the wrong language without a reminder right before they answer.
        messages.append({
            "role": "system",
            "content": f"Write `reply` in {language}, the language of the patient's latest message. "
            "Answer with a single JSON object matching the given schema.",
        })
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "format": self._schema,
                    "stream": False,
                    "think": False,
                    # Keep the model loaded between messages so replies after the first are fast.
                    "keep_alive": "30m",
                    "options": {"temperature": 0.3, "num_ctx": self._num_ctx, "num_predict": 800},
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            return AssistantDraft.model_validate_json(content)
        except (httpx.HTTPError, KeyError, ValueError, ValidationError) as exc:
            logger.warning("llm.error", provider=self.name, error=type(exc).__name__, detail=str(exc)[:200])
            raise LLMError(str(exc)) from exc


@lru_cache
def get_llm() -> LLMProvider:
    """FastAPI dependency. Tests override it with a scripted provider."""
    settings = get_settings()
    if settings.ai_provider == "openai":
        return OpenAIProvider(settings.openai_api_key or "", settings.openai_model or "", settings.ai_timeout_seconds)
    if settings.ai_provider == "ollama":
        return OllamaProvider(
            settings.ollama_base_url, settings.ollama_model, settings.ai_timeout_seconds, settings.ollama_num_ctx
        )
    from app.agents.demo_llm import DemoProvider

    return DemoProvider()
