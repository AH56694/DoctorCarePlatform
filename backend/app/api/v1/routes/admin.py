import asyncio
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.db.models import (
    AdminLog,
    AiKnowledgeChunk,
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
from backend.app.db.session import SessionLocal, get_db
from backend.app.schemas.admin import (
    AdminAiMessageRead,
    AdminAiModelConfigCreate,
    AdminAiModelConfigRead,
    AdminAiModelConfigUpdate,
    AdminCertificationRead,
    AdminCertificationReview,
    AdminChatMessageRead,
    AdminKnowledgeCreate,
    AdminKnowledgeRead,
    AdminLogRead,
    AdminSummaryRead,
    AdminUserRead,
    AdminUserStatusUpdate,
)
from backend.app.services.rag_client import RagServiceClient
from backend.app.services.sms import SmsNotificationService

router = APIRouter()

KNOWLEDGE_COLLECTIONS: dict[str, tuple[str, str]] = {
    "platform.general_knowledge": ("platform", "general_knowledge"),
    "medical.symptom_inquiry": ("medical", "symptom_inquiry"),
    "medical.medication_consult": ("medical", "medication_consult"),
    "medical.report_interpretation": ("medical", "report_interpretation"),
    "medical.care_method": ("medical", "care_method"),
    "platform.recruitment_process": ("platform", "recruitment_process"),
}


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


def _rag_doc_id(item_id: str) -> int:
    return UUID(item_id).int % 2_147_483_647 or 1


def _knowledge_read(item: AiKnowledgeChunk) -> AdminKnowledgeRead:
    metadata = item.metadata_json or {}
    return AdminKnowledgeRead(
        id=item.id,
        collection=item.collection,
        category=item.category,
        subcategory=item.subcategory,
        title=metadata.get("title", ""),
        content=item.content,
        file_name=metadata.get("file_name", ""),
        file_type=metadata.get("file_type", ""),
        rag_doc_id=metadata.get("rag_doc_id"),
        rag_status=metadata.get("rag_status", ""),
        rag_chunk_count=int(metadata.get("rag_chunk_count", 0) or 0),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


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


@router.get("/knowledge-items", response_model=list[AdminKnowledgeRead])
async def list_knowledge_items(
    collection: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AdminKnowledgeRead]:
    query = db.query(AiKnowledgeChunk)
    if collection:
        query = query.filter(AiKnowledgeChunk.collection == collection)
    rows = query.order_by(AiKnowledgeChunk.created_at.desc()).limit(limit).all()
    return [_knowledge_read(item) for item in rows]


@router.post("/knowledge-items", response_model=AdminKnowledgeRead, status_code=status.HTTP_201_CREATED)
async def create_knowledge_item(
    payload: AdminKnowledgeCreate,
    db: Session = Depends(get_db),
) -> AdminKnowledgeRead:
    if payload.collection not in KNOWLEDGE_COLLECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的知识库分类。")
    if not payload.content.strip() and not payload.file_content_base64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写知识内容或上传文件。")

    category, subcategory = KNOWLEDGE_COLLECTIONS[payload.collection]
    item = AiKnowledgeChunk(
        category=category,
        subcategory=subcategory,
        collection=payload.collection,
        content=payload.content.strip(),
        source_url=payload.file_name,
        metadata_json={
            "title": payload.title.strip(),
            "file_name": payload.file_name,
            "file_type": payload.file_type,
            "rag_status": "pending",
        },
    )
    db.add(item)
    db.flush()

    rag_doc_id = _rag_doc_id(item.id)
    item.metadata_json = {
        **(item.metadata_json or {}),
        "rag_doc_id": rag_doc_id,
        "rag_status": "pending",
        "rag_chunk_count": 0,
    }
    _log_admin_action(
        db,
        action="knowledge.ingest_queued",
        admin_id=payload.admin_id,
        target_type="ai_knowledge_chunk",
        target_id=item.id,
        target=payload.title,
        detail={"collection": payload.collection, "rag_doc_id": rag_doc_id},
    )
    db.commit()
    db.refresh(item)
    asyncio.create_task(
        _ingest_knowledge_background(
        item.id,
        payload.model_dump(),
        category,
        subcategory,
        rag_doc_id,
        )
    )
    return _knowledge_read(item)


async def _ingest_knowledge_background(
    item_id: str,
    payload_data: dict,
    category: str,
    subcategory: str,
    rag_doc_id: int,
) -> None:
    payload = AdminKnowledgeCreate(**payload_data)
    try:
        rag_result = await RagServiceClient().ingest_knowledge(
            {
                "doc_id": rag_doc_id,
                "title": payload.title.strip(),
                "collection": payload.collection,
                "category": category,
                "subcategory": subcategory,
                "content": payload.content.strip(),
                "file_name": payload.file_name,
                "file_type": payload.file_type,
                "file_content_base64": payload.file_content_base64,
                "source": payload.file_name or payload.title.strip(),
                "metadata": {"platform_knowledge_id": item_id, "admin_id": payload.admin_id},
            }
        )
    except Exception as exc:
        _mark_knowledge_ingest_failed(item_id, payload, rag_doc_id, str(exc))
        return

    db = SessionLocal()
    try:
        item = db.query(AiKnowledgeChunk).filter(AiKnowledgeChunk.id == item_id).first()
        if not item:
            return
        item.metadata_json = {
            **(item.metadata_json or {}),
            "rag_doc_id": rag_doc_id,
            "rag_status": "indexed",
            "rag_chunk_count": int(rag_result.get("chunks_count", 0) or 0),
            "rag_error": "",
        }
        _log_admin_action(
            db,
            action="knowledge.ingest",
            admin_id=payload.admin_id,
            target_type="ai_knowledge_chunk",
            target_id=item.id,
            target=payload.title,
            detail={"collection": payload.collection, "rag_doc_id": rag_doc_id, "rag_result": rag_result},
        )
        db.commit()
    finally:
        db.close()


def _mark_knowledge_ingest_failed(
    item_id: str,
    payload: AdminKnowledgeCreate,
    rag_doc_id: int,
    error: str,
) -> None:
    db = SessionLocal()
    try:
        item = db.query(AiKnowledgeChunk).filter(AiKnowledgeChunk.id == item_id).first()
        if not item:
            return
        item.metadata_json = {
            **(item.metadata_json or {}),
            "rag_doc_id": rag_doc_id,
            "rag_status": "failed",
            "rag_error": error,
        }
        _log_admin_action(
            db,
            action="knowledge.ingest_failed",
            admin_id=payload.admin_id,
            target_type="ai_knowledge_chunk",
            target_id=item.id,
            target=payload.title,
            detail={"collection": payload.collection, "error": error},
        )
        db.commit()
    finally:
        db.close()


@router.delete("/knowledge-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_item(
    item_id: str,
    admin_id: str | None = None,
    db: Session = Depends(get_db),
) -> None:
    item = db.query(AiKnowledgeChunk).filter(AiKnowledgeChunk.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识不存在。")

    metadata = item.metadata_json or {}
    rag_doc_id = metadata.get("rag_doc_id") or _rag_doc_id(item.id)
    try:
        await RagServiceClient().delete_knowledge(int(rag_doc_id))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="RAG 微服务删除失败，请稍后重试。") from exc

    _log_admin_action(
        db,
        action="knowledge.delete",
        admin_id=admin_id,
        target_type="ai_knowledge_chunk",
        target_id=item.id,
        target=metadata.get("title", item.source_url),
        detail={"collection": item.collection, "rag_doc_id": rag_doc_id},
    )
    db.delete(item)
    db.commit()


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
