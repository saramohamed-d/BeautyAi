import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import EvidenceLevel, KnowledgeDocumentStatus, Language


class KnowledgeDocument(Base, UUIDPkMixin, TimestampMixin):
    """
    Source-level metadata for one piece of medical knowledge (a
    guideline, paper, or official guidance document) that will back the
    RAG pipeline built in Sprint 8/9.

    `status` implements the "review/approval workflow" required by the
    spec: documents start as DRAFT/PENDING_REVIEW and only APPROVED
    documents should be surfaced by retrieval (enforced by the RAG query
    layer in Sprint 9 — this table just carries the state).

    Sprint 1 deliberately does NOT add an embedding/vector column to
    `knowledge_chunks` below — that belongs to Sprint 8, once the
    ingestion pipeline and embedding model are actually chosen. Adding it
    now, unused, would be exactly the kind of premature scope creep the
    project rules warn against.
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
    __tablename__ = "knowledge_chunks"

    knowledge_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # NOTE: a pgvector `embedding` column is added in Sprint 8, once the
    # ingestion pipeline (loader/cleaner/chunker/embedder) exists to
    # populate it. Deliberately absent here.

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_knowledge_chunks_document_id_chunk_index", "knowledge_document_id", "chunk_index"),
    )
