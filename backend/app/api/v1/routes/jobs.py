from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.models import (
    Application,
    CaregiverProfile,
    Conversation,
    Invitation,
    JobPosting,
    User,
    UserRole,
)
from backend.app.db.session import get_db
from backend.app.recommendation.service import (
    rank_available_caregivers,
    record_interaction,
)
from backend.app.schemas.jobs import (
    ApplicationCreate,
    ApplicationDecision,
    ApplicationRead,
    AvailableCaregiverRead,
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

OPEN_JOB_STATUSES = {"published"}
JOB_STATUS_TRANSITIONS = {
    "draft": {"published", "cancelled"},
    "published": {"matched", "closed", "cancelled"},
    "matched": {"closed"},
    "closed": set(),
    "cancelled": set(),
}


def _get_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _get_job(
    db: Session,
    job_id: str,
    *,
    for_update: bool = False,
) -> JobPosting:
    query = db.query(JobPosting).filter(JobPosting.id == job_id)
    if for_update:
        query = query.with_for_update()
    job = query.first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job posting not found")
    return job


def _user_has_role(user: User, role_name: str) -> bool:
    return any(role.role == role_name for role in user.roles)


def _require_role(user: User, role_name: str) -> None:
    if user.active_role != role_name or not _user_has_role(user, role_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Active role must be: {role_name}",
        )


def _require_job_owner(job: JobPosting, current_user: User) -> None:
    if job.employer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the job owner can perform this action",
        )


def _get_verified_caregiver(db: Session, caregiver_id: str) -> CaregiverProfile:
    profile = (
        db.query(CaregiverProfile)
        .join(User, User.id == CaregiverProfile.user_id)
        .join(
            UserRole,
            (UserRole.user_id == CaregiverProfile.user_id)
            & (UserRole.role == "caregiver"),
        )
        .filter(
            CaregiverProfile.user_id == caregiver_id,
            CaregiverProfile.id_verified.is_(True),
            CaregiverProfile.verification_status == "approved",
            CaregiverProfile.is_available.is_(True),
            User.status == "active",
            UserRole.verification_status == "approved",
        )
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caregiver identity and qualifications must be approved",
        )
    return profile


def _public_job_text(value: str) -> str:
    public_prefixes = (
        "护理时间：",
        "薪资酬劳：",
        "护理要求：",
    )
    safe_lines = [
        line.strip()
        for line in (value or "").splitlines()
        if line.strip().startswith(public_prefixes)
    ]
    return "\n".join(safe_lines)


def _job_read(job: JobPosting, *, owner_view: bool) -> JobPostingRead:
    result = JobPostingRead.model_validate(job)
    if owner_view:
        return result
    return result.model_copy(
        update={
            "patient_id": None,
            "location": job.city or "",
            "description": _public_job_text(job.description),
            "special_requirements": _public_job_text(job.special_requirements),
        }
    )


def _idempotency_key(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if len(normalized) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key must be 64 characters or fewer",
        )
    return normalized


def _get_application(
    db: Session,
    application_id: str,
    *,
    for_update: bool = False,
) -> Application:
    query = db.query(Application).filter(Application.id == application_id)
    if for_update:
        query = query.with_for_update()
    application = query.first()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def _get_invitation(
    db: Session,
    invitation_id: str,
    *,
    for_update: bool = False,
) -> Invitation:
    query = db.query(Invitation).filter(Invitation.id == invitation_id)
    if for_update:
        query = query.with_for_update()
    invitation = query.first()
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
async def create_job(
    payload: JobPostingCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> JobPostingRead:
    _require_role(current_user, "patient")
    if payload.employer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The authenticated user must be the employer",
        )
    patient_id = payload.patient_id or current_user.id
    if patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot publish a job for another patient",
        )
    job = JobPosting(**payload.model_dump(exclude={"patient_id"}), patient_id=patient_id, status="published")
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_read(job, owner_view=True)


