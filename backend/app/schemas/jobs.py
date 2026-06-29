from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobPostingCreate(BaseModel):
    employer_id: str
    patient_id: str | None = None
    title: str = Field(min_length=2, max_length=120)
    city: str = ""
    care_type: str = ""
    care_level: str = ""
    location: str = ""
    schedule: dict[str, Any] = Field(default_factory=dict)
    salary: dict[str, Any] = Field(default_factory=dict)
    budget_cents: int = 0
    special_requirements: str = ""
    description: str = ""


class JobPostingRead(JobPostingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobStatusUpdate(BaseModel):
    status: str = Field(pattern="^(draft|published|matched|closed|cancelled)$")


class ApplicationCreate(BaseModel):
    caregiver_id: str
    cover_letter: str = ""


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    caregiver_id: str
    status: str
    cover_letter: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ApplicationDecision(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")


class InvitationCreate(BaseModel):
    patient_id: str
    caregiver_id: str
    job_id: str | None = None
    message: str = ""


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    caregiver_id: str
    job_id: str | None = None
    status: str
    message: str = ""
    responded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InvitationDecision(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    participant_a: str | None = None
    participant_b: str | None = None
    kind: str
    source_type: str
    source_id: str | None = None
    title: str = ""


class MatchResult(BaseModel):
    status: str
    conversation: ConversationRead | None = None


class AvailableCaregiverRead(BaseModel):
    user_id: str
    real_name: str = ""
    bio: str = ""
    service_city: str = ""
    experience_years: int = 0
    rating_avg: float = 0
    is_available: bool = True
