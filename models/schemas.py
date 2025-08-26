from typing import List, Optional
from pydantic import BaseModel, Field


# ── Core entity ───────────────────────────────────────────────────────────────

class Medicine(BaseModel):
    id: int
    brand_name: str
    composition: str
    salt_name: str
    manufacturer: str
    strength: str
    category: str
    description: Optional[str] = None
    uses: Optional[str] = None
    side_effects: Optional[str] = None
    image_url: Optional[str] = None
    excellent_review_pct: float = 0.0
    average_review_pct: float = 0.0
    poor_review_pct: float = 0.0


# ── Search ────────────────────────────────────────────────────────────────────

class SearchHit(BaseModel):
    id: int
    brand_name: str
    composition: str
    manufacturer: str
    category: str
    score: float = Field(..., description="Fuzzy match score 0–100")


class SearchResponse(BaseModel):
    query: str
    results: List[SearchHit]
    total: int


# ── Medicine detail ───────────────────────────────────────────────────────────

class MedicineDetail(BaseModel):
    medicine: Medicine
    alternatives: List[Medicine]
    alternatives_count: int


# ── Semantic search ───────────────────────────────────────────────────────────

class SemanticHit(BaseModel):
    id: int
    brand_name: str
    composition: str
    manufacturer: str
    category: str
    description: Optional[str] = None
    uses: Optional[str] = None
    score: float = Field(..., description="Cosine similarity score 0–1")


class SemanticResponse(BaseModel):
    query: str
    results: List[SemanticHit]
    index_ready: bool


# ── System ────────────────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    status: str
    medicines_loaded: int
    fuzzy_index_size: int
    vector_count: int
    index_ready: bool
    index_building: bool
