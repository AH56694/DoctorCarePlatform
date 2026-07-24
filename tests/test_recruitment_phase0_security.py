from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.db.models import (
    AdminLog,
    Base,
    CaregiverProfile,
    JobPosting,
    PatientProfile,
    User,
    UserRole,
)
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.auth import issue_access_token


@pytest.fixture
def api() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, testing_session
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _create_user(
    db: Session,
    *,
    phone: str,
    role: str,
    role_status: str = "approved",
    account_status: str = "active",
) -> User:
    user = User(
        phone=phone,
        password_hash="test",
        display_name=phone,
        status=account_status,
        active_role=role,
    )
    db.add(user)
    db.flush()
    db.add(
        UserRole(
            user_id=user.id,
            role=role,
            is_active=True,
            verification_status=role_status,
        )
    )
    if role == "patient":
        db.add(
            PatientProfile(
                user_id=user.id,
                real_name=phone,
                id_verified=True,
                verification_status="approved",
            )
        )
    db.flush()
    return user


def _create_caregiver(
    db: Session,
    *,
    phone: str,
    profile_status: str = "approved",
    role_status: str = "approved",
    account_status: str = "active",
    verified: bool = True,
    available: bool = True,
) -> User:
    user = _create_user(
        db,
        phone=phone,
        role="caregiver",
        role_status=role_status,
        account_status=account_status,
    )
    db.add(
        CaregiverProfile(
            user_id=user.id,
            real_name=phone,
            id_verified=verified,
            verification_status=profile_status,
            is_available=available,
            service_city="上海",
            bio="术后护理",
            experience_years=5,
            rating_avg=4.8,
        )
    )
    db.flush()
    return user


def _create_job(db: Session, owner: User, *, status: str = "published") -> JobPosting:
    job = JobPosting(
        employer_id=owner.id,
        patient_id=owner.id,
        title="术后陪护",
        city="上海",
        care_type="术后护理",
        care_level="日间陪护",
        location="浦东新区 医院住院部 8 楼",
        budget_cents=48000,
        status=status,
        description=(
            "病人性别：女\n"
            "年龄：68 岁\n"
            "病症/护理类型：骨科术后 / 术后护理\n"
            "地点：浦东新区 医院住院部 8 楼\n"
            "护理时间：08:00 - 18:00"
        ),
        special_requirements="病人资料：女，68 岁\n护理要求：协助行动",
    )
    db.add(job)
    db.flush()
    return job


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_access_token(user.id)}"}


def test_production_rejects_development_auth_secret() -> None:
    original_env = settings.app_env
    original_secret = settings.auth_secret_key
    try:
        settings.app_env = "production"
        settings.auth_secret_key = "development-only-change-me"
        with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
            create_app()
    finally:
        settings.app_env = original_env
        settings.auth_secret_key = original_secret


