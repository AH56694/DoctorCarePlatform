from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SmsSendRequest(BaseModel):
    phone: str = Field(min_length=5)
    template_params: dict[str, str] = Field(default_factory=dict)
    template_code: str | None = None


class SmsNotificationCreate(BaseModel):
    phone: str = Field(min_length=5)
    scene: str = "manual"
    user_id: str | None = None
    template_code: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SmsNotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None = None
    scene: str
    phone: str
    template_code: str
    status: str
    provider_message_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sent_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SmsSceneRead(BaseModel):
    scene: str
    description: str
