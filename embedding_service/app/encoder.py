import hashlib
import math

from embedding_service.app.config import settings


class Encoder:
    def __init__(self) -> None:
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(f"BAAI/{settings.embedding_model}")
        except Exception:
            self._model = None

    def encode(self, texts: list[str]) -> list[list[float]]:
        if self._model is not None:
            vectors = self._model.encode(texts, normalize_embeddings=True)
            return [vector.tolist() for vector in vectors]
        return [self._hash_embedding(text) for text in texts]

    def _hash_embedding(self, text: str) -> list[float]:
        values = [0.0] * settings.embedding_dimension
        for token in text:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % settings.embedding_dimension
            sign = 1 if digest[4] % 2 == 0 else -1
            values[idx] += sign
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]


encoder = Encoder()
