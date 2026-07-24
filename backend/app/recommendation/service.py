from __future__ import annotations

import logging
import math
import random
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import (
    CaregiverProfile,
    JobPosting,
    RecruitmentInteraction,
)
from backend.app.recommendation.model import RecruitmentModelStore

logger = logging.getLogger(__name__)

ACTION_WEIGHTS = {
    "impression": 0.0,
    "filter": 0.5,
    "view": 1.0,
    "chat": 5.0,
    "invite": 7.0,
    "accept": 10.0,
    "reject": -6.0,
}
MEANINGFUL_ACTIONS = {"view", "chat", "invite", "accept", "reject"}

model_store = RecruitmentModelStore(settings.recruitment_model_path)


def record_interaction(
    db: Session,
    *,
    patient_id: str,
    action_type: str,
    caregiver_id: str | None = None,
    job_id: str | None = None,
    context: dict[str, Any] | None = None,
    request_id: str = "",
    model_version: str = "",
) -> None:
    interaction = RecruitmentInteraction(
        patient_id=patient_id,
        caregiver_id=caregiver_id,
        job_id=job_id,
        action_type=action_type,
        action_weight=ACTION_WEIGHTS.get(action_type, 0.0),
        context_json=context or {},
        request_id=request_id,
        model_version=model_version,
    )
    try:
        db.add(interaction)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record recruitment interaction")


def rank_available_caregivers(
    db: Session,
    profiles: list[CaregiverProfile],
    *,
    patient_id: str | None,
    job_id: str | None = None,
    filters: dict[str, Any] | None = None,
) -> list[CaregiverProfile]:
    if not profiles:
        return []
    if not patient_id:
        return sorted(
            profiles,
            key=lambda profile: (profile.rating_avg, profile.experience_years),
            reverse=True,
        )

    request_id = str(uuid4())
    active_filters = {
        key: value
        for key, value in (filters or {}).items()
        if value is not None and value != ""
    }
    if active_filters:
        record_interaction(
            db,
            patient_id=patient_id,
            job_id=job_id,
            action_type="filter",
            context=active_filters,
            request_id=request_id,
        )

    interactions = (
        db.query(RecruitmentInteraction)
        .filter(RecruitmentInteraction.patient_id == patient_id)
        .order_by(RecruitmentInteraction.created_at.desc())
        .limit(1000)
        .all()
    )
    candidate_ids = [profile.user_id for profile in profiles]
    model_scores = model_store.predict(patient_id, candidate_ids)
    behavior_scores = _behavior_affinity(db, profiles, interactions)
    preference_scores = _filter_affinity(profiles, interactions)
    job_scores = _job_affinity(db, profiles, job_id)
    quality_scores = {
        profile.user_id: _quality_score(profile)
        for profile in profiles
    }
    exploration_scores = {
        profile.user_id: random.Random(f"{request_id}:{profile.user_id}").random()
        for profile in profiles
    }

    meaningful = any(item.action_type in MEANINGFUL_ACTIONS for item in interactions)
    has_preference = any(item.action_type == "filter" for item in interactions)
    has_job = bool(job_scores)
    has_model = bool(model_scores)
    final_scores: dict[str, float] = {}

    for profile in profiles:
        caregiver_id = profile.user_id
        if not any((meaningful, has_preference, has_job, has_model)):
            final_scores[caregiver_id] = (
                0.2 * quality_scores[caregiver_id]
                + 0.8 * exploration_scores[caregiver_id]
            )
            continue

        components: list[tuple[float, float]] = [
            (quality_scores[caregiver_id], 0.10),
            (
                exploration_scores[caregiver_id],
                float(settings.recruitment_exploration_rate),
            ),
        ]
        if has_model:
            components.append((model_scores.get(caregiver_id, 0.35), 0.42))
        if meaningful:
            components.append((behavior_scores.get(caregiver_id, 0.0), 0.24))
        if has_preference:
            components.append((preference_scores.get(caregiver_id, 0.0), 0.14))
        if has_job:
            components.append((job_scores.get(caregiver_id, 0.0), 0.10))

        total_weight = sum(weight for _, weight in components)
        final_scores[caregiver_id] = (
            sum(value * weight for value, weight in components) / total_weight
        )

    ranked = sorted(
        profiles,
        key=lambda profile: final_scores[profile.user_id],
        reverse=True,
    )
    _record_impressions(
        db,
        patient_id=patient_id,
        job_id=job_id,
        request_id=request_id,
        model_version=model_store.model_version,
        ranked=ranked,
        scores=final_scores,
        filters=active_filters,
    )
    return ranked