def test_authentication_ownership_and_public_job_redaction(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api
    with session_factory() as db:
        owner = _create_user(db, phone="owner-10001", role="patient")
        stranger = _create_user(db, phone="stranger-10002", role="patient")
        caregiver = _create_caregiver(db, phone="caregiver-10003")
        published = _create_job(db, owner)
        private_job = _create_job(db, owner, status="matched")
        db.commit()

        assert client.get("/api/v1/jobs").status_code == 401
        assert (
            client.get(
                f"/api/v1/accounts/{owner.id}/identity",
                headers=_headers(stranger),
            ).status_code
            == 403
        )

        public_response = client.get(
            "/api/v1/jobs?status=published",
            headers=_headers(caregiver),
        )
        assert public_response.status_code == 200
        public_job = public_response.json()[0]
        assert public_job["patient_id"] is None
        assert public_job["location"] == "上海"
        assert "68" not in public_job["description"]
        assert "骨科术后" not in public_job["description"]
        assert "医院住院部" not in public_job["description"]
        assert "68" not in public_job["special_requirements"]

        owner_response = client.get(
            f"/api/v1/jobs/{published.id}",
            headers=_headers(owner),
        )
        assert owner_response.status_code == 200
        assert owner_response.json()["location"] == "浦东新区 医院住院部 8 楼"
        assert owner_response.json()["patient_id"] == owner.id

        hidden_response = client.get(
            f"/api/v1/jobs/{private_job.id}",
            headers=_headers(caregiver),
        )
        assert hidden_response.status_code == 404

        forged_job_chat = client.post(
            "/api/v1/conversations",
            headers=_headers(stranger),
            json={
                "participant_a": stranger.id,
                "participant_b": owner.id,
                "source_type": "job",
                "source_id": published.id,
                "title": "伪造候选人沟通",
            },
        )
        assert forged_job_chat.status_code == 400

        valid_job_chat = client.post(
            "/api/v1/conversations",
            headers=_headers(caregiver),
            json={
                "participant_a": caregiver.id,
                "participant_b": owner.id,
                "source_type": "job",
                "source_id": published.id,
                "title": "岗位沟通",
            },
        )
        assert valid_job_chat.status_code == 201


def test_candidate_pool_enforces_all_eligibility_rules(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api
    with session_factory() as db:
        owner = _create_user(db, phone="owner-20001", role="patient")
        other_owner = _create_user(db, phone="owner-20002", role="patient")
        eligible = _create_caregiver(db, phone="eligible-20003")
        _create_caregiver(
            db,
            phone="unverified-20004",
            profile_status="pending",
            verified=False,
        )
        _create_caregiver(
            db,
            phone="role-pending-20005",
            role_status="pending",
        )
        _create_caregiver(
            db,
            phone="suspended-20006",
            account_status="suspended",
        )
        _create_caregiver(
            db,
            phone="unavailable-20007",
            available=False,
        )
        job = _create_job(db, owner)
        db.commit()

        response = client.get(
            f"/api/v1/jobs/caregivers/available?job_id={job.id}",
            headers=_headers(owner),
        )
        assert response.status_code == 200
        assert [item["user_id"] for item in response.json()] == [eligible.id]

        forbidden = client.get(
            f"/api/v1/jobs/caregivers/available?job_id={job.id}",
            headers=_headers(other_owner),
        )
        assert forbidden.status_code == 403


def test_application_identity_idempotency_and_owner_review(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api
    with session_factory() as db:
        owner = _create_user(db, phone="owner-30001", role="patient")
        other_owner = _create_user(db, phone="owner-30002", role="patient")
        caregiver = _create_caregiver(db, phone="caregiver-30003")
        other_caregiver = _create_caregiver(db, phone="caregiver-30004")
        job = _create_job(db, owner)
        db.commit()

        spoofed = client.post(
            f"/api/v1/jobs/{job.id}/applications",
            headers=_headers(caregiver),
            json={"caregiver_id": other_caregiver.id, "cover_letter": "伪造身份"},
        )
        assert spoofed.status_code == 403

        headers = {
            **_headers(caregiver),
            "Idempotency-Key": "application-retry-30003",
        }
        first = client.post(
            f"/api/v1/jobs/{job.id}/applications",
            headers=headers,
            json={"caregiver_id": caregiver.id, "cover_letter": "五年经验"},
        )
        retry = client.post(
            f"/api/v1/jobs/{job.id}/applications",
            headers=headers,
            json={"caregiver_id": caregiver.id, "cover_letter": "五年经验"},
        )
        assert first.status_code == 201
        assert retry.status_code == 201
        assert retry.json()["id"] == first.json()["id"]
        changed_request = client.post(
            f"/api/v1/jobs/{job.id}/applications",
            headers=headers,
            json={"caregiver_id": caregiver.id, "cover_letter": "不同的请求内容"},
        )
        assert changed_request.status_code == 409

        assert (
            client.get(
                f"/api/v1/jobs/{job.id}/applications",
                headers=_headers(other_owner),
            ).status_code
            == 403
        )
        review = client.post(
            f"/api/v1/jobs/applications/{first.json()['id']}/review",
            headers=_headers(owner),
            json={"status": "rejected"},
        )
        assert review.status_code == 200
        same_review = client.post(
            f"/api/v1/jobs/applications/{first.json()['id']}/review",
            headers=_headers(owner),
            json={"status": "rejected"},
        )
        assert same_review.status_code == 200
        conflicting_review = client.post(
            f"/api/v1/jobs/applications/{first.json()['id']}/review",
            headers=_headers(owner),
            json={"status": "accepted"},
        )
        assert conflicting_review.status_code == 409


def test_invitation_is_scoped_and_idempotent(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api
    with session_factory() as db:
        owner = _create_user(db, phone="owner-40001", role="patient")
        other_owner = _create_user(db, phone="owner-40002", role="patient")
        caregiver = _create_caregiver(db, phone="caregiver-40003")
        job = _create_job(db, owner)
        db.commit()

        payload = {
            "patient_id": owner.id,
            "caregiver_id": caregiver.id,
            "job_id": job.id,
            "message": "邀请沟通",
        }
        headers = {
            **_headers(owner),
            "Idempotency-Key": "invitation-retry-40001",
        }
        first = client.post(
            "/api/v1/jobs/invitations",
            headers=headers,
            json=payload,
        )
        retry = client.post(
            "/api/v1/jobs/invitations",
            headers=headers,
            json=payload,
        )
        assert first.status_code == 201
        assert retry.status_code == 201
        assert retry.json()["id"] == first.json()["id"]
        changed_request = client.post(
            "/api/v1/jobs/invitations",
            headers=headers,
            json={**payload, "message": "使用相同键修改内容"},
        )
        assert changed_request.status_code == 409

        forged = client.post(
            "/api/v1/jobs/invitations",
            headers=_headers(other_owner),
            json=payload,
        )
        assert forged.status_code == 403

        caregiver_inbox = client.get(
            "/api/v1/jobs/invitations",
            headers=_headers(caregiver),
        )
        assert caregiver_inbox.status_code == 200
        assert [item["id"] for item in caregiver_inbox.json()] == [first.json()["id"]]

        accepted = client.post(
            f"/api/v1/jobs/invitations/{first.json()['id']}/respond",
            headers=_headers(caregiver),
            json={"status": "accepted"},
        )
        accepted_retry = client.post(
            f"/api/v1/jobs/invitations/{first.json()['id']}/respond",
            headers=_headers(caregiver),
            json={"status": "accepted"},
        )
        assert accepted.status_code == 200
        assert accepted_retry.status_code == 200
        assert accepted_retry.json()["conversation"]["id"] == accepted.json()["conversation"]["id"]


def test_admin_routes_require_active_admin_and_bind_audit_actor(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api
    with session_factory() as db:
        admin = _create_user(db, phone="admin-50001", role="admin")
        patient = _create_user(db, phone="patient-50002", role="patient")
        db.commit()

        denied = client.get(
            "/api/v1/admin/summary",
            headers=_headers(patient),
        )
        assert denied.status_code == 403

        updated = client.patch(
            f"/api/v1/admin/users/{patient.id}/status",
            headers=_headers(admin),
            json={
                "status": "suspended",
                "admin_id": patient.id,
                "reason": "安全回归测试",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "suspended"

        log = (
            db.query(AdminLog)
            .filter(
                AdminLog.action == "user.status_update",
                AdminLog.target_id == patient.id,
            )
            .one()
        )
        assert log.admin_id == admin.id
