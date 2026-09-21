"""
Text embeddings for the knowledge search.

- OpenAIEmbedder: the configured OpenAI embedding model, asked for 1536
  dimensions (the column size; text-embedding-3 models support this).
- DemoEmbedder: deterministic, offline "feature hashing" of words and
  character n-grams. It captures word overlap, not meaning, and it can't
  match across languages. Good enough to develop and test the pipeline;
  keyword search (see retrieval.py) carries more weight with it.

`min_similarity` is each embedder's cosine-similarity floor for a
passage to count as relevant. The values are starting points to tune
with the evaluation set (Sprint 16).
"""

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.knowledge import EMBEDDING_DIMENSIONS
from app.rag.text import STOPWORDS, light_arabic_stem
from app.workflows.safety import is_arabic, normalize

logger = get_logger(__name__)


class EmbeddingError(Exception):
    pass


class Embedder(Protocol):
    model: str
    min_similarity: float

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    min_similarity = 0.35
    batch_size = 64

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=2)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import openai

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            try:
                response = await self._client.embeddings.create(
                    model=self.model, input=batch, dimensions=EMBEDDING_DIMENSIONS
                )
            except openai.OpenAIError as exc:
                logger.warning("embeddings.error", error=type(exc).__name__)
                raise EmbeddingError(str(exc)) from exc
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
        return vectors


_WORD = re.compile(r"\w+", re.UNICODE)


def _features(text: str) -> dict[str, float]:
    features: dict[str, float] = {}
    for word in _WORD.findall(normalize(text)):
        if word in STOPWORDS or len(word) < 2:
            continue
        stem = light_arabic_stem(word) if is_arabic(word) else word
        features[f"w:{stem}"] = features.get(f"w:{stem}", 0.0) + 1.0
        padded = f"#{stem}#"
        for i in range(len(padded) - 3):
            gram = f"g:{padded[i:i + 4]}"
            features[gram] = features.get(gram, 0.0) + 0.3
    return features


class DemoEmbedder:
    # Bump the version whenever _features changes, so `reembed` refreshes stored vectors.
    model = "demo-hash-v3"
    min_similarity = 0.2

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for feature, weight in _features(text).items():
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign * weight
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.ai_provider == "openai":
        return OpenAIEmbedder(settings.openai_api_key or "", settings.openai_embedding_model or "", settings.ai_timeout_seconds)
    return DemoEmbedder()
