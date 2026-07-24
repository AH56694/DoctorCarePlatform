from __future__ import annotations

import random
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch
from sqlalchemy.orm import Session

from backend.app.db.models import CaregiverProfile, RecruitmentInteraction
from backend.app.recommendation.model import MODEL_FORMAT_VERSION, ImplicitMatrixFactorization


def train_recruitment_model(
    db: Session,
    output_path: str,
    *,
    embedding_dim: int = 32,
    epochs: int = 120,
    learning_rate: float = 0.03,
    negatives_per_positive: int = 3,
    seed: int = 20260723,
) -> dict[str, Any]:
    random.seed(seed)
    torch.manual_seed(seed)

    rows = (
        db.query(RecruitmentInteraction)
        .filter(RecruitmentInteraction.caregiver_id.isnot(None))
        .all()
    )
    candidate_ids = sorted(
        item[0]
        for item in db.query(CaregiverProfile.user_id)
        .filter(CaregiverProfile.is_available.is_(True))
        .all()
    )
    if not candidate_ids:
        raise ValueError("No available caregivers found for recommendation training")

    pair_weights: dict[tuple[str, str], float] = defaultdict(float)
    for row in rows:
        if row.caregiver_id:
            pair_weights[(row.patient_id, row.caregiver_id)] += float(row.action_weight)

    positive_pairs = [pair for pair, weight in pair_weights.items() if weight > 0]
    if not positive_pairs:
        raise ValueError("No positive recruitment interactions found for training")

    patient_ids = sorted({patient_id for patient_id, _ in pair_weights})
    user_to_index = {user_id: index for index, user_id in enumerate(patient_ids)}
    caregiver_to_index = {
        caregiver_id: index for index, caregiver_id in enumerate(candidate_ids)
    }

    samples: list[tuple[int, int, float, float]] = []
    positive_by_user: dict[str, set[str]] = defaultdict(set)
    for (patient_id, caregiver_id), weight in pair_weights.items():
        if caregiver_id not in caregiver_to_index:
            continue
        target = 1.0 if weight > 0 else 0.0
        sample_weight = min(4.0, 1.0 + abs(weight) / 4.0)
        samples.append(
            (
                user_to_index[patient_id],
                caregiver_to_index[caregiver_id],
                target,
                sample_weight,
            )
        )
        if weight > 0:
            positive_by_user[patient_id].add(caregiver_id)

    for patient_id, caregiver_id in positive_pairs:
        if patient_id not in user_to_index or caregiver_id not in caregiver_to_index:
            continue
        negative_pool = [
            item
            for item in candidate_ids
            if item not in positive_by_user[patient_id]
        ]
        if not negative_pool:
            continue
        for negative_id in random.sample(
            negative_pool,
            min(negatives_per_positive, len(negative_pool)),
        ):
            samples.append(
                (
                    user_to_index[patient_id],
                    caregiver_to_index[negative_id],
                    0.0,
                    0.75,
                )
            )

    random.shuffle(samples)
    user_indices = torch.tensor([item[0] for item in samples], dtype=torch.long)
    candidate_indices = torch.tensor([item[1] for item in samples], dtype=torch.long)
    targets = torch.tensor([item[2] for item in samples], dtype=torch.float32)
    weights = torch.tensor([item[3] for item in samples], dtype=torch.float32)

    model = ImplicitMatrixFactorization(
        num_users=len(user_to_index),
        num_candidates=len(caregiver_to_index),
        embedding_dim=embedding_dim,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)
    loss_function = torch.nn.BCEWithLogitsLoss(reduction="none")

    model.train()
    final_loss = 0.0
    for _ in range(epochs):
        optimizer.zero_grad()
        logits = model(user_indices, candidate_indices)
        loss = (loss_function(logits, targets) * weights).mean()
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach())

    model.eval()
    with torch.inference_mode():
        probabilities = torch.sigmoid(model(user_indices, candidate_indices))
        accuracy = float(((probabilities >= 0.5) == (targets >= 0.5)).float().mean())

    model_version = datetime.now(UTC).strftime("pytorch-implicit-mf-%Y%m%d%H%M%S")
    artifact = {
        "format_version": MODEL_FORMAT_VERSION,
        "model_version": model_version,
        "embedding_dim": embedding_dim,
        "user_to_index": user_to_index,
        "caregiver_to_index": caregiver_to_index,
        "state_dict": model.state_dict(),
        "trained_at": datetime.now(UTC).isoformat(),
        "metrics": {
            "loss": final_loss,
            "accuracy": accuracy,
            "samples": len(samples),
            "positive_pairs": len(positive_pairs),
        },
    }

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(destination)
    return {
        "model_version": model_version,
        "path": str(destination.resolve()),
        **artifact["metrics"],
        "users": len(user_to_index),
        "caregivers": len(caregiver_to_index),
    }
