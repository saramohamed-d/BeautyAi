from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Reference:
    """One retrieved passage, as shown to the model and cited to the patient."""

    chunk_id: UUID
    document_id: UUID
    # Stable key of the article across re-ingestion (e.g. "acne-basics-en");
    # what evaluation and analytics identify a source by.
    slug: str | None
    title: str
    heading: str | None
    content: str
    language: str
    source: str
    url: str | None
    score: float
    similarity: float
