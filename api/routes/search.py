from fastapi import APIRouter, Query

from core.database import get_connection
from models.schemas import SearchHit, SearchResponse
from services.fuzzy_search import FuzzySearchService

router = APIRouter()


@router.get("/search", response_model=SearchResponse, summary="Fuzzy brand-name search")
def search_medicines(
    q: str = Query(..., min_length=1, description="Medicine name (partial or misspelled OK)"),
    limit: int = Query(10, ge=1, le=50),
):
    fuzzy_hits = FuzzySearchService.search(q, limit)
    if not fuzzy_hits:
        return SearchResponse(query=q, results=[], total=0)

    ids = [h["id"] for h in fuzzy_hits]
    score_map = {h["id"]: h["score"] for h in fuzzy_hits}

    placeholders = ",".join("?" * len(ids))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT id, brand_name, composition, manufacturer, category "
            f"FROM medicines WHERE id IN ({placeholders})",
            ids,
        ).fetchall()

    results = [
        SearchHit(
            id=row["id"],
            brand_name=row["brand_name"],
            composition=row["composition"],
            manufacturer=row["manufacturer"],
            category=row["category"],
            score=score_map.get(row["id"], 0.0),
        )
        for row in rows
    ]
    results.sort(key=lambda x: x.score, reverse=True)

    return SearchResponse(query=q, results=results, total=len(results))
