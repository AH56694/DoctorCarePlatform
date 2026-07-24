from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import torch
from torch import nn

logger = logging.getLogger(__name__)

MODEL_FORMAT_VERSION = 1


class ImplicitMatrixFactorization(nn.Module):
    """Learn patient and caregiver embeddings from implicit recruitment feedback."""

    def __init__(self, num_users: int, num_candidates: int, embedding_dim: int = 32) -> None:
        super().__init__()
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.candidate_embedding = nn.Embedding(num_candidates, embedding_dim)
        self.user_bias = nn.Embedding(num_users, 1)
        self.candidate_bias = nn.Embedding(num_candidates, 1)
        nn.init.normal_(self.user_embedding.weight, std=0.05)
        nn.init.normal_(self.candidate_embedding.weight, std=0.05)
        nn.init.zeros_(self.user_bias.weight)
        nn.init.zeros_(self.candidate_bias.weight)

    def forward(
        self,
        user_indices: torch.Tensor,
        candidate_indices: torch.Tensor,
    ) -> torch.Tensor:
        user_vectors = self.user_embedding(user_indices)
        candidate_vectors = self.candidate_embedding(candidate_indices)
        affinity = (user_vectors * candidate_vectors).sum(dim=-1)
        return (
            affinity
            + self.user_bias(user_indices).squeeze(-1)
            + self.candidate_bias(candidate_indices).squeeze(-1)
        )


class RecruitmentModelStore:
    """Load a trusted local model artifact and refresh it when the file changes."""

    def __init__(self, artifact_path: str) -> None:
        self.artifact_path = Path(artifact_path)
        self._mtime_ns: int | None = None
        self._artifact: dict[str, Any] | None = None
        self._model: ImplicitMatrixFactorization | None = None

    @property
    def model_version(self) -> str:
        self._load_if_needed()
        if not self._artifact:
            return "behavior-rule-fallback"
        return str(self._artifact.get("model_version") or "pytorch-implicit-mf")

    def predict(self, patient_id: str, caregiver_ids: list[str]) -> dict[str, float]:
        self._load_if_needed()
        if not self._artifact or not self._model:
            return {}

        user_to_index = self._artifact["user_to_index"]
        caregiver_to_index = self._artifact["caregiver_to_index"]
        user_index = user_to_index.get(patient_id)
        if user_index is None:
            return {}

        known = [
            (caregiver_id, caregiver_to_index[caregiver_id])
            for caregiver_id in caregiver_ids
            if caregiver_id in caregiver_to_index
        ]
        if not known:
            return {}

        user_indices = torch.full((len(known),), int(user_index), dtype=torch.long)
        candidate_indices = torch.tensor([item[1] for item in known], dtype=torch.long)
        with torch.inference_mode():
            scores = torch.sigmoid(self._model(user_indices, candidate_indices)).tolist()
        return {known[index][0]: float(score) for index, score in enumerate(scores)}

    def _load_if_needed(self) -> None:
        try:
            mtime_ns = self.artifact_path.stat().st_mtime_ns
        except FileNotFoundError:
            self._mtime_ns = None
            self._artifact = None
            self._model = None
            return

        if self._mtime_ns == mtime_ns and self._artifact is not None:
            return

        try:
            artifact = torch.load(
                self.artifact_path,
                map_location="cpu",
                weights_only=True,
            )
            if artifact.get("format_version") != MODEL_FORMAT_VERSION:
                raise ValueError("Unsupported recruitment model format")
            model = ImplicitMatrixFactorization(
                num_users=len(artifact["user_to_index"]),
                num_candidates=len(artifact["caregiver_to_index"]),
                embedding_dim=int(artifact["embedding_dim"]),
            )
            model.load_state_dict(artifact["state_dict"])
            model.eval()
        except Exception:
            logger.exception("Failed to load recruitment model from %s", self.artifact_path)
            self._mtime_ns = mtime_ns
            self._artifact = None
            self._model = None
            return

        self._mtime_ns = mtime_ns
        self._artifact = artifact
        self._model = model
        logger.info(
            "Loaded recruitment model %s from %s",
            artifact.get("model_version"),
            self.artifact_path,
        )
