"""
Loading knowledge documents: text → passages → embeddings → database.

Used by the CLI (`python -m app.rag.cli ingest ...`), the admin API and
the dev seed. Documents are keyed by `slug`, so re-running ingestion
updates in place: unchanged text is skipped (content hash), changed text
is re-chunked and re-embedded and, if it was approved, goes back to
review. Approval always needs a named reviewer.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.core.logging import get_logger
from app.models.enums import EvidenceLevel, KnowledgeDocumentStatus, Language
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.chunking import Passage, chunk_markdown, parse_front_matter
from app.rag.embeddings import Embedder

logger = get_logger(__name__)


@dataclass
class DocumentInput:
    slug: str
    title: str
    language: Language
    body: str
    source: str
    evidence_level: EvidenceLevel = EvidenceLevel.EXPERT_OPINION
    url: str | None = None
    specialty: str | None = None
    summary: str | None = None
    version: str = "1.0"


def default_knowledge_dir() -> Path:
    configured = get_settings().knowledge_dir
    # backend/app/rag/ingest.py → repo root is three levels up from app/.
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / "data" / "knowledge"


def read_document_file(path: Path) -> DocumentInput:
    meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
    missing = [key for key in ("slug", "title", "language", "source") if not meta.get(key)]
    if missing:
        raise ValueError(f"{path.name}: missing front matter {', '.join(missing)}")
    return DocumentInput(
        slug=meta["slug"],
        title=meta["title"],
        language=Language(meta["language"]),
        body=body,
        source=meta["source"],
        evidence_level=EvidenceLevel(meta.get("evidence_level", EvidenceLevel.EXPERT_OPINION.value)),
        url=meta.get("url") or None,
        specialty=meta.get("specialty") or None,
        summary=meta.get("summary") or None,
        version=meta.get("version", "1.0"),
    )


def _hash(doc: DocumentInput) -> str:
    return hashlib.sha256(f"{doc.title}\n{doc.language.value}\n{doc.body}".encode()).hexdigest()


def _embedding_text(title: str, passage: Passage) -> str:
    # Title and heading give a short passage its context ("When to see a dermatologist" of *what*?).
    return "\n".join(filter(None, [title, passage.heading, passage.content]))


async def _replace_chunks(db: AsyncSession, document: KnowledgeDocument, embedder: Embedder) -> int:
    passages = chunk_markdown(document.body or "")
    if not passages:
        raise ValidationAppError("The document has no text to index")
    vectors = await embedder.embed([_embedding_text(document.title, p) for p in passages])
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_document_id == document.id))
    for index, (passage, vector) in enumerate(zip(passages, vectors, strict=True)):
        db.add(
            KnowledgeChunk(
                knowledge_document_id=document.id,
                chunk_index=index,
                heading=passage.heading,
                content=passage.content,
                language=document.language,
                embedding=vector,
                embedding_model=embedder.model,
            )
        )
    return len(passages)


def approve(document: KnowledgeDocument, reviewer: str) -> None:
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValidationAppError("Approving a document requires the reviewer's name")
    document.status = KnowledgeDocumentStatus.APPROVED
    document.reviewed_by = reviewer
    document.reviewed_at = datetime.now(timezone.utc)
    document.last_reviewed = date.today()


async def upsert_document(
    db: AsyncSession, doc: DocumentInput, embedder: Embedder, approve_as: str | None = None
) -> tuple[KnowledgeDocument, str]:
    """Creates or updates a document by slug. Returns (document, "created" | "updated" | "unchanged")."""
    content_hash = _hash(doc)
    document = await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == doc.slug))
    if document is not None and document.content_hash == content_hash:
        if approve_as and document.status != KnowledgeDocumentStatus.APPROVED:
            approve(document, approve_as)
            await db.commit()
        return document, "unchanged"

    outcome = "created" if document is None else "updated"
    if document is None:
        document = KnowledgeDocument(slug=doc.slug)
        db.add(document)
    document.title, document.language, document.body = doc.title, doc.language, doc.body
    document.source, document.url, document.specialty = doc.source, doc.url, doc.specialty
    document.summary, document.version, document.evidence_level = doc.summary, doc.version, doc.evidence_level
    document.content_hash = content_hash
    # New or changed text always needs (re-)review.
    document.status = KnowledgeDocumentStatus.PENDING_REVIEW
    document.reviewed_by = document.reviewed_at = None
    await db.flush()

    count = await _replace_chunks(db, document, embedder)
    if approve_as:
        approve(document, approve_as)
    await db.commit()
    await db.refresh(document)
    logger.info("knowledge.ingested", slug=doc.slug, outcome=outcome, chunks=count, status=document.status.value)
    return document, outcome


async def ingest_directory(
    db: AsyncSession, directory: Path, embedder: Embedder, approve_as: str | None = None
) -> dict[str, list[str]]:
    """Ingests every *.md except README.md. Returns slugs by outcome (and file names that failed)."""
    report: dict[str, list[str]] = {"created": [], "updated": [], "unchanged": [], "failed": []}
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        try:
            doc = read_document_file(path)
        except ValueError as exc:
            logger.warning("knowledge.bad_file", file=path.name, error=str(exc))
            report["failed"].append(f"{path.name}: {exc}")
            continue
        _, outcome = await upsert_document(db, doc, embedder, approve_as)
        report[outcome].append(doc.slug)
    return report


async def reembed_all(db: AsyncSession, embedder: Embedder) -> int:
    """Re-embeds chunks made with a different model (after changing the embedding model)."""
    chunks = (
        await db.scalars(
            select(KnowledgeChunk)
            .join(KnowledgeDocument)
            .where((KnowledgeChunk.embedding_model != embedder.model) | KnowledgeChunk.embedding_model.is_(None))
        )
    ).all()
    titles = {c.knowledge_document_id: None for c in chunks}
    for document in (await db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(titles)))).all():
        titles[document.id] = document.title
    vectors = await embedder.embed(
        [_embedding_text(titles[c.knowledge_document_id] or "", Passage(c.heading, c.content)) for c in chunks]
    )
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding, chunk.embedding_model = vector, embedder.model
    await db.commit()
    return len(chunks)