@router.get("", response_model=list[JobPostingRead])
async def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    status_filter: str | None = Query(default=None, alias="status"),
    city: str | None = None,
    care_type: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> list[JobPostingRead]:
    query = db.query(JobPosting).filter(
        or_(
            JobPosting.employer_id == current_user.id,
            JobPosting.status == "published",
        )
    )
    if status_filter:
        query = query.filter(JobPosting.status == status_filter)
    if city:
        query = query.filter(JobPosting.city == city)
    if care_type:
        query = query.filter(JobPosting.care_type == care_type)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(JobPosting.title.like(like), JobPosting.description.like(like)))
    jobs = query.order_by(JobPosting.created_at.desc()).limit(100).all()
    return [
        _job_read(job, owner_view=job.employer_id == current_user.id)
        for job in jobs
    ]


@router.get("/caregivers/{caregiver_id}/applications", response_model=list[ApplicationRead])
async def list_caregiver_applications(
    caregiver_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> list[Application]:
    _require_role(current_user, "caregiver")
    if caregiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view another caregiver's applications",
        )
    return (
        db.query(Application)
        .filter(Application.caregiver_id == caregiver_id)
        .order_by(Application.created_at.desc())
        .all()
    )


@router.post("/applications/{application_id}/review", response_model=MatchResult)
async def review_application(
    application_id: str,
    payload: ApplicationDecision,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> MatchResult:
    _require_role(current_user, "patient")
    application = _get_application(db, application_id, for_update=True)
    job = _get_job(db, application.job_id, for_update=True)
    _require_job_owner(job, current_user)
    if application.status != "pending":
        if application.status == payload.status:
            existing = _find_existing_conversation(db, "application", application.id)
            return MatchResult(status=application.status, conversation=existing)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application has already been reviewed",
        )
    conversation = None
    if payload.status == "accepted":
        if job.status != "published":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job is no longer available for matching",
            )
        _get_verified_caregiver(db, application.caregiver_id)
    application.status = payload.status
    if payload.status == "accepted":
        job.status = "matched"
        _set_caregiver_available(db, application.caregiver_id, False)
        conversation = _create_match_conversation(
            db,
            patient_id=job.employer_id,
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
    record_interaction(
        db,
        patient_id=job.employer_id,
        caregiver_id=application.caregiver_id,
        job_id=job.id,
        action_type="accept" if application.status == "accepted" else "reject",
        context={"source": "application_review"},
    )
    return MatchResult(status=application.status, conversation=conversation)


@router.get("/caregivers/available", response_model=list[AvailableCaregiverRead])
async def list_available_caregivers(
    current_user: Annotated[User, Depends(get_current_user)],
    city: str | None = None,
    keyword: str | None = None,
    min_experience: int | None = Query(default=None, ge=0, le=80),
    patient_id: str | None = None,
    job_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[AvailableCaregiverRead]:
    _require_role(current_user, "patient")
    if patient_id and patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot request recommendations for another user",
        )
    if job_id:
        job = _get_job(db, job_id)
        _require_job_owner(job, current_user)
    query = (
        db.query(CaregiverProfile)
        .join(User, User.id == CaregiverProfile.user_id)
        .join(
            UserRole,
            (UserRole.user_id == CaregiverProfile.user_id)
            & (UserRole.role == "caregiver"),
        )
        .filter(
            CaregiverProfile.is_available.is_(True),
            CaregiverProfile.id_verified.is_(True),
            CaregiverProfile.verification_status == "approved",
            User.status == "active",
            UserRole.verification_status == "approved",
        )
    )
    if city:
        query = query.filter(CaregiverProfile.service_city == city)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(CaregiverProfile.real_name.like(like), CaregiverProfile.bio.like(like)))
    if min_experience is not None:
        query = query.filter(CaregiverProfile.experience_years >= min_experience)

    profiles = query.limit(500).all()
    profiles = rank_available_caregivers(
        db,
        profiles,
        patient_id=current_user.id,
        job_id=job_id,
        filters={
            "city": city,
            "keyword": keyword,
            "min_experience": min_experience,
        },
    )[:100]
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
async def create_invitation(
    payload: InvitationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    idempotency_header: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
    db: Session = Depends(get_db),
) -> Invitation:
    _require_role(current_user, "patient")
    if payload.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create an invitation for another patient",
        )
    key = _idempotency_key(idempotency_header)
    if key:
        existing_by_key = (
            db.query(Invitation)
            .filter(
                Invitation.patient_id == current_user.id,
                Invitation.idempotency_key == key,
            )
            .first()
        )
        if existing_by_key:
            if (
                existing_by_key.caregiver_id != payload.caregiver_id
                or existing_by_key.job_id != payload.job_id
                or existing_by_key.message != payload.message
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key was already used for another invitation",
                )
            return existing_by_key
    _get_verified_caregiver(db, payload.caregiver_id)
    if not payload.job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A published job is required for an invitation",
        )
    job = _get_job(db, payload.job_id, for_update=True)
    _require_job_owner(job, current_user)
    if job.status != "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only published jobs can send invitations",
        )

    existing_query = db.query(Invitation).filter(
        Invitation.patient_id == current_user.id,
        Invitation.caregiver_id == payload.caregiver_id,
        Invitation.status == "pending",
    )
    if payload.job_id:
        existing_query = existing_query.filter(Invitation.job_id == payload.job_id)
    existing = existing_query.first()
    if existing:
        return existing

    invitation = Invitation(
        **payload.model_dump(),
        status="pending",
        idempotency_key=key,
    )
    db.add(invitation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if key:
            existing_by_key = (
                db.query(Invitation)
                .filter(Invitation.idempotency_key == key)
                .first()
            )
            if existing_by_key:
                if (
                    existing_by_key.patient_id == current_user.id
                    and existing_by_key.caregiver_id == payload.caregiver_id
                    and existing_by_key.job_id == payload.job_id
                    and existing_by_key.message == payload.message
                ):
                    return existing_by_key
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key was already used for another invitation",
                ) from None
        existing = db.query(Invitation).filter(
            Invitation.patient_id == current_user.id,
            Invitation.caregiver_id == payload.caregiver_id,
            Invitation.job_id == payload.job_id,
        ).first()
        if existing:
            return existing
        raise
    db.refresh(invitation)
    await _notify_user(
        db,
        user_id=invitation.caregiver_id,
        scene="new_invitation",
        payload={"invitation_id": invitation.id, "job_id": invitation.job_id or "", "patient_id": invitation.patient_id},
    )
    record_interaction(
        db,
        patient_id=invitation.patient_id,
        caregiver_id=invitation.caregiver_id,
        job_id=invitation.job_id,
        action_type="invite",
        context={"source": "invitation"},
    )
    return invitation


