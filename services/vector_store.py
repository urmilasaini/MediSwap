from __future__ import annotations

import asyncio
from typing import List

from core.config import settings


class VectorStoreService:
    """Manages Qdrant vector index. Supports memory / local-file / remote modes."""

    _client = None
    _building: bool = False

    # ── Connection ────────────────────────────────────────────────────────────

    @classmethod
    async def connect(cls) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        try:
            if settings.QDRANT_MODE == "memory":
                cls._client = QdrantClient(":memory:")
            elif settings.QDRANT_MODE == "local":
                import os
                os.makedirs(settings.QDRANT_PATH, exist_ok=True)
                cls._client = QdrantClient(path=settings.QDRANT_PATH)
            else:
                cls._client = QdrantClient(url=settings.QDRANT_URL)

            existing = [c.name for c in cls._client.get_collections().collections]
            if settings.QDRANT_COLLECTION not in existing:
                cls._client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=settings.EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    ),
                )
                print(f"[VectorStore] Collection '{settings.QDRANT_COLLECTION}' created ({settings.QDRANT_MODE})")
            else:
                count = cls._client.count(settings.QDRANT_COLLECTION).count
                print(f"[VectorStore] Collection ready — {count} vectors ({settings.QDRANT_MODE})")

        except Exception as exc:
            print(f"[VectorStore] WARNING: could not connect — {exc}")
            cls._client = None

    # ── Index build ───────────────────────────────────────────────────────────

    @classmethod
    async def build_from_db(cls) -> None:
        """Embed all medicines from SQLite and upsert into Qdrant."""
        if cls._building:
            return
        cls._building = True

        try:
            from qdrant_client.models import PointStruct
            from core.database import get_connection
            from services.embeddings import EmbeddingService

            with get_connection() as conn:
                rows = conn.execute("SELECT * FROM medicines").fetchall()
            medicines = [dict(r) for r in rows]

            if not medicines:
                print("[VectorStore] No medicines to index")
                return

            print(f"[VectorStore] Building index for {len(medicines)} medicines...")
            texts = [EmbeddingService.build_medicine_text(m) for m in medicines]

            loop = asyncio.get_event_loop()
            vectors: List[List[float]] = await loop.run_in_executor(
                None, EmbeddingService.embed_batch, texts
            )

            points = [
                PointStruct(
                    id=m["id"],
                    vector=v,
                    payload={
                        "brand_name": m["brand_name"],
                        "composition": m["composition"],
                        "manufacturer": m["manufacturer"],
                        "category": m["category"],
                        "description": m.get("description") or "",
                    },
                )
                for m, v in zip(medicines, vectors)
            ]

            batch_size = 128
            for i in range(0, len(points), batch_size):
                cls._upsert_batch(points[i : i + batch_size])

            print(f"[VectorStore] Index ready — {cls.count()} vectors")

        except Exception as exc:
            print(f"[VectorStore] Build error: {exc}")
        finally:
            cls._building = False

    # ── Search ────────────────────────────────────────────────────────────────

    @classmethod
    def search(cls, vector: List[float], limit: int | None = None) -> List[dict]:
        if cls._client is None:
            return []
        limit = limit or settings.SEMANTIC_LIMIT
        try:
            if hasattr(cls._client, "query_points"):
                response = cls._client.query_points(
                    collection_name=settings.QDRANT_COLLECTION,
                    query=vector,
                    limit=limit,
                    with_payload=True,
                )
                hits = response.points
            else:
                hits = cls._client.search(
                    collection_name=settings.QDRANT_COLLECTION,
                    query_vector=vector,
                    limit=limit,
                    with_payload=True,
                )
            return [{"id": h.id, "score": round(h.score, 4), **h.payload} for h in hits]
        except Exception as exc:
            print(f"[VectorStore] Search error: {exc}")
            return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    @classmethod
    def _upsert_batch(cls, points: list) -> None:
        if cls._client:
            cls._client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)

    @classmethod
    def count(cls) -> int:
        if cls._client is None:
            return 0
        try:
            return cls._client.count(settings.QDRANT_COLLECTION).count
        except Exception:
            return 0

    @classmethod
    def is_ready(cls) -> bool:
        return cls._client is not None and cls.count() > 0

    @classmethod
    def is_building(cls) -> bool:
        return cls._building
