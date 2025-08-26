from __future__ import annotations

from typing import List

from core.config import settings


class EmbeddingService:
    """Lazy-loads BGE-small model; thread-safe singleton."""

    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            from sentence_transformers import SentenceTransformer
            print(f"[Embeddings] Loading {settings.EMBEDDING_MODEL} ...")
            cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            print("[Embeddings] Model ready")
        return cls._model

    @classmethod
    def embed(cls, text: str) -> List[float]:
        model = cls._get_model()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    @classmethod
    def embed_batch(cls, texts: List[str]) -> List[List[float]]:
        model = cls._get_model()
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=64,
            show_progress_bar=len(texts) > 50,
        )
        return vectors.tolist()

    @staticmethod
    def build_medicine_text(medicine: dict) -> str:
        """
        Combine medicine fields into a rich embedding string.
        Field order and weighting matters for retrieval quality:
          1. brand_name   — primary identifier
          2. composition  — exact salt match
          3. category     — coarse group
          4. uses         — natural language; most helpful for semantic queries
          5. description  — short summary
        """
        parts = [
            medicine.get("brand_name", ""),
            medicine.get("composition", ""),
            medicine.get("category", ""),
            medicine.get("uses", "") or "",
            medicine.get("description", "") or "",
        ]
        return " | ".join(p.strip() for p in parts if p and p.strip())
