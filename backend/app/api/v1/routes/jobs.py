from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Application,
    CaregiverProfile,
    Conversation,
    Invitation,
    JobPosting,
    User,
)
from backend.app.db.session import get_db
from backend.app.schemas.jobs import (
    ApplicationCreate,
    ApplicationDecision,
    ApplicationRead,
    AvailableCaregiverRead,
    ConversationRead,
    InvitationCreate,
    InvitationDecision,
    InvitationRead,
    JobPostingCreate,
    JobPostingRead,
    JobStatusUpdate,
    MatchResult,
)
from backend.app.services.sms import SmsNotificationService

router = APIRouter()

OPEN_JOB_STATUSES = {"published", "matched"}


def _get_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _get_job(db: Session, job_id: str) -> JobPosting:
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found")
    return job


def _get_application(db: Session, application_id: str) -> Application:
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def _get_invitation(db: Session, invitation_id: str) -> Invitation:
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


def _conversation_title(patient: User, caregiver: User) -> str:
    left = patient.display_name or patient.phone
    right = caregiver.display_name or caregiver.phone
    return f"{left} / {right}"


def _find_existing_conversation(db: Session, source_type: str, source_id: str) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(Conversation.source_type == source_type, Conversation.source_id == source_id)
        .first()
    )


def _create_match_conversation(
    db: Session,
    *,
    patient_id: str,
    caregiver_id: str,
    source_type: str,
    source_id: str,
) -> Conversation:
    existing = _find_existing_conversation(db, source_type, source_id)
    if existing:
        return existing

    patient = _get_user(db, patient_id)
    caregiver = _get_user(db, caregiver_id)
    conversation = Conversation(
        owner_id=patient_id,
        participant_a=patient_id,
        participant_b=caregiver_id,
        kind="care_chat",
        source_type=source_type,
        source_id=source_id,
        title=_conversation_title(patient, caregiver),
    )
    db.add(conversation)
    return conversation


def _set_caregiver_available(db: Session, user_id: str, is_available: bool) -> None:
    profile = db.query(CaregiverProfile).filter(CaregiverProfile.user_id == user_id).first()
    if profile:
        profile.is_available = is_available


async def _notify_user(db: Session, *, user_id: str, scene: str, payload: dict) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.phone:
        return
    await SmsNotificationService().create_and_send(
        db,
        scene=scene,
        user_id=user.id,
        phone=user.phone,
        payload=payload,
    )


@router.post("", response_model=JobPostingRead, status_code=status.HTTP_201_CREATED)
async def create_job(payload: JobPostingCreate, db: Session = Depends(get_db)) -> JobPosting:
    _get_user(db, payload.employer_id)
    patient_id = payload.patient_id or payload.employer_id
    _get_user(db, patient_id)
    job = JobPosting(**payload.model_dump(exclude={"patient_id"}), patient_id=patient_id, status="published")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[JobPostingRead])
async def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    city: str | None = None,
    care_type: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> list[JobPosting]:
    query = db.query(JobPosting)
    if status_filter:
        query = query.filter(JobPosting.status == status_filter)
    if city:
        query = query.filter(JobPosting.city == city)
    if care_type:
        query = query.filter(JobPosting.care_type == care_type)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(JobPosting.title.like(like), JobPosting.description.like(like)))
    return query.order_by(JobPosting.created_at.desc()).limit(100).all()


@router.get("/caregivers/{caregiver_id}/applications", response_model=list[ApplicationRead])
async def list_caregiver_applications(caregiver_id: str, db: Session = Depends(get_db)) -> list[Application]:
    _get_user(db, caregiver_id)
    return (
        db.query(Application)
        .filter(Application.caregiver_id == caregiver_id)
        .order_by(Application.created_at.desc())
        .all()
    )


@router.post("/applications/{application_id}/review", response_model=MatchResult)
async def review_application(
    application_id: str, payload: ApplicationDecision, db: Session = Depends(get_db)
) -> MatchResult:
    application = _get_application(db, application_id)
    job = _get_job(db, application.job_id)
    application.status = payload.status

    conversation = None
    if payload.status == "accepted":
        job.status = "matched"
        _set_caregiver_available(db, application.caregiver_id, False)
        conversation = _create_match_conversation(
            db,
            patient_id=job.patient_id or job.employer_id,
            caregiver_id=application.caregiver_id,
            source_type="application",
            source_id=application.id,
        )

    db.commit()
    if conversation:
        db.refresh(conversation)
    await _notify_user(
        db,
        user_id=application.caregiver_id,
        scene="application_review",
        payload={"job_id": job.id, "job_title": job.title, "status": application.status},
    )
    return MatchResult(status=application.status, conversation=conversation)