@router.get("/invitations", response_model=list[InvitationRead])
async def list_invitations(
    current_user: Annotated[User, Depends(get_current_user)],
    patient_id: str | None = None,
    caregiver_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Invitation]:
    query = db.query(Invitation)
    if current_user.active_role == "caregiver":
        if caregiver_id and caregiver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view another caregiver's invitations",
            )
        query = query.filter(Invitation.caregiver_id == current_user.id)
    else:
        _require_role(current_user, "patient")
        if patient_id and patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view another patient's invitations",
            )
        query = query.filter(Invitation.patient_id == current_user.id)
    if status_filter:
        query = query.filter(Invitation.status == status_filter)
    return query.order_by(Invitation.created_at.desc()).limit(100).all()


@router.post("/invitations/{invitation_id}/respond", response_model=MatchResult)
async def respond_invitation(
    invitation_id: str,
    payload: InvitationDecision,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> MatchResult:
    _require_role(current_user, "caregiver")
    invitation = _get_invitation(db, invitation_id, for_update=True)
    if invitation.caregiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the invited caregiver can respond",
        )
    if invitation.status != "pending":
        if invitation.status == payload.status:
            existing = _find_existing_conversation(db, "invitation", invitation.id)
            return MatchResult(status=invitation.status, conversation=existing)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invitation has already been answered",
        )
    conversation = None
    if payload.status == "accepted":
        _get_verified_caregiver(db, invitation.caregiver_id)
        if invitation.job_id:
            job = _get_job(db, invitation.job_id, for_update=True)
            if job.status != "published":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Job is no longer available for matching",
                )
            job.status = "matched"
    invitation.status = payload.status
    invitation.responded_at = datetime.now(UTC)
    if payload.status == "accepted":
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
    record_interaction(
        db,
        patient_id=invitation.patient_id,
        caregiver_id=invitation.caregiver_id,
        job_id=invitation.job_id,
        action_type="accept" if invitation.status == "accepted" else "reject",
        context={"source": "invitation_response"},
    )
    return MatchResult(status=invitation.status, conversation=conversation)


