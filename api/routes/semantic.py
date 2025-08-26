import asyncio

from fastapi import APIRouter, BackgroundTasks, Query

from models.schemas import SemanticHit, SemanticResponse
from services.embeddings import EmbeddingService
from services.vector_store import VectorStoreService

router = APIRouter()


@router.get("/semantic", response_model=SemanticResponse, summary="AI-powered semantic medicine search")
def semantic_search(
    q: str = Query(..., min_length=1, description="Natural language query e.g. 'fever medicine for adults'"),
    limit: int = Query(6, ge=1, le=20),
    background_tasks: BackgroundTasks = None,
):
    if not VectorStoreService.is_ready():
        if not VectorStoreService.is_building():
            # trigger build in background if not already running
            if background_tasks:
                background_tasks.add_task(_trigger_build)
        return SemanticResponse(
            query=q,
            results=[],
            index_ready=False,
        )

    loop = asyncio.new_event_loop()
    vector = EmbeddingService.embed(q)
    hits = VectorStoreService.search(vector, limit)

    results = [
        SemanticHit(
            id=hit["id"],
            brand_name=hit.get("brand_name", ""),
            composition=hit.get("composition", ""),
            manufacturer=hit.get("manufacturer", ""),
            category=hit.get("category", ""),
            description=hit.get("description"),
            score=hit["score"],
        )
        for hit in hits
    ]

    return SemanticResponse(query=q, results=results, index_ready=True)


async def _trigger_build():
    await VectorStoreService.build_from_db()
