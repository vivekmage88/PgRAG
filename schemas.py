from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    k: int = Field(default=5, ge=1, le=20)
    max_distance: float = Field(default=0.6, gt=0, le=2.0)
    document_id: int | None = Field(default=None, ge=1)


class Source(BaseModel):
    page: int
    heading: str | None
    distance: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    filename: str
    page_count: int
    created_at: datetime