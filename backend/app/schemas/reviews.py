from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    conversation_id: str
    reviewer_id: str
    reviewee_id: str
    score: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    comment: str = Field(default="", max_length=2000)


class ReviewUpdate(BaseModel):
    score: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    comment: str = Field(default="", max_length=2000)


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    reviewer_id: str
    reviewee_id: str
    score: int
    tags: list[Any] = Field(default_factory=list)
    comment: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TrustSummaryRead(BaseModel):
    user_id: str
    rating_avg: float = 0
    review_count: int = 0
    recent_reviews: list[ReviewRead] = Field(default_factory=list)
