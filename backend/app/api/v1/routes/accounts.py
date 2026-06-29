from base64 import urlsafe_b64encode
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import CaregiverProfile, Certification, PatientProfile, User, UserRole
from backend.app.db.session import get_db
from backend.app.schemas.accounts import (
    AccountRead,
    AuthResponse,
    CaregiverProfileRead,
    CaregiverProfileUpdate,
    CertificationCreate,
    CertificationRead,
    CertificationReview,
    PatientProfileRead,
    PatientProfileUpdate,
    RoleCreateRequest,
    RoleSwitchRequest,
    UserLogin,
    UserRegister,
    UserRoleRead,
)
from backend.app.services.auth import hash_password, verify_password
from backend.app.services.sms import SmsNotificationService

router = APIRouter()

VALID_ROLES = {"patient", "caregiver"}
VALID_REVIEW_STATUSES = {"pending", "approved", "rejected"}


def _load_user(db: Session, user_id: str) -> User:
    user = (
        db.query(User)
        .options(
            selectinload(User.roles),
            selectinload(User.patient_profile),
            selectinload(User.caregiver_profile).selectinload(CaregiverProfile.certifications),
        )
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _role_or_400(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be patient or caregiver")
    return normalized


def _review_status_or_400(review_status: str) -> str:
    normalized = review_status.strip().lower()
    if normalized not in VALID_REVIEW_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid review status")
    return normalized


def _issue_demo_token(user_id: str) -> str:
    raw = f"{user_id}:{uuid4()}".encode("utf-8")
    return urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _ensure_role(db: Session, user: User, role: str, *, active: bool = False) -> UserRole:
    role = _role_or_400(role)
    existing = next((item for item in user.roles if item.role == role), None)
    if existing:
        if active:
            _activate_role(user, role)
        return existing

    new_role = UserRole(
        user_id=user.id,
        role=role,
        is_active=active,
        verification_status="approved" if role == "patient" else "pending",
    )
    db.add(new_role)
    user.roles.append(new_role)
    if active:
        _activate_role(user, role)
    return new_role


def _activate_role(user: User, role: str) -> None:
    role = _role_or_400(role)
    if role not in {item.role for item in user.roles}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target role does not exist")
    user.active_role = role
    for item in user.roles:
        item.is_active = item.role == role


def _account_read(user: User) -> AccountRead:
    caregiver = user.caregiver_profile
    certifications = caregiver.certifications if caregiver else []
    return AccountRead(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
        status=user.status,
        active_role=user.active_role,
        roles=[
            UserRoleRead(
                id=item.id,
                role=item.role,
                is_active=item.is_active,
                verification_status=item.verification_status,
            )
            for item in sorted(user.roles, key=lambda role: role.role)
        ],
        patient_profile=(
            PatientProfileRead(
                real_name=user.patient_profile.real_name,
                id_verified=user.patient_profile.id_verified,
                verification_status=user.patient_profile.verification_status,
                basic_info=user.patient_profile.basic_info,
            )
            if user.patient_profile
            else None
        ),
        caregiver_profile=(
            CaregiverProfileRead(
                real_name=caregiver.real_name,
                id_verified=caregiver.id_verified,
                verification_status=caregiver.verification_status,
                bio=caregiver.bio,
                is_available=caregiver.is_available,
                experience_years=caregiver.experience_years,
                service_city=caregiver.service_city,
                rating_avg=caregiver.rating_avg,
            )
            if caregiver
            else None
        ),
        certifications=[
            CertificationRead(
                id=item.id,
                caregiver_profile_id=item.caregiver_profile_id,
                certificate_type=item.certificate_type,
                file_url=item.file_url,
                description=item.description,
                review_status=item.review_status,
                review_note=item.review_note,
            )
            for item in certifications
        ],
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: Session = Depends(get_db)) -> AuthResponse:
    initial_role = _role_or_400(payload.initial_role)
    if db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")

    user = User(
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        active_role=initial_role,
    )
    db.add(user)
    db.flush()
    _ensure_role(db, user, initial_role, active=True)
    if initial_role == "patient":
        db.add(PatientProfile(user_id=user.id, verification_status="pending"))
    else:
        db.add(CaregiverProfile(user_id=user.id, verification_status="pending"))
    db.commit()
    user = _load_user(db, user.id)
    return AuthResponse(access_token=_issue_demo_token(user.id), account=_account_read(user))


@router.post("/login", response_model=AuthResponse)
async def login(payload: UserLogin, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.phone == payload.phone).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid phone or password")
    user = _load_user(db, user.id)
    return AuthResponse(access_token=_issue_demo_token(user.id), account=_account_read(user))


@router.get("/{user_id}/identity", response_model=AccountRead)
async def get_identity(user_id: str, db: Session = Depends(get_db)) -> AccountRead:
    return _account_read(_load_user(db, user_id))


@router.post("/{user_id}/roles", response_model=AccountRead)
async def create_role(user_id: str, payload: RoleCreateRequest, db: Session = Depends(get_db)) -> AccountRead:
    user = _load_user(db, user_id)
    role = _role_or_400(payload.role)
    _ensure_role(db, user, role)
    if role == "patient" and not user.patient_profile:
        db.add(PatientProfile(user_id=user.id, verification_status="pending"))
    if role == "caregiver" and not user.caregiver_profile:
        db.add(CaregiverProfile(user_id=user.id, verification_status="pending"))
    db.commit()
    return _account_read(_load_user(db, user.id))


@router.post("/{user_id}/roles/switch", response_model=AccountRead)
async def switch_role(user_id: str, payload: RoleSwitchRequest, db: Session = Depends(get_db)) -> AccountRead:
    user = _load_user(db, user_id)
    _activate_role(user, payload.role)
    db.commit()
    return _account_read(_load_user(db, user.id))


@router.put("/{user_id}/profiles/patient", response_model=AccountRead)
async def upsert_patient_profile(
    user_id: str, payload: PatientProfileUpdate, db: Session = Depends(get_db)
) -> AccountRead:
    user = _load_user(db, user_id)
    _ensure_role(db, user, "patient")
    profile = user.patient_profile or PatientProfile(user_id=user.id)
    profile.real_name = payload.real_name
    profile.id_number = payload.id_number
    profile.basic_info = payload.basic_info
    profile.id_verified = bool(payload.real_name and payload.id_number)
    profile.verification_status = "approved" if profile.id_verified else "pending"
    db.add(profile)
    db.commit()
    return _account_read(_load_user(db, user.id))


@router.put("/{user_id}/profiles/caregiver", response_model=AccountRead)
async def upsert_caregiver_profile(
    user_id: str, payload: CaregiverProfileUpdate, db: Session = Depends(get_db)
) -> AccountRead:
    user = _load_user(db, user_id)
    _ensure_role(db, user, "caregiver")
    profile = user.caregiver_profile or CaregiverProfile(user_id=user.id)
    profile.real_name = payload.real_name
    profile.id_number = payload.id_number
    profile.bio = payload.bio
    profile.is_available = payload.is_available
    profile.experience_years = payload.experience_years
    profile.service_city = payload.service_city
    profile.id_verified = bool(payload.real_name and payload.id_number)
    profile.verification_status = "pending"
    db.add(profile)
    db.commit()
    return _account_read(_load_user(db, user.id))


@router.post("/{user_id}/certifications", response_model=CertificationRead, status_code=status.HTTP_201_CREATED)
async def submit_certification(
    user_id: str, payload: CertificationCreate, db: Session = Depends(get_db)
) -> CertificationRead:
    user = _load_user(db, user_id)
    _ensure_role(db, user, "caregiver")
    caregiver = user.caregiver_profile or CaregiverProfile(user_id=user.id, verification_status="pending")
    db.add(caregiver)
    db.flush()
    certification = Certification(
        caregiver_profile_id=caregiver.id,
        certificate_type=payload.certificate_type,
        file_url=payload.file_url,
        description=payload.description,
        review_status="pending",
    )
    db.add(certification)
    db.commit()
    return CertificationRead(
        id=certification.id,
        caregiver_profile_id=certification.caregiver_profile_id,
        certificate_type=certification.certificate_type,
        file_url=certification.file_url,
        description=certification.description,
        review_status=certification.review_status,
        review_note=certification.review_note,
    )


@router.post("/certifications/{certification_id}/review", response_model=CertificationRead)
async def review_certification(
    certification_id: str, payload: CertificationReview, db: Session = Depends(get_db)
) -> CertificationRead:
    certification = db.query(Certification).filter(Certification.id == certification_id).first()
    if not certification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found")
    certification.review_status = _review_status_or_400(payload.review_status)
    certification.review_note = payload.review_note
    caregiver = certification.caregiver_profile
    if caregiver:
        caregiver.verification_status = certification.review_status
        caregiver.id_verified = certification.review_status == "approved"
        role = next((item for item in caregiver.user.roles if item.role == "caregiver"), None)
        if role:
            role.verification_status = certification.review_status
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
    return CertificationRead(
        id=certification.id,
        caregiver_profile_id=certification.caregiver_profile_id,
        certificate_type=certification.certificate_type,
        file_url=certification.file_url,
        description=certification.description,
        review_status=certification.review_status,
        review_note=certification.review_note,
    )
