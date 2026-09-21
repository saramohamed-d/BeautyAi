import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import EvidenceLevel, KnowledgeDocumentStatus, Language

# Fixed by the column type below; changing it needs a migration and re-embedding.
EMBEDDING_DIMENSIONS = 1536


class KnowledgeDocument(Base, UUIDPkMixin, TimestampMixin):
    """
    One piece of medical knowledge (a patient-education article,
    guideline or official guidance) backing the RAG search (Sprint 8).

    Review workflow: documents enter as PENDING_REVIEW and only APPROVED
    ones are ever retrieved (enforced in app/rag/retrieval.py). Approving
    requires a named reviewer (`reviewed_by`). Changing an approved
    document's text sends it back to PENDING_REVIEW.

    `slug` identifies a document across re-ingestion from
    data/knowledge/, and `content_hash` lets ingestion skip unchanged files.
    """

    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    procedure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("procedures.id", ondelete="SET NULL"), nullable=True
    )
    evidence_level: Mapped[EvidenceLevel] = mapped_column(
        SAEnum(
            EvidenceLevel, name="evidence_level", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )
    language: Mapped[Language] = mapped_column(
        SAEnum(Language, name="language", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_reviewed: Mapped[date | None] = mapped_column(Date, nullable=True)
    slug: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full original text (Markdown), shown on the article page. Chunks are derived from it.
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[KnowledgeDocumentStatus] = mapped_column(
        SAEnum(
            KnowledgeDocumentStatus,
            name="knowledge_document_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=KnowledgeDocumentStatus.DRAFT,
        index=True,
    )

    procedure: Mapped["Procedure | None"] = relationship()
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="KnowledgeChunk.chunk_index"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeDocument id={self.id} title={self.title!r}>"


class KnowledgeChunk(Base, UUIDPkMixin, TimestampMixin):
    """
    A retrievable passage of a document.

    Two indexes serve hybrid search (see app/rag/retrieval.py):
    - `embedding` (pgvector, HNSW, cosine) for meaning-based matches.
      `embedding_model` records which model produced the vector; search
      only compares vectors from the currently configured model.
    - `search_vector` (generated tsvector, GIN) for keyword matches, built
      with Postgres's Arabic or English analyzer by the chunk's language.
    """

    __tablename__ = "knowledge_chunks"

    knowledge_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Heading path of the section the passage comes from, e.g. "When to see a dermatologist".
    heading: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Copied from the document so the keyword index (a generated column) can use it.
    language: Mapped[Language] = mapped_column(
        SAEnum(Language, name="language", values_callable=lambda e: [m.value for m in e], create_type=False),
        nullable=False,
        server_default=Language.EN.value,
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "CASE WHEN language = 'ar' THEN to_tsvector('arabic'::regconfig, content) "
            "ELSE to_tsvector('english'::regconfig, content) END",
            persisted=True,
        ),
    )

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_knowledge_chunks_document_id_chunk_index", "knowledge_document_id", "chunk_index"),
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_knowledge_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )
