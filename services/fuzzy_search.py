from __future__ import annotations

from typing import List, Tuple

from core.config import settings


class FuzzySearchService:
    """In-memory RapidFuzz search over brand names. Loaded once at startup."""

    _index: List[Tuple[int, str]] = []   # [(id, brand_name), ...]

    @classmethod
    async def load(cls) -> None:
        from core.database import get_connection

        with get_connection() as conn:
            rows = conn.execute("SELECT id, brand_name FROM medicines ORDER BY id").fetchall()

        cls._index = [(r["id"], r["brand_name"]) for r in rows]
        print(f"[FuzzySearch] Indexed {len(cls._index)} brand names")

    @classmethod
    def search(cls, query: str, limit: int | None = None) -> List[dict]:
        from rapidfuzz import fuzz, process

        if not cls._index:
            return []

        limit = limit or settings.FUZZY_LIMIT
        names = [name for _, name in cls._index]

        matches = process.extract(
            query,
            names,
            scorer=fuzz.WRatio,
            limit=limit * 3,            # over-fetch, then filter by threshold
        )

        results: List[dict] = []
        seen_ids: set = set()

        for match_name, score, idx in matches:
            if score < settings.FUZZY_THRESHOLD:
                continue
            med_id = cls._index[idx][0]
            if med_id in seen_ids:
                continue
            seen_ids.add(med_id)
            results.append({"id": med_id, "brand_name": match_name, "score": round(score, 1)})

        return results[:limit]

    @classmethod
    async def reload(cls) -> None:
        await cls.load()

    @classmethod
    def size(cls) -> int:
        return len(cls._index)
