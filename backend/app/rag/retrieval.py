"""
Hybrid search over APPROVED knowledge passages.

Two rankings, merged with Reciprocal Rank Fusion (RRF):
1. Meaning: cosine similarity of pgvector embeddings (HNSW index), only
   against vectors from the current embedding model.
2. Keywords: Postgres full-text search, using the Arabic or English
   analyzer (stemming) per passage. Query words are OR-ed, so a
   natural-language question still matches passages that share some of
   its important words.

A passage is kept if its similarity clears the embedder's
`min_similarity`, or if it matched at least KEYWORD_MIN_TERMS distinct
query words (after stemming and stop-word removal) and clears a quarter
of that similarity. Keywords can therefore rescue relevant passages the
embeddings rank low (common with Arabic word forms), but a single
shared word ("tell", "hair") can't pull in unrelated text. At most two
passages per document are returned, and passages in the patient's
language get a small boost.
"""

import re
from uuid import UUID

from sqlalchemy import case, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import KnowledgeDocumentStatus
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.embeddings import Embedder
from app.rag.types import Reference
from app.rag.text import is_stopword
from app.workflows.safety import _TASHKEEL

CANDIDATES = 20
RRF_K = 60
SAME_LANGUAGE_BONUS = 0.004
MAX_PER_DOCUMENT = 2
KEYWORD_MIN_TERMS = 2
_WORD = re.compile(r"\w{2,}", re.UNICODE)


def _query_terms(query: str) -> list[str]:
    """
    One tsquery expression per distinct, non-stop-word query word. Only
    word characters are kept, so nothing can inject tsquery syntax.

    Only light cleanup (lower-case, no diacritics): Postgres's Arabic
    analyzer already unifies alef forms and strips "ال", but it keeps ة and
    ه apart, and people often type ه for a final ة ("الولاده"), so such
    words are searched both ways.
    """
    words = [w for w in dict.fromkeys(_WORD.findall(_TASHKEEL.sub("", query.lower()))) if not is_stopword(w)][:20]
    return [f"({w} | {w[:-1]}ة)" if w.endswith("ه") and len(w) > 2 else w for w in words]


def _tsquery(expression: str):
    """The same query under both analyzers; each drops its own stop words and stems its own language."""
    return func.to_tsquery(literal_column("'english'::regconfig"), expression).op("||")(
        func.to_tsquery(literal_column("'arabic'::regconfig"), expression)
    )


async def search(
    db: AsyncSession, query: str, embedder: Embedder, *, language: str | None = None, limit: int = 4
) -> list[Reference]:
    query = query.strip()
    if not query:
        return []
    [query_vector] = await embedder.embed([query])
    approved = KnowledgeDocument.status == KnowledgeDocumentStatus.APPROVED

    distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
    vector_rows = (
        await db.execute(
            select(KnowledgeChunk.id, (1 - distance).label("similarity"))
            .join(KnowledgeDocument)
            .where(approved, KnowledgeChunk.embedding_model == embedder.model)
            .order_by(distance)
            .limit(CANDIDATES)
        )
    ).all()

    keyword_rows = []
    if terms := _query_terms(query):
        tsquery = _tsquery(" | ".join(terms))
        rank = func.ts_rank_cd(KnowledgeChunk.search_vector, tsquery)
        # How many distinct query words this passage matches.
        matched_terms = sum(
            (case((KnowledgeChunk.search_vector.op("@@")(_tsquery(term)), 1), else_=0) for term in terms),
            start=literal_column("0"),
        )
        keyword_rows = (
            await db.execute(
                select(KnowledgeChunk.id, rank.label("rank"), matched_terms.label("terms"))
                .join(KnowledgeDocument)
                .where(approved, KnowledgeChunk.search_vector.op("@@")(tsquery))
                .order_by(rank.desc())
                .limit(CANDIDATES)
            )
        ).all()

    similarity = {row.id: float(row.similarity) for row in vector_rows}
    keyword_ids = {row.id for row in keyword_rows if row.terms >= KEYWORD_MIN_TERMS}
    fused: dict[UUID, float] = {}
    for ranking in (vector_rows, keyword_rows):
        for position, row in enumerate(ranking):
            fused[row.id] = fused.get(row.id, 0.0) + 1.0 / (RRF_K + position + 1)
    if not fused:
        return []

    # Similarity for keyword-only hits (outside the vector top-N), to apply the gate.
    missing = [chunk_id for chunk_id in fused if chunk_id not in similarity]
    if missing:
        for row in await db.execute(
            select(KnowledgeChunk.id, (1 - distance).label("similarity")).where(
                KnowledgeChunk.id.in_(missing), KnowledgeChunk.embedding_model == embedder.model
            )
        ):
            similarity[row.id] = float(row.similarity)

    def relevant(chunk_id: UUID) -> bool:
        sim = similarity.get(chunk_id, 0.0)
        return sim >= embedder.min_similarity or (chunk_id in keyword_ids and sim >= embedder.min_similarity / 4)

    kept = [chunk_id for chunk_id in fused if relevant(chunk_id)]
    if not kept:
        return []
    rows = (
        await db.execute(
            select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(KnowledgeChunk.id.in_(kept))
        )
    ).all()
    candidates = []
    for chunk, document in rows:
        score = fused[chunk.id] + (SAME_LANGUAGE_BONUS if language and chunk.language.value == language else 0.0)
        candidates.append((score, chunk, document))
    candidates.sort(key=lambda item: item[0], reverse=True)

    results: list[Reference] = []
    per_document: dict[UUID, int] = {}
    for score, chunk, document in candidates:
        if per_document.get(document.id, 0) >= MAX_PER_DOCUMENT:
            continue
        per_document[document.id] = per_document.get(document.id, 0) + 1
        results.append(
            Reference(
                chunk_id=chunk.id,
                document_id=document.id,
                slug=document.slug,
                title=document.title,
                heading=chunk.heading,
                content=chunk.content,
                language=chunk.language.value,
                source=document.source,
                url=document.url,
                score=round(score, 5),
                similarity=round(similarity.get(chunk.id, 0.0), 4),
            )
        )
        if len(results) == limit:
            break
    return results


async def index_is_empty(db: AsyncSession) -> bool:
    return not await db.scalar(text("SELECT EXISTS (SELECT 1 FROM knowledge_chunks WHERE embedding IS NOT NULL)"))
