from fastapi import APIRouter, HTTPException

from core.config import settings
from core.database import get_connection
from models.schemas import Medicine, MedicineDetail

router = APIRouter()


@router.get("/medicine/{medicine_id}", response_model=MedicineDetail, summary="Medicine details + same-composition alternatives")
def get_medicine(medicine_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM medicines WHERE id = ?", (medicine_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Medicine not found")

        medicine = Medicine(**dict(row))

        alt_rows = conn.execute(
            "SELECT * FROM medicines WHERE composition = ? AND id != ? LIMIT ?",
            (medicine.composition, medicine_id, settings.ALTERNATIVES_LIMIT),
        ).fetchall()

    alternatives = [Medicine(**dict(r)) for r in alt_rows]

    return MedicineDetail(
        medicine=medicine,
        alternatives=alternatives,
        alternatives_count=len(alternatives),
    )


@router.get("/medicines", response_model=list[Medicine], summary="List all medicines with optional category filter")
def list_medicines(
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    with get_connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM medicines WHERE category = ? LIMIT ? OFFSET ?",
                (category, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM medicines LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

    return [Medicine(**dict(r)) for r in rows]


@router.get("/categories", response_model=list[str], summary="All available medicine categories")
def get_categories():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM medicines ORDER BY category"
        ).fetchall()
    return [r["category"] for r in rows]