@router.get("/{job_id}", response_model=JobPostingRead)
async def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> JobPostingRead:
    job = _get_job(db, job_id)
    owner_view = job.employer_id == current_user.id
    if not owner_view and job.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job posting not found",
        )
    return _job_read(job, owner_view=owner_view)


@router.patch("/{job_id}/status", response_model=JobPostingRead)
async def update_job_status(
    job_id: str,
    payload: JobStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> JobPostingRead:
    _require_role(current_user, "patient")
    job = _get_job(db, job_id, for_update=True)
    _require_job_owner(job, current_user)
    if payload.status == job.status:
        return _job_read(job, owner_view=True)
    allowed = JOB_STATUS_TRANSITIONS.get(job.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot change job status from {job.status} to {payload.status}",
        )
    job.status = payload.status
    db.commit()
    db.refresh(job)
    return _job_read(job, owner_view=True)


@router.post("/{job_id}/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def apply_job(
    job_id: str,
    payload: ApplicationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    idempotency_header: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
    db: Session = Depends(get_db),
) -> Application:
    _require_role(current_user, "caregiver")
    if payload.caregiver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit an application for another caregiver",
        )
    key = _idempotency_key(idempotency_header)
    if key:
        existing_by_key = (
            db.query(Application)
            .filter(
                Application.caregiver_id == current_user.id,
                Application.idempotency_key == key,
            )
            .first()
        )
        if existing_by_key:
            if (
                existing_by_key.job_id != job_id
                or existing_by_key.cover_letter != payload.cover_letter
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key was already used for another application",
                )
            return existing_by_key
    _get_verified_caregiver(db, current_user.id)
    job = _get_job(db, job_id, for_update=True)
    if job.status not in OPEN_JOB_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is not open for applications")
    if job.employer_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot apply to your own job",
        )
    existing = (
        db.query(Application)
        .filter(Application.job_id == job_id, Application.caregiver_id == current_user.id)
        .first()
    )
    if existing:
        return existing

    application = Application(
        job_id=job_id,
        caregiver_id=current_user.id,
        status="pending",
        cover_letter=payload.cover_letter,
        idempotency_key=key,
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if key:
            existing_by_key = (
                db.query(Application)
                .filter(Application.idempotency_key == key)
                .first()
            )
            if existing_by_key:
                if (
                    existing_by_key.caregiver_id == current_user.id
                    and existing_by_key.job_id == job_id
                    and existing_by_key.cover_letter == payload.cover_letter
                ):
                    return existing_by_key
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key was already used for another application",
                ) from None
        existing = db.query(Application).filter(
            Application.job_id == job_id,
            Application.caregiver_id == current_user.id,
        ).first()
        if existing:
            return existing
        raise
    db.refresh(application)
    await _notify_user(
        db,
        user_id=job.employer_id,
        scene="new_application",
        payload={"job_id": job.id, "job_title": job.title, "caregiver_id": application.caregiver_id},
    )
    return application


@router.get("/{job_id}/applications", response_model=list[ApplicationRead])
async def list_job_applications(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> list[Application]:
    _require_role(current_user, "patient")
    job = _get_job(db, job_id)
    _require_job_owner(job, current_user)
    return (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .order_by(Application.created_at.desc())
        .all()
    )
