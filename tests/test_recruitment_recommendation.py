from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Base,
    CaregiverProfile,
    RecruitmentInteraction,
    User,
)
from backend.app.recommendation.model import RecruitmentModelStore
from backend.app.recommendation.service import rank_available_caregivers
from backend.app.recommendation.training import train_recruitment_model


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _user(db: Session, phone: str, role: str) -> User:
    user = User(
        phone=phone,
        password_hash="test",
        display_name=phone,
        active_role=role,
    )
    db.add(user)
    db.flush()
    return user


def _caregiver(
    db: Session,
    phone: str,
    city: str,
    bio: str,
    experience: int,
) -> tuple[User, CaregiverProfile]:
    user = _user(db, phone, "caregiver")
    profile = CaregiverProfile(
        user_id=user.id,
        real_name=phone,
        verification_status="approved",
        is_available=True,
        service_city=city,
        bio=bio,
        experience_years=experience,
        rating_avg=4.5,
    )
    db.add(profile)
    db.flush()
    return user, profile


def test_recent_view_moves_similar_candidate_forward() -> None:
    db = _session()
    patient = _user(db, "patient", "patient")
    viewed_user, viewed = _caregiver(
        db,
        "viewed",
        "上海",
        "骨科术后护理和康复训练",
        6,
    )
    _, similar = _caregiver(
        db,
        "similar",
        "上海",
        "擅长骨科术后护理和行动康复",
        5,
    )
    _, different = _caregiver(
        db,
        "different",
        "北京",
        "慢病管理和血压监测",
        1,
    )
    db.add(
        RecruitmentInteraction(
            patient_id=patient.id,
            caregiver_id=viewed_user.id,
            action_type="view",
            action_weight=1,
            context_json={},
        )
    )
    db.commit()

    ranked = rank_available_caregivers(
        db,
        [different, similar, viewed],
        patient_id=patient.id,
    )

    assert ranked.index(similar) < ranked.index(different)
    db.close()


def test_pytorch_training_produces_personalized_scores(tmp_path: Path) -> None:
    db = _session()
    patient_a = _user(db, "patient-a", "patient")
    patient_b = _user(db, "patient-b", "patient")
    caregiver_a, _ = _caregiver(db, "caregiver-a", "上海", "术后护理", 6)
    caregiver_b, _ = _caregiver(db, "caregiver-b", "北京", "慢病护理", 5)
    caregiver_c, _ = _caregiver(db, "caregiver-c", "广州", "康复护理", 4)

    interactions = [
        (patient_a.id, caregiver_a.id, 10.0),
        (patient_a.id, caregiver_b.id, -6.0),
        (patient_b.id, caregiver_b.id, 10.0),
        (patient_b.id, caregiver_a.id, -6.0),
    ]
    for patient_id, caregiver_id, weight in interactions:
        db.add(
            RecruitmentInteraction(
                patient_id=patient_id,
                caregiver_id=caregiver_id,
                action_type="accept" if weight > 0 else "reject",
                action_weight=weight,
                context_json={},
            )
        )
    db.commit()

    artifact_path = tmp_path / "recommendation.pt"
    result = train_recruitment_model(
        db,
        str(artifact_path),
        epochs=100,
        embedding_dim=8,
        seed=7,
    )
    store = RecruitmentModelStore(str(artifact_path))
    scores_a = store.predict(
        patient_a.id,
        [caregiver_a.id, caregiver_b.id, caregiver_c.id],
    )
    scores_b = store.predict(
        patient_b.id,
        [caregiver_a.id, caregiver_b.id, caregiver_c.id],
    )

    assert result["samples"] > 0
    assert scores_a[caregiver_a.id] > scores_a[caregiver_b.id]
    assert scores_b[caregiver_b.id] > scores_b[caregiver_a.id]
    db.close()
