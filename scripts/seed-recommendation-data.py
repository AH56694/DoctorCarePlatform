from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic local recruitment recommendation data."
    )
    parser.add_argument("--database-url", default="")
    parser.add_argument("--patients", type=int, default=12)
    parser.add_argument("--caregivers", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260723)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    from backend.app.db.models import (
        Application,
        Base,
        CaregiverProfile,
        Certification,
        JobPosting,
        PatientProfile,
        RecruitmentInteraction,
        User,
        UserRole,
    )
    from backend.app.db.session import SessionLocal, engine
    from backend.app.services.auth import hash_password

    random.seed(args.seed)
    Base.metadata.create_all(bind=engine)

    cities = ["上海", "北京", "广州", "深圳", "杭州", "南京"]
    specialties = [
        ("术后护理", ["骨科术后", "伤口护理", "康复训练", "协助行动"]),
        ("老年陪护", ["失能照护", "认知症照护", "生活协助", "营养管理"]),
        ("慢病护理", ["糖尿病护理", "血压监测", "用药提醒", "健康记录"]),
        ("康复护理", ["肢体康复", "行动训练", "康复评估", "生活能力训练"]),
        ("夜间陪护", ["夜间观察", "翻身辅助", "安全巡视", "睡眠照护"]),
    ]
    certificates = ["护士执业证", "养老护理员证", "康复护理证", "急救培训证"]
    family_names = ["王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
    given_names = ["芳", "敏", "娜", "静", "强", "磊", "杰", "丽", "霞", "伟"]
    preference_archetypes = [
        {"city": "上海", "specialty": "术后护理", "min_experience": 5},
        {"city": "北京", "specialty": "老年陪护", "min_experience": 4},
        {"city": "广州", "specialty": "慢病护理", "min_experience": 3},
        {"city": "深圳", "specialty": "康复护理", "min_experience": 5},
        {"city": "杭州", "specialty": "夜间陪护", "min_experience": 3},
        {"city": "南京", "specialty": "老年陪护", "min_experience": 6},
    ]

    db = SessionLocal()
    try:
        caregivers: list[tuple[User, CaregiverProfile, str]] = []
        for index in range(args.caregivers):
            phone = f"1388{index:07d}"
            user = db.query(User).filter(User.phone == phone).first()
            specialty, skills = specialties[index % len(specialties)]
            city = cities[(index * 5 + index // len(cities)) % len(cities)]
            experience = 1 + (index * 3) % 15
            rating = round(3.4 + ((index * 17) % 16) / 10, 1)
            real_name = (
                family_names[index % len(family_names)]
                + given_names[(index * 3) % len(given_names)]
            )
            bio = (
                f"主要提供{specialty}，擅长{'、'.join(skills)}。"
                f"有{experience}年一线护理经验，可在{city}接单。"
            )

            if not user:
                user = User(
                    phone=phone,
                    password_hash=hash_password("demo123456"),
                    display_name=f"演示护理{index + 1:02d}",
                    status="active",
                    active_role="caregiver",
                )
                db.add(user)
                db.flush()
            role = (
                db.query(UserRole)
                .filter(UserRole.user_id == user.id, UserRole.role == "caregiver")
                .first()
            )
            if not role:
                db.add(
                    UserRole(
                        user_id=user.id,
                        role="caregiver",
                        is_active=True,
                        verification_status="approved",
                    )
                )
            profile = (
                db.query(CaregiverProfile)
                .filter(CaregiverProfile.user_id == user.id)
                .first()
            )
            if not profile:
                profile = CaregiverProfile(user_id=user.id)
                db.add(profile)
            profile.real_name = real_name
            profile.id_number = f"DEMO-C-{index + 1:04d}"
            profile.id_verified = True
            profile.verification_status = "approved"
            profile.bio = bio
            profile.is_available = True
            profile.experience_years = experience
            profile.service_city = city
            profile.rating_avg = rating
            db.flush()

            existing_certificates = {
                item.certificate_type
                for item in db.query(Certification)
                .filter(Certification.caregiver_profile_id == profile.id)
                .all()
            }
            certificate_type = certificates[index % len(certificates)]
            if certificate_type not in existing_certificates:
                db.add(
                    Certification(
                        caregiver_profile_id=profile.id,
                        certificate_type=certificate_type,
                        file_url=f"/demo/certificates/{profile.id}.jpg",
                        description=f"{specialty}演示认证资料",
                        review_status="approved",
                        review_note="本地随机数据",
                    )
                )
            caregivers.append((user, profile, specialty))

        patients: list[tuple[User, JobPosting, dict[str, object]]] = []
        for index in range(args.patients):
            phone = f"1399{index:07d}"
            user = db.query(User).filter(User.phone == phone).first()
            preference = preference_archetypes[index % len(preference_archetypes)]
            if not user:
                user = User(
                    phone=phone,
                    password_hash=hash_password("demo123456"),
                    display_name=f"演示患者{index + 1:02d}",
                    status="active",
                    active_role="patient",
                )
                db.add(user)
                db.flush()
            role = (
                db.query(UserRole)
                .filter(UserRole.user_id == user.id, UserRole.role == "patient")
                .first()
            )
            if not role:
                db.add(
                    UserRole(
                        user_id=user.id,
                        role="patient",
                        is_active=True,
                        verification_status="approved",
                    )
                )
            profile = (
                db.query(PatientProfile)
                .filter(PatientProfile.user_id == user.id)
                .first()
            )
            if not profile:
                profile = PatientProfile(user_id=user.id)
                db.add(profile)
            profile.real_name = f"患者{index + 1:02d}"
            profile.id_number = f"DEMO-P-{index + 1:04d}"
            profile.id_verified = True
            profile.verification_status = "approved"
            profile.basic_info = {
                "推荐偏好城市": preference["city"],
                "推荐偏好类型": preference["specialty"],
                "最低经验": preference["min_experience"],
            }

            title = f"PyTorch推荐演示-{preference['specialty']}-{index + 1:02d}"
            job = (
                db.query(JobPosting)
                .filter(JobPosting.employer_id == user.id, JobPosting.title == title)
                .first()
            )
            if not job:
                job = JobPosting(
                    employer_id=user.id,
                    patient_id=user.id,
                    title=title,
                    city=str(preference["city"]),
                    care_type=str(preference["specialty"]),
                    care_level="日间陪护",
                    location=f"{preference['city']}市区",
                    schedule={
                        "start_time": "08:00",
                        "end_time": "18:00",
                    },
                    salary={"unit": "天", "amount_yuan": 500},
                    budget_cents=50000,
                    status="published",
                    special_requirements=f"经验不少于{preference['min_experience']}年",
                    description=f"需要{preference['specialty']}相关护理支持",
                )
                db.add(job)
                db.flush()
            patients.append((user, job, preference))

        db.commit()

        demo_patient_ids = [item[0].id for item in patients]
        (
            db.query(RecruitmentInteraction)
            .filter(RecruitmentInteraction.patient_id.in_(demo_patient_ids))
            .delete(synchronize_session=False)
        )
        db.commit()

        now = datetime.now(UTC).replace(tzinfo=None)
        interaction_count = 0
        for patient_index, (patient, job, preference) in enumerate(patients):
            ranked_candidates: list[tuple[float, User, CaregiverProfile, str]] = []
            for caregiver, profile, specialty in caregivers:
                affinity = 0.0
                if profile.service_city == preference["city"]:
                    affinity += 0.4
                if specialty == preference["specialty"]:
                    affinity += 0.35
                if profile.experience_years >= int(preference["min_experience"]):
                    affinity += 0.15
                affinity += float(profile.rating_avg) / 50
                affinity += random.uniform(-0.08, 0.08)
                ranked_candidates.append((affinity, caregiver, profile, specialty))
            ranked_candidates.sort(key=lambda item: item[0], reverse=True)

            db.add(
                RecruitmentInteraction(
                    patient_id=patient.id,
                    job_id=job.id,
                    action_type="filter",
                    action_weight=0.5,
                    context_json={
                        "city": preference["city"],
                        "keyword": preference["specialty"],
                        "min_experience": preference["min_experience"],
                        "dataset": "synthetic_v1",
                    },
                    request_id=f"seed-filter-{patient_index}",
                    model_version="synthetic_v1",
                    created_at=now - timedelta(days=20),
                )
            )
            interaction_count += 1

            for position, (_, caregiver, _, _) in enumerate(
                ranked_candidates,
                start=1,
            ):
                created_at = now - timedelta(
                    days=random.randint(1, 18),
                    minutes=position,
                )
                db.add(
                    RecruitmentInteraction(
                        patient_id=patient.id,
                        caregiver_id=caregiver.id,
                        job_id=job.id,
                        action_type="impression",
                        action_weight=0,
                        context_json={
                            "position": position,
                            "dataset": "synthetic_v1",
                        },
                        request_id=f"seed-{patient_index}",
                        model_version="synthetic_v1",
                        created_at=created_at,
                    )
                )
                interaction_count += 1

            for _, caregiver, _, _ in ranked_candidates[:12]:
                actions = ["view"]
                rank = next(
                    index
                    for index, item in enumerate(ranked_candidates)
                    if item[1].id == caregiver.id
                )
                if rank < 6:
                    actions.append("chat")
                if rank < 4:
                    actions.append("invite")
                if rank < 2:
                    actions.append("accept")
                for action in actions:
                    weight = {
                        "view": 1.0,
                        "chat": 5.0,
                        "invite": 7.0,
                        "accept": 10.0,
                    }[action]
                    db.add(
                        RecruitmentInteraction(
                            patient_id=patient.id,
                            caregiver_id=caregiver.id,
                            job_id=job.id,
                            action_type=action,
                            action_weight=weight,
                            context_json={"dataset": "synthetic_v1"},
                            request_id=f"seed-{patient_index}",
                            model_version="synthetic_v1",
                            created_at=now - timedelta(days=random.randint(0, 14)),
                        )
                    )
                    interaction_count += 1

                application = (
                    db.query(Application)
                    .filter(
                        Application.job_id == job.id,
                        Application.caregiver_id == caregiver.id,
                    )
                    .first()
                )
                if not application:
                    db.add(
                        Application(
                            job_id=job.id,
                            caregiver_id=caregiver.id,
                            status="pending",
                            cover_letter="本地PyTorch推荐演示应聘数据",
                        )
                    )

            for _, caregiver, _, _ in ranked_candidates[-4:]:
                db.add(
                    RecruitmentInteraction(
                        patient_id=patient.id,
                        caregiver_id=caregiver.id,
                        job_id=job.id,
                        action_type="reject",
                        action_weight=-6.0,
                        context_json={"dataset": "synthetic_v1"},
                        request_id=f"seed-{patient_index}",
                        model_version="synthetic_v1",
                        created_at=now - timedelta(days=random.randint(0, 10)),
                    )
                )
                interaction_count += 1

        db.commit()
        print(
            {
                "patients": len(patients),
                "caregivers": len(caregivers),
                "interactions": interaction_count,
                "password": "demo123456",
                "patient_phone_range": (
                    "13990000000",
                    f"1399{args.patients - 1:07d}",
                ),
                "caregiver_phone_range": (
                    "13880000000",
                    f"1388{args.caregivers - 1:07d}",
                ),
            }
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
