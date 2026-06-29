from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.db.models import (
    AdminLog,
    AiMessage,
    AiModelConfig,
    AiSession,
    Application,
    CaregiverProfile,
    Certification,
    JobPosting,
    Message,
    Review,
    SmsNotification,
    User,
    UserRole,
)
from backend.app.db.session import get_db
from backend.app.schemas.admin import (
    AdminAiMessageRead,
    AdminAiModelConfigCreate,
    AdminAiModelConfigRead,
    AdminAiModelConfigUpdate,
    AdminCertificationRead,
    AdminCertificationReview,
    AdminChatMessageRead,
    AdminLogRead,
    AdminSummaryRead,
    AdminUserRead,
    AdminUserStatusUpdate,
)
from backend.app.services.sms import SmsNotificationService

router = APIRouter()


def _log_admin_action(
    db: Session,
    *,
    action: str,
    admin_id: str | None = None,
    target_type: str = "",
    target_id: str = "",
    target: str = "",
    detail: dict | None = None,
) -> None:
    db.add(
        AdminLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target=target,
            detail=detail or {},
        )
    )


def _get_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _certification_read(certification: Certification) -> AdminCertificationRead:
    caregiver = certification.caregiver_profile
    return AdminCertificationRead(
        id=certification.id,
        caregiver_profile_id=certification.caregiver_profile_id,
        caregiver_user_id=caregiver.user_id if caregiver else "",
        caregiver_name=caregiver.real_name if caregiver else "",
        certificate_type=certification.certificate_type,
        file_url=certification.file_url,
        description=certification.description or "",
        review_status=certification.review_status,
        review_note=certification.review_note or "",
        created_at=certification.created_at,
    )


@router.get("/summary", response_model=AdminSummaryRead)
async def get_admin_summary(db: Session = Depends(get_db)) -> AdminSummaryRead:
    return AdminSummaryRead(
        users=db.query(func.count(User.id)).scalar() or 0,
        active_jobs=db.query(func.count(JobPosting.id)).filter(JobPosting.status.in_(["published", "matched"])).scalar() or 0,
        pending_certifications=(
            db.query(func.count(Certification.id)).filter(Certification.review_status == "pending").scalar() or 0
        ),
        ai_sessions=db.query(func.count(AiSession.id)).scalar() or 0,
        risk_alerts=db.query(func.count(AiSession.id)).filter(AiSession.risk_flag != "none").scalar() or 0,
        sms_notifications=db.query(func.count(SmsNotification.id)).scalar() or 0,
        reviews=db.query(func.count(Review.id)).scalar() or 0,
    )