def _behavior_affinity(
    db: Session,
    profiles: list[CaregiverProfile],
    interactions: list[RecruitmentInteraction],
) -> dict[str, float]:
    relevant = [
        item
        for item in interactions
        if item.caregiver_id and item.action_type in MEANINGFUL_ACTIONS
    ]
    if not relevant:
        return {}

    reference_ids = {item.caregiver_id for item in relevant if item.caregiver_id}
    reference_profiles = {
        profile.user_id: profile
        for profile in db.query(CaregiverProfile)
        .filter(CaregiverProfile.user_id.in_(reference_ids))
        .all()
    }
    raw_scores: dict[str, float] = {}
    for profile in profiles:
        score = 0.0
        normalization = 0.0
        for item in relevant:
            reference = reference_profiles.get(item.caregiver_id or "")
            if not reference:
                continue
            weight = float(item.action_weight) * _time_decay(item.created_at)
            score += weight * _profile_similarity(profile, reference)
            normalization += abs(weight)
        raw_scores[profile.user_id] = score / normalization if normalization else 0.0
    return _min_max(raw_scores)


def _filter_affinity(
    profiles: list[CaregiverProfile],
    interactions: list[RecruitmentInteraction],
) -> dict[str, float]:
    filter_events = [item for item in interactions if item.action_type == "filter"]
    if not filter_events:
        return {}

    raw_scores: dict[str, float] = {}
    for profile in profiles:
        score = 0.0
        normalization = 0.0
        for item in filter_events[:100]:
            context = item.context_json or {}
            decay = _time_decay(item.created_at)
            event_score = 0.0
            event_weight = 0.0
            city = str(context.get("city") or "").strip()
            keyword = str(context.get("keyword") or "").strip()
            min_experience = int(context.get("min_experience") or 0)
            if city:
                event_score += 0.45 if profile.service_city == city else 0.0
                event_weight += 0.45
            if keyword:
                text = f"{profile.real_name} {profile.bio}".lower()
                event_score += 0.4 if keyword.lower() in text else 0.0
                event_weight += 0.4
            if min_experience:
                event_score += 0.15 if profile.experience_years >= min_experience else 0.0
                event_weight += 0.15
            if event_weight:
                score += decay * event_score / event_weight
                normalization += decay
        raw_scores[profile.user_id] = score / normalization if normalization else 0.0
    return _min_max(raw_scores)


def _job_affinity(
    db: Session,
    profiles: list[CaregiverProfile],
    job_id: str | None,
) -> dict[str, float]:
    if not job_id:
        return {}
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        return {}

    job_text = " ".join(
        [
            job.title or "",
            job.care_type or "",
            job.care_level or "",
            job.description or "",
            job.special_requirements or "",
        ]
    )
    scores: dict[str, float] = {}
    for profile in profiles:
        city_score = 1.0 if job.city and profile.service_city == job.city else 0.0
        semantic_score = _text_similarity(job_text, profile.bio or "")
        scores[profile.user_id] = 0.45 * city_score + 0.55 * semantic_score
    return _min_max(scores)


def _profile_similarity(
    left: CaregiverProfile,
    right: CaregiverProfile,
) -> float:
    city = 1.0 if left.service_city and left.service_city == right.service_city else 0.0
    experience = max(0.0, 1.0 - abs(left.experience_years - right.experience_years) / 12)
    rating = max(0.0, 1.0 - abs(float(left.rating_avg) - float(right.rating_avg)) / 5)
    bio = _text_similarity(left.bio or "", right.bio or "")
    return 0.35 * city + 0.2 * experience + 0.15 * rating + 0.3 * bio


def _text_similarity(left: str, right: str) -> float:
    left_chars = {character for character in left.lower() if character.isalnum()}
    right_chars = {character for character in right.lower() if character.isalnum()}
    if not left_chars or not right_chars:
        return 0.0
    return len(left_chars & right_chars) / len(left_chars | right_chars)


def _quality_score(profile: CaregiverProfile) -> float:
    rating = min(max(float(profile.rating_avg) / 5, 0.0), 1.0)
    experience = min(max(profile.experience_years / 10, 0.0), 1.0)
    verification = 1.0 if profile.verification_status == "approved" else 0.3
    return 0.55 * rating + 0.3 * experience + 0.15 * verification


def _time_decay(created_at: datetime | None) -> float:
    if not created_at:
        return 1.0
    created = created_at.replace(tzinfo=UTC)
    age_days = max(
        0.0,
        (datetime.now(UTC) - created).total_seconds() / 86400,
    )
    return math.pow(0.95, age_days)


def _min_max(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    minimum = min(values.values())
    maximum = max(values.values())
    if math.isclose(minimum, maximum):
        return {key: 0.5 if maximum else 0.0 for key in values}
    return {
        key: (value - minimum) / (maximum - minimum)
        for key, value in values.items()
    }


def _record_impressions(
    db: Session,
    *,
    patient_id: str,
    job_id: str | None,
    request_id: str,
    model_version: str,
    ranked: list[CaregiverProfile],
    scores: dict[str, float],
    filters: dict[str, Any],
) -> None:
    try:
        db.add_all(
            [
                RecruitmentInteraction(
                    patient_id=patient_id,
                    caregiver_id=profile.user_id,
                    job_id=job_id,
                    action_type="impression",
                    action_weight=0,
                    context_json={
                        "position": position,
                        "score": round(scores[profile.user_id], 6),
                        "filters": filters,
                    },
                    request_id=request_id,
                    model_version=model_version,
                )
                for position, profile in enumerate(ranked[:20], start=1)
            ]
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record recruitment impressions")
