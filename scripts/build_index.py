"""
scripts/build_index.py
──────────────────────
Embed medicines from SQLite and push vectors into Qdrant.

Usage:
    python scripts/build_index.py            # uses settings from .env
    python scripts/build_index.py --rebuild  # drops collection and rebuilds
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings
from core.database import get_connection
from services.embeddings import EmbeddingService
from services.vector_store import VectorStoreService


async def build(rebuild: bool = False) -> None:
    print(f"[Index] Connecting to Qdrant ({settings.QDRANT_MODE}) ...")
    await VectorStoreService.connect()

    if VectorStoreService._client is None:
        raise RuntimeError("Could not connect to Qdrant; stop any running app instance and retry")

    if rebuild and VectorStoreService._client:
        from qdrant_client.models import Distance, VectorParams
        try:
            VectorStoreService._client.delete_collection(settings.QDRANT_COLLECTION)
            print(f"[Index] Dropped collection '{settings.QDRANT_COLLECTION}'")
        except Exception:
            pass
        VectorStoreService._client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )
        print(f"[Index] Recreated collection '{settings.QDRANT_COLLECTION}'")

    if not rebuild and VectorStoreService.is_ready():
        print(f"[Index] Already indexed ({VectorStoreService.count()} vectors). Use --rebuild to force.")
        return

    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM medicines").fetchall()

    medicines = [dict(r) for r in rows]
    if not medicines:
        print("[Index] No medicines found — run scripts/ingest_data.py first")
        return

    print(f"[Index] Embedding {len(medicines)} medicines with {settings.EMBEDDING_MODEL} ...")
    texts = [EmbeddingService.build_medicine_text(m) for m in medicines]
    vectors = EmbeddingService.embed_batch(texts)

    from qdrant_client.models import PointStruct

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
        batch = points[i : i + batch_size]
        VectorStoreService._upsert_batch(batch)
        done = min(i + batch_size, len(points))
        print(f"[Index] Upserted {done}/{len(points)}")

    print(f"[Index] Done — {VectorStoreService.count()} vectors in Qdrant")
    VectorStoreService._client.close()
    VectorStoreService._client = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Qdrant vector index from SQLite")
    parser.add_argument("--rebuild", action="store_true", help="Drop and rebuild existing index")
    args = parser.parse_args()
    asyncio.run(build(rebuild=args.rebuild))
