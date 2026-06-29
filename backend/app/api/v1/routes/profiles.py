from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import (
    CaregiverProfile,
    Certification,
    JobPosting,
    MedicalCase,
    PatientProfile,
    Review,
    User,
)
from backend.app.db.session import get_db
from backend.app.schemas.profiles import (
    CaregiverAvailabilityUpdate,
    CaregiverResumeRead,
    PatientHomepageRead,
    ProfileJobRead,
    PublicCertificationRead,
    PublicMedicalCaseRead,
    PublicReviewRead,
)

router = APIRouter()

PUBLIC_CASE_VISIBILITIES = {"public", "matched", "summary_public"}


def _get_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _public_case_read(case: MedicalCase) -> PublicMedicalCaseRead:
    return PublicMedicalCaseRead(
        id=case.id,
        summary=case.summary or "",
        public_summary=case.public_summary or case.summary or "",
        visibility=case.visibility,
        attachments=case.attachments or [],
        updated_at=case.updated_at,
    )


def _job_read(job: JobPosting) -> ProfileJobRead:
    return ProfileJobRead(
        id=job.id,
        title=job.title,
        city=job.city,
        care_type=job.care_type,
        location=job.location,
        budget_cents=job.budget_cents,
        status=job.status,
        created_at=job.created_at,
    )


def _review_read(review: Review) -> PublicReviewRead:
    return PublicReviewRead(
        id=review.id,
        reviewer_id=review.reviewer_id,
        score=review.score,
        tags=review.tags or [],
        comment=review.comment or "",
        created_at=review.created_at,
    )


def _certification_read(certification: Certification) -> PublicCertificationRead:
    return PublicCertificationRead(
        id=certification.id,
        certificate_type=certification.certificate_type,
        file_url=certification.file_url,
        description=certification.description or "",
        review_status=certification.review_status,
    )


def _caregiver_resume_read(db: Session, profile: CaregiverProfile) -> CaregiverResumeRead:
    user = _get_user(db, profile.user_id)
    review_stats = (
        db.query(func.count(Review.id), func.coalesce(func.avg(Review.score), 0))
        .filter(Review.reviewee_id == profile.user_id)
        .one()
    )
    review_count = int(review_stats[0] or 0)
    rating_avg = float(review_stats[1] or profile.rating_avg or 0)
    recent_reviews = (
        db.query(Review)
        .filter(Review.reviewee_id == profile.user_id)
        .order_by(Review.created_at.desc())
        .limit(5)
        .all()
    )
    certifications = [
        _certification_read(item)
        for item in sorted(profile.certifications, key=lambda item: item.created_at, reverse=True)
        if item.review_status == "approved"
    ]
    return CaregiverResumeRead(
        user_id=profile.user_id,
        display_name=user.display_name,
        real_name=profile.real_name,
        id_verified=profile.id_verified,
        verification_status=profile.verification_status,
        bio=profile.bio or "",
        is_available=profile.is_available,
        experience_years=profile.experience_years,
        service_city=profile.service_city,
        rating_avg=rating_avg,
        review_count=review_count,
        certifications=certifications,
        recent_reviews=[_review_read(item) for item in recent_reviews],
    )


@router.get("/patients/{user_id}", response_model=PatientHomepageRead)
async def get_patient_homepage(user_id: str, db: Session = Depends(get_db)) -> PatientHomepageRead:
    user = _get_user(db, user_id)
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")

    public_cases = (
        db.query(MedicalCase)
        .filter(
            MedicalCase.patient_owner_id == user_id,
            MedicalCase.visibility.in_(PUBLIC_CASE_VISIBILITIES),
        )
        .order_by(MedicalCase.updated_at.desc())
        .limit(10)
        .all()
    )
    job_history = (
        db.query(JobPosting)
        .filter(or_(JobPosting.employer_id == user_id, JobPosting.patient_id == user_id))
        .order_by(JobPosting.created_at.desc())
        .limit(20)
        .all()
    )
    review_count, rating_avg = (
        db.query(func.count(Review.id), func.coalesce(func.avg(Review.score), 0))
        .filter(Review.reviewee_id == user_id)
        .one()
    )
    recent_reviews = (
        db.query(Review)
        .filter(Review.reviewee_id == user_id)
        .order_by(Review.created_at.desc())
        .limit(5)
        .all()
    )
    return PatientHomepageRead(
        user_id=user.id,
        display_name=user.display_name,
        real_name=profile.real_name,
        id_verified=profile.id_verified,
        verification_status=profile.verification_status,
        basic_info=profile.basic_info or {},
        rating_avg=float(rating_avg or 0),
        review_count=int(review_count or 0),
        recent_reviews=[_review_read(item) for item in recent_reviews],
        public_cases=[_public_case_read(item) for item in public_cases],
        job_history=[_job_read(item) for item in job_history],
    )


@router.get("/caregivers", response_model=list[CaregiverResumeRead])
async def list_caregiver_resumes(
    city: str | None = None,
    keyword: str | None = None,
    available_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[CaregiverResumeRead]:
    query = db.query(CaregiverProfile).options(selectinload(CaregiverProfile.certifications))
    if available_only:
        query = query.filter(CaregiverProfile.is_available.is_(True))
    if city:
        query = query.filter(CaregiverProfile.service_city == city)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(CaregiverProfile.real_name.like(like), CaregiverProfile.bio.like(like)))

    profiles = query.order_by(CaregiverProfile.rating_avg.desc(), CaregiverProfile.created_at.desc()).limit(50).all()
    return [_caregiver_resume_read(db, profile) for profile in profiles]


@router.get("/caregivers/{user_id}", response_model=CaregiverResumeRead)
async def get_caregiver_resume(user_id: str, db: Session = Depends(get_db)) -> CaregiverResumeRead:
    profile = (
        db.query(CaregiverProfile)
        .options(selectinload(CaregiverProfile.certifications))
        .filter(CaregiverProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caregiver profile not found")
    return _caregiver_resume_read(db, profile)


@router.patch("/caregivers/{user_id}/availability", response_model=CaregiverResumeRead)
async def update_caregiver_availability(
    user_id: str, payload: CaregiverAvailabilityUpdate, db: Session = Depends(get_db)
) -> CaregiverResumeRead:
    profile = (
        db.query(CaregiverProfile)
        .options(selectinload(CaregiverProfile.certifications))
        .filter(CaregiverProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caregiver profile not found")

    profile.is_available = payload.is_available
    db.commit()
    db.refresh(profile)
    return _caregiver_resume_read(db, profile)
