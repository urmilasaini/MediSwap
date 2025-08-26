"""
PharmaAI — Medicine Alternative Recommendation System
======================================================
Entry point. Run with:

    uvicorn app:app --reload          # dev
    python app.py                     # production (Hugging Face Spaces uses port 7860)
"""

import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import init_db
from models.schemas import StatusResponse
from services.fuzzy_search import FuzzySearchService
from services.vector_store import VectorStoreService
from api.routes import medicines, search, semantic

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"{'─'*50}")

    init_db()

    # Auto-ingest CSV if DB is empty
    from core.database import get_connection
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]

    if count == 0:
        print("[Startup] DB empty — running ingest ...")
        from scripts.ingest_data import ingest
        ingest()

    await FuzzySearchService.load()
    await VectorStoreService.connect()

    # Build vector index in background if empty
    if not VectorStoreService.is_ready():
        print("[Startup] Vector index empty — building in background ...")
        asyncio.create_task(VectorStoreService.build_from_db())

    print(f"{'─'*50}\n")

    yield  # ── app running ──────────────────────────────────────────────────


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description="Semantic medicine alternative recommendation using BGE embeddings + Qdrant.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(search.router,    prefix="/api", tags=["Search"])
app.include_router(medicines.router, prefix="/api", tags=["Medicines"])
app.include_router(semantic.router,  prefix="/api", tags=["Semantic"])


@app.get("/api/status", response_model=StatusResponse, tags=["System"])
async def status():
    from core.database import get_connection
    with get_connection() as conn:
        med_count = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]

    return StatusResponse(
        status="ok",
        medicines_loaded=med_count,
        fuzzy_index_size=FuzzySearchService.size(),
        vector_count=VectorStoreService.count(),
        index_ready=VectorStoreService.is_ready(),
        index_building=VectorStoreService.is_building(),
    )


@app.get("/api/health", tags=["System"])
async def health():
    return {"status": "ok"}


# ── Static (must be last — catches everything else) ───────────────────────────

app.mount("/", StaticFiles(directory="static", html=True), name="static")


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)
