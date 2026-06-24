from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType

from backend.app.db.session import Base


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        return f"vector({self.dimensions})"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    display_name: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    active_role: Mapped[str] = mapped_column(String(32), default="patient")

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user")
    patient_profile: Mapped["PatientProfile | None"] = relationship(back_populates="user", uselist=False)
    caregiver_profile: Mapped["CaregiverProfile | None"] = relationship(back_populates="user", uselist=False)


class UserRole(Base, TimestampMixin):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="pending")

    user: Mapped[User] = relationship(back_populates="roles")


class PatientProfile(Base, TimestampMixin):
    __tablename__ = "patient_profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    real_name: Mapped[str] = mapped_column(String(80), default="")
    id_number: Mapped[str] = mapped_column(String(64), default="")
    id_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="pending")
    basic_info: Mapped[dict] = mapped_column(JSONB, default=dict)

    user: Mapped[User] = relationship(back_populates="patient_profile")


class CaregiverProfile(Base, TimestampMixin):
    __tablename__ = "caregiver_profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    real_name: Mapped[str] = mapped_column(String(80), default="")
    id_number: Mapped[str] = mapped_column(String(64), default="")
    id_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="pending")
    bio: Mapped[str] = mapped_column(Text, default="")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    service_city: Mapped[str] = mapped_column(String(80), default="")
    rating_avg: Mapped[float] = mapped_column(Float, default=0)

    user: Mapped[User] = relationship(back_populates="caregiver_profile")
    certifications: Mapped[list["Certification"]] = relationship(back_populates="caregiver_profile")


class Certification(Base, TimestampMixin):
    __tablename__ = "certifications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    caregiver_profile_id: Mapped[str] = mapped_column(ForeignKey("caregiver_profiles.id", ondelete="CASCADE"))
    certificate_type: Mapped[str] = mapped_column(String(80))
    file_url: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    review_note: Mapped[str] = mapped_column(Text, default="")

    caregiver_profile: Mapped[CaregiverProfile] = relationship(back_populates="certifications")


class JobPosting(Base, TimestampMixin):
    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    employer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80), default="")
    care_type: Mapped[str] = mapped_column(String(80), default="")
    care_level: Mapped[str] = mapped_column(String(64), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    schedule: Mapped[dict] = mapped_column(JSONB, default=dict)
    salary: Mapped[dict] = mapped_column(JSONB, default=dict)
    budget_cents: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    special_requirements: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    caregiver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    cover_letter: Mapped[str] = mapped_column(Text, default="")


class Invitation(Base, TimestampMixin):
    __tablename__ = "invitations"
    __table_args__ = (
        UniqueConstraint("patient_id", "caregiver_id", "job_id", name="uq_invitations_patient_caregiver_job"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    caregiver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job_postings.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    message: Mapped[str] = mapped_column(Text, default="")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    participant_a: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    participant_b: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="care_chat")
    source_type: Mapped[str] = mapped_column(String(32), default="")
    source_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    title: Mapped[str] = mapped_column(String(160), default="")


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    sender_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sender_type: Mapped[str] = mapped_column(String(32), default="user")
    body: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, default="")
    attachment_url: Mapped[str] = mapped_column(String(500), default="")
    attachment_type: Mapped[str] = mapped_column(String(64), default="")


class AiSession(Base, TimestampMixin):
    __tablename__ = "ai_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    role_context: Mapped[str] = mapped_column(String(32), default="patient")
    title: Mapped[str] = mapped_column(String(160), default="")
    risk_flag: Mapped[str] = mapped_column(String(32), default="none")
    summary: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class AiMessage(Base, TimestampMixin):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str | None] = mapped_column(ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    sender: Mapped[str] = mapped_column(String(16), default="user")
    content: Mapped[str] = mapped_column(Text, default="")
    user_message: Mapped[str] = mapped_column(Text)
    assistant_message: Mapped[str] = mapped_column(Text, default="")
    intent_category: Mapped[str] = mapped_column(String(64), index=True)
    intent_subcategory: Mapped[str] = mapped_column(String(64), default="", index=True)
    intent_confidence: Mapped[float] = mapped_column(Float, default=0)
    cache_hit_level: Mapped[str] = mapped_column(String(16), default="miss")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class MedicalCase(Base, TimestampMixin):
    __tablename__ = "medical_cases"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    patient_owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    public_summary: Mapped[str] = mapped_column(Text, default="")
    history_encrypted: Mapped[str] = mapped_column(Text, default="")
    symptoms_encrypted: Mapped[str] = mapped_column(Text, default="")
    medications_encrypted: Mapped[str] = mapped_column(Text, default="")
    encrypted_payload: Mapped[str] = mapped_column(Text)
    attachments: Mapped[list] = mapped_column(JSONB, default=list)
    visibility: Mapped[str] = mapped_column(String(32), default="private")
    linked_ai_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_sessions.id", ondelete="SET NULL"), nullable=True
    )
    encryption_key_version: Mapped[str] = mapped_column(String(32), default="v1")
    encryption_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)


class AiModelConfig(Base, TimestampMixin):
    __tablename__ = "ai_model_configs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    provider: Mapped[str] = mapped_column(String(64), default="deepseek", index=True)
    model_name: Mapped[str] = mapped_column(String(120), default="deepseek-chat")
    base_url: Mapped[str] = mapped_column(String(500), default="https://api.deepseek.com")
    api_key_ref: Mapped[str] = mapped_column(String(120), default="LLM_API_KEY")
    temperature: Mapped[float] = mapped_column(Float, default=0.3)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)


class AiKnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "ai_knowledge_chunks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    category: Mapped[str] = mapped_column(String(64), index=True)
    subcategory: Mapped[str] = mapped_column(String(64), index=True)
    collection: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class AiSemanticCache(Base, TimestampMixin):
    __tablename__ = "ai_semantic_cache"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    category: Mapped[str] = mapped_column(String(64), index=True)
    subcategory: Mapped[str] = mapped_column(String(64), index=True)
    query_text: Mapped[str] = mapped_column(Text)
    query_embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    answer_text: Mapped[str] = mapped_column(Text)
    cached_answer: Mapped[str] = mapped_column(Text, default="")
    intent_category: Mapped[str] = mapped_column(String(64), default="", index=True)
    reusable_as_final: Mapped[bool] = mapped_column(Boolean, default=False)
    cache_policy: Mapped[str] = mapped_column(String(32), default="context_only")
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("conversation_id", "reviewer_id", name="uq_reviews_conversation_reviewer"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewee_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    score: Mapped[int] = mapped_column(Integer)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    comment: Mapped[str] = mapped_column(Text, default="")


class SmsNotification(Base, TimestampMixin):
    __tablename__ = "sms_notifications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    scene: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[str] = mapped_column(String(32), index=True)
    template_code: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    provider_message_id: Mapped[str] = mapped_column(String(128), default="")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminLog(Base, TimestampMixin):
    __tablename__ = "admin_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    admin_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str] = mapped_column(String(80), default="")
    target_id: Mapped[str] = mapped_column(String(120), default="")
    target: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
