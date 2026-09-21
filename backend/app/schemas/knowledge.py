from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import EvidenceLevel, KnowledgeDocumentStatus, Language


class KnowledgeDocumentSummary(BaseModel):
    id: UUID
    slug: str | None
    title: str
    summary: str | None
    language: Language
    specialty: str | None
    source: str
    status: KnowledgeDocumentStatus
    reviewed_by: str | None
    last_reviewed: date | None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentRead(KnowledgeDocumentSummary):
    body: str | None
    url: str | None
    evidence_level: EvidenceLevel
    version: str
    reviewed_at: datetime | None
    updated_at: datetime


class KnowledgeDocumentCreate(BaseModel):
    slug: str = Field(..., min_length=3, max_length=128, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str = Field(..., min_length=3, max_length=512)
    language: Language
    body: str = Field(..., min_length=50)
    source: str = Field(..., min_length=2, max_length=255)
    url: str | None = Field(None, max_length=1024)
    specialty: str | None = Field(None, max_length=128)
    summary: str | None = Field(None, max_length=1000)
    evidence_level: EvidenceLevel = EvidenceLevel.EXPERT_OPINION


class KnowledgeDocumentUpdate(BaseModel):
    """Changing title or body re-indexes the document and sends it back to review."""

    title: str | None = Field(None, min_length=3, max_length=512)
    body: str | None = Field(None, min_length=50)
    summary: str | None = Field(None, max_length=1000)
    source: str | None = Field(None, min_length=2, max_length=255)
    url: str | None = Field(None, max_length=1024)
    specialty: str | None = Field(None, max_length=128)
    status: KnowledgeDocumentStatus | None = None
    reviewed_by: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def approval_needs_reviewer(self) -> "KnowledgeDocumentUpdate":
        if self.status == KnowledgeDocumentStatus.APPROVED and not (self.reviewed_by or "").strip():
            raise ValueError("approving a document requires reviewed_by (the reviewing clinician)")
        if self.status == KnowledgeDocumentStatus.APPROVED and ({"title", "body"} & self.model_fields_set):
            raise ValueError("change the text and approve it in two steps, so the approved version is the reviewed one")
        return self


class KnowledgeSearchHit(BaseModel):
    document_id: UUID
    title: str
    heading: str | None
    snippet: str
    language: str
    score: float
