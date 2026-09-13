import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProcedureBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    category: str = Field(..., min_length=2, max_length=128)
    description: str | None = None
    typical_price_min: float | None = Field(None, ge=0)
    typical_price_max: float | None = Field(None, ge=0)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError("slug must be lowercase-kebab-case (e.g. 'chemical-peel')")
        return v


class ProcedureCreate(ProcedureBase):
    pass


class ProcedureUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    category: str | None = Field(None, min_length=2, max_length=128)
    description: str | None = None
    typical_price_min: float | None = Field(None, ge=0)
    typical_price_max: float | None = Field(None, ge=0)


class ProcedureRead(ProcedureBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
