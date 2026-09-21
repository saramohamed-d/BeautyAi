"""
Knowledge library: public reading and search of APPROVED articles, and
admin management with a review step.

Anything not approved is invisible to non-admins (404), exactly like it
is to the chat's retrieval.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, OptionalPrincipal
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models.enums import KnowledgeDocumentStatus, Language
from app.models.knowledge import KnowledgeDocument
from app.rag.embeddings import Embedder, get_embedder
from app.rag.ingest import DocumentInput, approve, upsert_document
from app.rag.retrieval import search
from app.schemas.common import PaginatedResponse
from app.schemas.knowledge import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentRead,
    KnowledgeDocumentSummary,
    KnowledgeDocumentUpdate,
    KnowledgeSearchHit,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
SNIPPET_CHARS = 280


async def _visible_document(db: AsyncSession, document_id: UUID, is_admin: bool) -> KnowledgeDocument:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None or (document.status != KnowledgeDocumentStatus.APPROVED and not is_admin):
        raise NotFoundError(f"Document '{document_id}' not found")
    return document


@router.get("/search", response_model=list[KnowledgeSearchHit])
async def search_knowledge(
    q: str = Query(..., min_length=2, max_length=500),
    language: Language | None = Query(None, description="Prefer passages in this language"),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
) -> list[KnowledgeSearchHit]:
    """The same hybrid search the chat uses. Approved articles only."""
    references = await search(db, q, embedder, language=language.value if language else None, limit=limit)
    return [
        KnowledgeSearchHit(
            document_id=r.document_id,
            title=r.title,
            heading=r.heading,
            snippet=r.content if len(r.content) <= SNIPPET_CHARS else r.content[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…",
            language=r.language,
            score=r.score,
        )
        for r in references
    ]


@router.get("/documents", response_model=PaginatedResponse[KnowledgeDocumentSummary])
async def list_documents(
    principal: OptionalPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    language: Language | None = Query(None),
    status_filter: KnowledgeDocumentStatus | None = Query(None, alias="status", description="Admins only"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[KnowledgeDocumentSummary]:
    query = select(KnowledgeDocument)
    if principal is not None and principal.is_admin:
        if status_filter is not None:
            query = query.where(KnowledgeDocument.status == status_filter)
    else:
        query = query.where(KnowledgeDocument.status == KnowledgeDocumentStatus.APPROVED)
    if language is not None:
        query = query.where(KnowledgeDocument.language == language)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(query.order_by(KnowledgeDocument.title).offset((page - 1) * page_size).limit(page_size))
    return PaginatedResponse.build(list(rows.all()), total or 0, page, page_size)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentRead)
async def get_document(
    document_id: UUID, principal: OptionalPrincipal, db: AsyncSession = Depends(get_db)
) -> KnowledgeDocumentRead:
    return await _visible_document(db, document_id, bool(principal and principal.is_admin))


@router.post("/documents", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: KnowledgeDocumentCreate,
    _: AdminPrincipal,
    db: AsyncSession = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
) -> KnowledgeDocumentRead:
    """Adds an article as pending_review: indexed, but not searchable until approved."""
    if await db.scalar(select(KnowledgeDocument.id).where(KnowledgeDocument.slug == payload.slug)):
        raise ConflictError(f"A document with slug '{payload.slug}' already exists")
    document, _ = await upsert_document(db, DocumentInput(**payload.model_dump()), embedder)
    return document


@router.patch("/documents/{document_id}", response_model=KnowledgeDocumentRead)
async def update_document(
    document_id: UUID,
    payload: KnowledgeDocumentUpdate,
    _: AdminPrincipal,
    db: AsyncSession = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
) -> KnowledgeDocumentRead:
    document = await _visible_document(db, document_id, is_admin=True)
    changes = payload.model_dump(exclude_unset=True)

    if {"title", "body"} & changes.keys():
        # New text: re-chunk and re-embed; upsert_document puts it back to pending_review.
        document, _ = await upsert_document(
            db,
            DocumentInput(
                slug=document.slug or str(document.id),
                title=changes.get("title", document.title),
                language=document.language,
                body=changes.get("body", document.body or ""),
                source=changes.get("source", document.source),
                evidence_level=document.evidence_level,
                url=changes.get("url", document.url),
                specialty=changes.get("specialty", document.specialty),
                summary=changes.get("summary", document.summary),
                version=document.version,
            ),
            embedder,
        )
        return document

    for field in ("summary", "source", "url", "specialty"):
        if field in changes:
            setattr(document, field, changes[field])
    if payload.status == KnowledgeDocumentStatus.APPROVED:
        approve(document, payload.reviewed_by or "")
    elif payload.status is not None:
        document.status = payload.status
    await db.commit()
    await db.refresh(document)
    return document
