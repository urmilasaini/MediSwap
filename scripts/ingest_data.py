"""
scripts/ingest_data.py
──────────────────────
Load a medicine CSV into SQLite.
Handles both the original minimal schema and the full schema with
uses / side_effects / image_url / review percentages.

Usage
-----
    python scripts/ingest_data.py                         # use settings.DATA_CSV
    python scripts/ingest_data.py --csv path/to/file.csv
    python scripts/ingest_data.py --csv data/processed/medicines_clean.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import track

console = Console()

REQUIRED = {"brand_name", "composition", "salt_name", "manufacturer", "strength", "category"}

# Columns with defaults when missing from the CSV
OPTIONAL_DEFAULTS: dict[str, object] = {
    "description":          "",
    "uses":                 "",
    "side_effects":         "",
    "image_url":            "",
    "excellent_review_pct": 0.0,
    "average_review_pct":   0.0,
    "poor_review_pct":      0.0,
}


def ingest(csv_path: str | None = None) -> int:
    from core.config import settings
    from core.database import init_db, get_connection

    csv_file = Path(csv_path or settings.DATA_CSV)
    if not csv_file.exists():
        console.print(f"[red]ERROR: {csv_file} not found[/red]")
        console.print(
            "[dim]Run  python scripts/setup.py  to download and preprocess data.[/dim]"
        )
        sys.exit(1)

    console.print(f"[cyan]Reading:[/cyan] {csv_file}")
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    if not raw_rows:
        console.print("[red]ERROR: CSV is empty[/red]")
        sys.exit(1)

    # Validate required columns
    missing = REQUIRED - set(raw_rows[0].keys())
    if missing:
        console.print(f"[red]ERROR: Missing required columns: {missing}[/red]")
        sys.exit(1)

    # Fill optional columns with defaults
    rows: list[dict] = []
    for raw in raw_rows:
        row = dict(raw)
        for col, default in OPTIONAL_DEFAULTS.items():
            val = row.get(col, "")
            if val is None or str(val).strip() == "":
                row[col] = default
            elif isinstance(default, float):
                try:
                    row[col] = float(val)
                except (ValueError, TypeError):
                    row[col] = default
        rows.append(row)

    console.print(f"[dim]{len(rows):,} rows read[/dim]")

    init_db()

    with get_connection() as conn:
        conn.execute("DELETE FROM medicines")
        conn.executemany(
            """
            INSERT INTO medicines
                (brand_name, composition, salt_name, manufacturer, strength, category,
                 description, uses, side_effects, image_url,
                 excellent_review_pct, average_review_pct, poor_review_pct)
            VALUES
                (:brand_name, :composition, :salt_name, :manufacturer, :strength, :category,
                 :description, :uses, :side_effects, :image_url,
                 :excellent_review_pct, :average_review_pct, :poor_review_pct)
            """,
            rows,
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]

    console.print(f"[green]✓ {count:,} medicines loaded → {settings.DB_PATH}[/green]")
    return count


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest medicine CSV into SQLite")
    p.add_argument("--csv", help="Path to CSV file (default: settings.DATA_CSV)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    ingest(args.csv)
