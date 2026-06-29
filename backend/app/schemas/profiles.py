from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PublicMedicalCaseRead(BaseModel):
    id: str
    summary: str = ""
    public_summary: str = ""
    visibility: str = "private"
    attachments: list[Any] = Field(default_factory=list)
    updated_at: datetime | None = None


class ProfileJobRead(BaseModel):
    id: str
    title: str
    city: str = ""
    care_type: str = ""
    location: str = ""
    budget_cents: int = 0
    status: str = "draft"
    created_at: datetime | None = None


class PatientHomepageRead(BaseModel):
    user_id: str
    display_name: str = ""
    real_name: str = ""
    id_verified: bool = False
    verification_status: str = "pending"
    basic_info: dict[str, Any] = Field(default_factory=dict)
    rating_avg: float = 0
    review_count: int = 0
    recent_reviews: list["PublicReviewRead"] = Field(default_factory=list)
    public_cases: list[PublicMedicalCaseRead] = Field(default_factory=list)
    job_history: list[ProfileJobRead] = Field(default_factory=list)


class PublicCertificationRead(BaseModel):
    id: str
    certificate_type: str
    file_url: str = ""
    description: str = ""
    review_status: str = "pending"


class PublicReviewRead(BaseModel):
    id: str
    reviewer_id: str
    score: int
    tags: list[Any] = Field(default_factory=list)
    comment: str = ""
    created_at: datetime | None = None


class CaregiverResumeRead(BaseModel):
    user_id: str
    display_name: str = ""
    real_name: str = ""
    id_verified: bool = False
    verification_status: str = "pending"
    bio: str = ""
    is_available: bool = True
    experience_years: int = 0
    service_city: str = ""
    rating_avg: float = 0
    review_count: int = 0
    certifications: list[PublicCertificationRead] = Field(default_factory=list)
    recent_reviews: list[PublicReviewRead] = Field(default_factory=list)


class CaregiverAvailabilityUpdate(BaseModel):
    is_available: bool
