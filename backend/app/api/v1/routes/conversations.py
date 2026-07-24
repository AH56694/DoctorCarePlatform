from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.models import (
    Application,
    CaregiverProfile,
    Conversation,
    Invitation,
    JobPosting,
    Message,
    User,
    UserRole,
)
from backend.app.db.session import get_db
from backend.app.recommendation.service import record_interaction
from backend.app.schemas.conversations import (
    ConversationCreate,
    ConversationRead,
    MessageCreate,
    MessageRead,
)
from backend.app.services.message_cache import message_cache

router = APIRouter()


def _get_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _get_conversation(db: Session, conversation_id: str) -> Conversation:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def _is_participant(conversation: Conversation, user_id: str) -> bool:
    return user_id in {conversation.participant_a, conversation.participant_b}


def _default_title(db: Session, participant_a: str, participant_b: str) -> str:
    left = _get_user(db, participant_a)
    right = _get_user(db, participant_b)
    return f"{left.display_name or left.phone} / {right.display_name or right.phone}"


def _record_recruitment_chat(
    db: Session,
    payload: ConversationCreate,
) -> None:
    if payload.source_type not in {"profile", "job", "application", "invitation"}:
        return
    patient_id: str | None = None
    caregiver_id: str | None = None
    job_id: str | None = None
    if payload.source_type == "job":
        job_id = payload.source_id
        job = (
            db.query(JobPosting)
            .filter(JobPosting.id == payload.source_id)
            .first()
        )
        if job:
            patient_id = job.employer_id
            caregiver_id = next(
                (
                    participant
                    for participant in {
                        payload.participant_a,
                        payload.participant_b,
                    }
                    if participant != job.employer_id
                ),
                None,
            )
    elif payload.source_type == "application" and payload.source_id:
        application = (
            db.query(Application)
            .filter(Application.id == payload.source_id)
            .first()
        )
        if application:
            job = (
                db.query(JobPosting)
                .filter(JobPosting.id == application.job_id)
                .first()
            )
            job_id = application.job_id
            patient_id = job.employer_id if job else None
            caregiver_id = application.caregiver_id
    elif payload.source_type == "invitation" and payload.source_id:
        invitation = (
            db.query(Invitation)
            .filter(Invitation.id == payload.source_id)
            .first()
        )
        if invitation:
            patient_id = invitation.patient_id
            caregiver_id = invitation.caregiver_id
            job_id = invitation.job_id
    elif payload.source_type == "profile":
        participants = (
            db.query(User)
            .filter(
                User.id.in_(
                    [payload.participant_a, payload.participant_b]
                )
            )
            .all()
        )
        patient = next(
            (user for user in participants if user.active_role == "patient"),
            None,
        )
        candidate = next(
            (
                user
                for user in participants
                if user.id != (patient.id if patient else "")
                and _is_approved_caregiver(db, user.id)
            ),
            None,
        )
        if patient and candidate:
            patient_id = patient.id
            caregiver_id = candidate.id
    if not patient_id or not caregiver_id:
        return
    record_interaction(
        db,
        patient_id=patient_id,
        caregiver_id=caregiver_id,
        job_id=job_id,
        action_type="chat",
        context={
            "source_type": payload.source_type,
            "source_id": payload.source_id or "",
        },
    )


def _is_approved_caregiver(db: Session, user_id: str) -> bool:
    return (
        db.query(CaregiverProfile)
        .join(User, User.id == CaregiverProfile.user_id)
        .join(
            UserRole,
            (UserRole.user_id == CaregiverProfile.user_id)
            & (UserRole.role == "caregiver"),
        )
        .filter(
            CaregiverProfile.user_id == user_id,
            CaregiverProfile.id_verified.is_(True),
            CaregiverProfile.verification_status == "approved",
            User.status == "active",
            UserRole.verification_status == "approved",
        )
        .first()
        is not None
    )


def _validate_source_participants(db: Session, payload: ConversationCreate) -> None:
    participants = {payload.participant_a, payload.participant_b}
    if payload.source_type == "job" and payload.source_id:
        job = db.query(JobPosting).filter(JobPosting.id == payload.source_id).first()
        caregiver_id = next(
            (
                participant
                for participant in participants
                if job and participant != job.employer_id
            ),
            None,
        )
        if (
            not job
            or job.status != "published"
            or job.employer_id not in participants
            or not caregiver_id
            or not _is_approved_caregiver(db, caregiver_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation participants do not match the job",
            )
    if payload.source_type == "application" and payload.source_id:
        application = (
            db.query(Application)
            .filter(Application.id == payload.source_id)
            .first()
        )
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found",
            )
        job = db.query(JobPosting).filter(JobPosting.id == application.job_id).first()
        expected = {application.caregiver_id, job.employer_id if job else ""}
        if participants != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation participants do not match the application",
            )
    if payload.source_type == "invitation" and payload.source_id:
        invitation = (
            db.query(Invitation)
            .filter(Invitation.id == payload.source_id)
            .first()
        )
        expected = (
            {invitation.patient_id, invitation.caregiver_id}
            if invitation
            else set()
        )
        if participants != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation participants do not match the invitation",
            )


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> Conversation:
    if payload.participant_a == payload.participant_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Participants cannot be the same")
    if payload.participant_a != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="participant_a must be the authenticated user",
        )
    _get_user(db, payload.participant_a)
    _get_user(db, payload.participant_b)
    _validate_source_participants(db, payload)

    query = db.query(Conversation).filter(
        Conversation.kind == "care_chat",
        Conversation.participant_a.in_([payload.participant_a, payload.participant_b]),
        Conversation.participant_b.in_([payload.participant_a, payload.participant_b]),
    )
    if payload.source_type and payload.source_id:
        query = query.filter(Conversation.source_type == payload.source_type, Conversation.source_id == payload.source_id)
    existing = query.first()
    if existing:
        return existing

    conversation = Conversation(
        owner_id=payload.participant_a,
        participant_a=payload.participant_a,
        participant_b=payload.participant_b,
        kind="care_chat",
        source_type=payload.source_type,
        source_id=payload.source_id,
        title=payload.title or _default_title(db, payload.participant_a, payload.participant_b),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    _record_recruitment_chat(db, payload)
    return conversation


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: str = Query(...),
    db: Session = Depends(get_db),
) -> list[Conversation]:
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot list another user's conversations",
        )
    return (
        db.query(Conversation)
        .filter(or_(Conversation.participant_a == user_id, Conversation.participant_b == user_id))
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
        .limit(100)
        .all()
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: str = Query(...),
    db: Session = Depends(get_db),
) -> list[Message]:
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot read messages as another user",
        )
    conversation = _get_conversation(db, conversation_id)
    if not _is_participant(conversation, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only participants can read messages")
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(200)
        .all()
    )


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message(
    conversation_id: str,
    payload: MessageCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> Message:
    conversation = _get_conversation(db, conversation_id)
    if payload.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="sender_id must be the authenticated user",
        )
    if not _is_participant(conversation, payload.sender_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only participants can send messages")
    message = Message(
        conversation_id=conversation_id,
        sender_id=payload.sender_id,
        sender_type="user",
        body=payload.body,
        content=payload.body,
        attachment_url=payload.attachment_url,
        attachment_type=payload.attachment_type,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    message_cache.add_message(
        "care",
        conversation_id,
        {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "sender_type": message.sender_type,
            "body": message.body,
            "content": message.content,
            "attachment_url": message.attachment_url,
            "attachment_type": message.attachment_type,
            "created_at": message.created_at,
        },
    )
    return message
