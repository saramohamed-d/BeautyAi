"""
Shared pagination schema used by every list endpoint.

Design decision: one generic PaginatedResponse[T], not a bespoke
"PatientListResponse", "DoctorListResponse", etc. per resource. Every
list endpoint in the API returns the exact same envelope shape, so
frontend code (Sprint 3+) writes one generic list-fetching hook instead
of one per resource.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)
