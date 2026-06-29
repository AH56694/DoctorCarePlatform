from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminSummaryRead(BaseModel):
    users: int = 0
    active_jobs: int = 0
    pending_certifications: int = 0
    ai_sessions: int = 0
    risk_alerts: int = 0
    sms_notifications: int = 0
    reviews: int = 0


class AdminUserRead(BaseModel):
    id: str
    phone: str
    display_name: str = ""
    status: str
    active_role: str
    created_at: datetime | None = None


class AdminUserStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|disabled|suspended)$")
    admin_id: str | None = None
    reason: str = ""


class AdminCertificationRead(BaseModel):
    id: str
    caregiver_profile_id: str
    caregiver_user_id: str
    caregiver_name: str = ""
    certificate_type: str
    file_url: str = ""
    description: str = ""
    review_status: str
    review_note: str = ""
    created_at: datetime | None = None


class AdminCertificationReview(BaseModel):
    review_status: str = Field(pattern="^(pending|approved|rejected)$")
    review_note: str = ""
    admin_id: str | None = None


class AdminAiMessageRead(BaseModel):
    id: str
    session_id: str | None = None
    sender: str
    content: str = ""
    intent_category: str = ""
    intent_subcategory: str = ""
    intent_confidence: float = 0
    cache_hit_level: str = "miss"
    created_at: datetime | None = None


class AdminChatMessageRead(BaseModel):
    id: str
    conversation_id: str
    sender_id: str | None = None
    sender_type: str
    body: str = ""
    content: str = ""
    attachment_url: str = ""
    created_at: datetime | None = None


class AdminAiModelConfigCreate(BaseModel):
    provider: str = "deepseek"
    model_name: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    api_key_ref: str = "LLM_API_KEY"
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1)
    is_active: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)
    admin_id: str | None = None


class AdminAiModelConfigUpdate(BaseModel):
    provider: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    api_key_ref: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
    parameters: dict[str, Any] | None = None
    admin_id: str | None = None


class AdminAiModelConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    model_name: str
    base_url: str
    api_key_ref: str
    temperature: float
    max_tokens: int
    is_active: bool
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    admin_id: str | None = None
    action: str
    target_type: str = ""
    target_id: str = ""
    target: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    ip_address: str = ""
    created_at: datetime | None = None