@router.get("/caregivers/available", response_model=list[AvailableCaregiverRead])
async def list_available_caregivers(
    city: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> list[AvailableCaregiverRead]:
    query = db.query(CaregiverProfile).filter(CaregiverProfile.is_available.is_(True))
    if city:
        query = query.filter(CaregiverProfile.service_city == city)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(CaregiverProfile.real_name.like(like), CaregiverProfile.bio.like(like)))

    profiles = query.order_by(CaregiverProfile.rating_avg.desc(), CaregiverProfile.created_at.desc()).limit(100).all()
    return [
        AvailableCaregiverRead(
            user_id=profile.user_id,
            real_name=profile.real_name,
            bio=profile.bio,
            service_city=profile.service_city,
            experience_years=profile.experience_years,
            rating_avg=profile.rating_avg,
            is_available=profile.is_available,
        )
        for profile in profiles
    ]


@router.post("/invitations", response_model=InvitationRead, status_code=status.HTTP_201_CREATED)
async def create_invitation(payload: InvitationCreate, db: Session = Depends(get_db)) -> Invitation:
    _get_user(db, payload.patient_id)
    _get_user(db, payload.caregiver_id)
    if payload.job_id:
        _get_job(db, payload.job_id)

    existing_query = db.query(Invitation).filter(
        Invitation.patient_id == payload.patient_id,
        Invitation.caregiver_id == payload.caregiver_id,
        Invitation.status == "pending",
    )
    if payload.job_id:
        existing_query = existing_query.filter(Invitation.job_id == payload.job_id)
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pending invitation already exists")

    invitation = Invitation(**payload.model_dump(), status="pending")
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    await _notify_user(
        db,
        user_id=invitation.caregiver_id,
        scene="new_invitation",
        payload={"invitation_id": invitation.id, "job_id": invitation.job_id or "", "patient_id": invitation.patient_id},
    )
    return invitation


@router.get("/invitations", response_model=list[InvitationRead])
async def list_invitations(
    patient_id: str | None = None,
    caregiver_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Invitation]:
    query = db.query(Invitation)
    if patient_id:
        query = query.filter(Invitation.patient_id == patient_id)
    if caregiver_id:
        query = query.filter(Invitation.caregiver_id == caregiver_id)
    if status_filter:
        query = query.filter(Invitation.status == status_filter)
    return query.order_by(Invitation.created_at.desc()).limit(100).all()


@router.post("/invitations/{invitation_id}/respond", response_model=MatchResult)
async def respond_invitation(
    invitation_id: str, payload: InvitationDecision, db: Session = Depends(get_db)
) -> MatchResult:
    invitation = _get_invitation(db, invitation_id)
    invitation.status = payload.status
    invitation.responded_at = datetime.now(timezone.utc)

    conversation = None
    if payload.status == "accepted":
        if invitation.job_id:
            job = _get_job(db, invitation.job_id)
            job.status = "matched"
        _set_caregiver_available(db, invitation.caregiver_id, False)
        conversation = _create_match_conversation(
            db,
            patient_id=invitation.patient_id,
            caregiver_id=invitation.caregiver_id,
            source_type="invitation",
            source_id=invitation.id,
        )

    db.commit()
    if conversation:
        db.refresh(conversation)
    await _notify_user(
        db,
        user_id=invitation.patient_id,
        scene="invitation_response",
        payload={"invitation_id": invitation.id, "caregiver_id": invitation.caregiver_id, "status": invitation.status},
    )
    return MatchResult(status=invitation.status, conversation=conversation)


@router.get("/{job_id}", response_model=JobPostingRead)
async def get_job(job_id: str, db: Session = Depends(get_db)) -> JobPosting:
    return _get_job(db, job_id)


@router.patch("/{job_id}/status", response_model=JobPostingRead)
async def update_job_status(job_id: str, payload: JobStatusUpdate, db: Session = Depends(get_db)) -> JobPosting:
    job = _get_job(db, job_id)
    job.status = payload.status
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def apply_job(job_id: str, payload: ApplicationCreate, db: Session = Depends(get_db)) -> Application:
    job = _get_job(db, job_id)
    if job.status not in OPEN_JOB_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is not open for applications")
    _get_user(db, payload.caregiver_id)
    existing = (
        db.query(Application)
        .filter(Application.job_id == job_id, Application.caregiver_id == payload.caregiver_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Caregiver already applied to this job")

    application = Application(
        job_id=job_id,
        caregiver_id=payload.caregiver_id,
        status="pending",
        cover_letter=payload.cover_letter,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    await _notify_user(
        db,
        user_id=job.patient_id or job.employer_id,
        scene="new_application",
        payload={"job_id": job.id, "job_title": job.title, "caregiver_id": application.caregiver_id},
    )
    return application


@router.get("/{job_id}/applications", response_model=list[ApplicationRead])
async def list_job_applications(job_id: str, db: Session = Depends(get_db)) -> list[Application]:
    _get_job(db, job_id)
    return (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .order_by(Application.created_at.desc())
        .all()
    )