@router.get("/users", response_model=list[AdminUserRead])
async def list_users(
    keyword: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AdminUserRead]:
    query = db.query(User)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.phone.like(like), User.display_name.like(like)))
    if status_filter:
        query = query.filter(User.status == status_filter)
    users = query.order_by(User.created_at.desc()).limit(limit).all()
    return [
        AdminUserRead(
            id=user.id,
            phone=user.phone,
            display_name=user.display_name,
            status=user.status,
            active_role=user.active_role,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.patch("/users/{user_id}/status", response_model=AdminUserRead)
async def update_user_status(
    user_id: str,
    payload: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
) -> AdminUserRead:
    user = _get_user(db, user_id)
    old_status = user.status
    user.status = payload.status
    _log_admin_action(
        db,
        action="user.status_update",
        admin_id=payload.admin_id,
        target_type="user",
        target_id=user.id,
        target=user.phone,
        detail={"old_status": old_status, "new_status": payload.status, "reason": payload.reason},
    )
    db.commit()
    db.refresh(user)
    return AdminUserRead(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
        status=user.status,
        active_role=user.active_role,
        created_at=user.created_at,
    )


@router.get("/certifications", response_model=list[AdminCertificationRead])
async def list_certifications(
    status_filter: str | None = Query(default="pending", alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AdminCertificationRead]:
    query = db.query(Certification).join(CaregiverProfile)
    if status_filter:
        query = query.filter(Certification.review_status == status_filter)
    certifications = query.order_by(Certification.created_at.desc()).limit(limit).all()
    return [_certification_read(item) for item in certifications]


@router.post("/certifications/{certification_id}/review", response_model=AdminCertificationRead)
async def review_certification(
    certification_id: str,
    payload: AdminCertificationReview,
    db: Session = Depends(get_db),
) -> AdminCertificationRead:
    certification = db.query(Certification).filter(Certification.id == certification_id).first()
    if not certification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found")

    old_status = certification.review_status
    certification.review_status = payload.review_status
    certification.review_note = payload.review_note
    caregiver = certification.caregiver_profile
    if caregiver:
        caregiver.verification_status = payload.review_status
        caregiver.id_verified = payload.review_status == "approved"
        role = db.query(UserRole).filter(UserRole.user_id == caregiver.user_id, UserRole.role == "caregiver").first()
        if role:
            role.verification_status = payload.review_status

    _log_admin_action(
        db,
        action="certification.review",
        admin_id=payload.admin_id,
        target_type="certification",
        target_id=certification.id,
        target=certification.certificate_type,
        detail={"old_status": old_status, "new_status": payload.review_status, "note": payload.review_note},
    )
    db.commit()
    if caregiver and caregiver.user.phone:
        await SmsNotificationService().create_and_send(
            db,
            scene="verification_result",
            user_id=caregiver.user_id,
            phone=caregiver.user.phone,
            payload={
                "certification_id": certification.id,
                "certificate_type": certification.certificate_type,
                "status": certification.review_status,
            },
        )
    db.refresh(certification)
    return _certification_read(certification)


@router.get("/content/ai-messages", response_model=list[AdminAiMessageRead])
async def list_ai_messages(
    intent_category: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AdminAiMessageRead]:
    query = db.query(AiMessage)
    if intent_category:
        query = query.filter(AiMessage.intent_category == intent_category)
    messages = query.order_by(AiMessage.created_at.desc()).limit(limit).all()
    return [
        AdminAiMessageRead(
            id=item.id,
            session_id=item.session_id,
            sender=item.sender,
            content=item.content or item.user_message or item.assistant_message or "",
            intent_category=item.intent_category,
            intent_subcategory=item.intent_subcategory,
            intent_confidence=item.intent_confidence,
            cache_hit_level=item.cache_hit_level,
            created_at=item.created_at,
        )
        for item in messages
    ]


@router.get("/content/chat-messages", response_model=list[AdminChatMessageRead])
async def list_chat_messages(
    conversation_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AdminChatMessageRead]:
    query = db.query(Message)
    if conversation_id:
        query = query.filter(Message.conversation_id == conversation_id)
    messages = query.order_by(Message.created_at.desc()).limit(limit).all()
    return [
        AdminChatMessageRead(
            id=item.id,
            conversation_id=item.conversation_id,
            sender_id=item.sender_id,
            sender_type=item.sender_type,
            body=item.body,
            content=item.content,
            attachment_url=item.attachment_url,
            created_at=item.created_at,
        )
        for item in messages
    ]


@router.get("/ai-model-configs", response_model=list[AdminAiModelConfigRead])
async def list_ai_model_configs(db: Session = Depends(get_db)) -> list[AiModelConfig]:
    return db.query(AiModelConfig).order_by(AiModelConfig.is_active.desc(), AiModelConfig.created_at.desc()).all()


@router.post("/ai-model-configs", response_model=AdminAiModelConfigRead, status_code=status.HTTP_201_CREATED)
async def create_ai_model_config(
    payload: AdminAiModelConfigCreate,
    db: Session = Depends(get_db),
) -> AiModelConfig:
    if payload.is_active:
        db.query(AiModelConfig).update({"is_active": False})
    config = AiModelConfig(**payload.model_dump(exclude={"admin_id"}))
    db.add(config)
    db.flush()
    _log_admin_action(
        db,
        action="ai_model_config.create",
        admin_id=payload.admin_id,
        target_type="ai_model_config",
        target_id=config.id,
        target=config.model_name,
        detail={"provider": config.provider, "is_active": config.is_active},
    )
    db.commit()
    db.refresh(config)
    return config


@router.patch("/ai-model-configs/{config_id}", response_model=AdminAiModelConfigRead)
async def update_ai_model_config(
    config_id: str,
    payload: AdminAiModelConfigUpdate,
    db: Session = Depends(get_db),
) -> AiModelConfig:
    config = db.query(AiModelConfig).filter(AiModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI model config not found")
    updates = payload.model_dump(exclude_unset=True, exclude={"admin_id"})
    if updates.get("is_active") is True:
        db.query(AiModelConfig).filter(AiModelConfig.id != config_id).update({"is_active": False})
    for key, value in updates.items():
        setattr(config, key, value)
    _log_admin_action(
        db,
        action="ai_model_config.update",
        admin_id=payload.admin_id,
        target_type="ai_model_config",
        target_id=config.id,
        target=config.model_name,
        detail=updates,
    )
    db.commit()
    db.refresh(config)
    return config


@router.post("/ai-model-configs/{config_id}/activate", response_model=AdminAiModelConfigRead)
async def activate_ai_model_config(
    config_id: str,
    admin_id: str | None = None,
    db: Session = Depends(get_db),
) -> AiModelConfig:
    config = db.query(AiModelConfig).filter(AiModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI model config not found")
    db.query(AiModelConfig).update({"is_active": False})
    config.is_active = True
    _log_admin_action(
        db,
        action="ai_model_config.activate",
        admin_id=admin_id,
        target_type="ai_model_config",
        target_id=config.id,
        target=config.model_name,
        detail={"provider": config.provider},
    )
    db.commit()
    db.refresh(config)
    return config


@router.delete("/ai-model-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_model_config(
    config_id: str,
    admin_id: str | None = None,
    db: Session = Depends(get_db),
) -> None:
    config = db.query(AiModelConfig).filter(AiModelConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI model config not found")
    if config.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active AI model config cannot be deleted")
    _log_admin_action(
        db,
        action="ai_model_config.delete",
        admin_id=admin_id,
        target_type="ai_model_config",
        target_id=config.id,
        target=config.model_name,
        detail={"provider": config.provider},
    )
    db.delete(config)
    db.commit()


@router.get("/logs", response_model=list[AdminLogRead])
async def list_admin_logs(
    action: str | None = None,
    target_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AdminLog]:
    query = db.query(AdminLog)
    if action:
        query = query.filter(AdminLog.action == action)
    if target_type:
        query = query.filter(AdminLog.target_type == target_type)
    return query.order_by(AdminLog.created_at.desc()).limit(limit).all()
