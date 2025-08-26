"""
scripts/setup.py
────────────────
One-command pipeline: download → preprocess → validate → ingest → index

Usage
-----
    python scripts/setup.py                     # auto-detect Kaggle or use seed
    python scripts/setup.py --source kaggle     # force Kaggle download
    python scripts/setup.py --source seed       # use bundled seed data
    python scripts/setup.py --skip-index        # skip Qdrant indexing (ingest only)
    python scripts/setup.py --rebuild           # drop DB + Qdrant and start fresh
    python scripts/setup.py --stats-only        # print stats on existing DB
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Make root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich import box

console = Console()


def banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]PharmaAI[/bold cyan] — Data Setup Pipeline\n"
            "[dim]Medicine Alternative Recommendation System[/dim]",
            box=box.DOUBLE_EDGE,
            border_style="cyan",
            padding=(1, 4),
        )
    )


def step(n: int, total: int, label: str) -> None:
    console.print(f"\n[bold cyan][{n}/{total}][/bold cyan] {label}")


def run(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    banner()

    from core.config import settings
    from core.database import init_db, get_connection
    from data.pipeline.download import DataDownloader
    from data.pipeline.preprocess import Preprocessor
    from data.pipeline.validate import Validator
    from data.pipeline.stats import DataStats

    TOTAL_STEPS = 4 if args.skip_index else 5

    # ── Stats-only mode ────────────────────────────────────────────────────────
    if args.stats_only:
        import pandas as pd
        init_db()
        with get_connection() as conn:
            df = pd.read_sql("SELECT * FROM medicines", conn)
        if df.empty:
            console.print("[red]No medicines in DB. Run setup first.[/red]")
            return
        DataStats.summary(df, "Current Database")
        DataStats.sample(df)
        return

    # ── Rebuild: drop existing data ────────────────────────────────────────────
    if args.rebuild:
        console.print(Rule("[yellow]Rebuild mode — dropping existing data[/yellow]"))
        db_path = Path(settings.DB_PATH)
        if db_path.exists():
            db_path.unlink()
            console.print(f"  [dim]Removed {db_path}[/dim]")
        qdrant_path = Path(settings.QDRANT_PATH)
        if qdrant_path.exists():
            import shutil
            shutil.rmtree(qdrant_path)
            console.print(f"  [dim]Removed {qdrant_path}[/dim]")

    # ── Step 1: Download ───────────────────────────────────────────────────────
    step(1, TOTAL_STEPS, "Downloading / loading raw data")
    downloader = DataDownloader()

    if args.source == "kaggle":
        from data.pipeline.download import RAW_DIR, KAGGLE_FILENAME
        raw_path = downloader._download_kaggle(RAW_DIR / KAGGLE_FILENAME)
    elif args.source == "seed":
        from data.pipeline.seed_generator import generate_csv
        raw_path = Path(settings.DB_PATH).parent / "raw" / "seed_medicines.csv"
        generate_csv(raw_path)
        console.print(f"[green]✓ Seed CSV generated: {raw_path.name}[/green]")
    else:
        raw_path = downloader.get(force=args.rebuild)

    # ── Step 2: Preprocess ────────────────────────────────────────────────────
    step(2, TOTAL_STEPS, "Preprocessing — parse compositions, infer categories, clean text")
    preprocessor = Preprocessor()
    clean_path = preprocessor.run(raw_path)

    # ── Step 3: Validate ──────────────────────────────────────────────────────
    step(3, TOTAL_STEPS, "Validating data quality")
    import pandas as pd

    df = pd.read_csv(clean_path)
    rejected_path = clean_path.parent / "rejected_rows.csv"
    result = Validator().run(df, rejected_path=rejected_path)

    DataStats.summary(result.valid, "Validated Dataset")

    # ── Step 4: Ingest to SQLite ──────────────────────────────────────────────
    step(4, TOTAL_STEPS, "Loading medicines into SQLite")
    init_db()

    with get_connection() as conn:
        conn.execute("DELETE FROM medicines")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'medicines'")
        ingest_df = result.valid.copy()
        text_columns = [
            "brand_name", "composition", "salt_name", "manufacturer",
            "strength", "category", "description", "uses",
            "side_effects", "image_url",
        ]
        ingest_df[text_columns] = ingest_df[text_columns].fillna("")
        rows = ingest_df.to_dict(orient="records")
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

    console.print(f"[green]✓ {count:,} medicines inserted into SQLite[/green]")

    # ── Step 5: Build vector index ────────────────────────────────────────────
    if not args.skip_index:
        step(5, TOTAL_STEPS, f"Building Qdrant vector index  [{settings.QDRANT_MODE} mode]")
        asyncio.run(_build_index())

    elapsed = time.perf_counter() - start
    result_label = "loaded" if args.skip_index else "indexed"
    console.print(
        Panel.fit(
            f"[bold green]Setup complete![/bold green]  "
            f"{count:,} medicines {result_label}  •  {elapsed:.1f}s",
            border_style="green",
        )
    )


async def _build_index() -> None:
    from services.vector_store import VectorStoreService

    await VectorStoreService.connect()

    if VectorStoreService.is_ready():
        from core.config import settings as s
        if s.QDRANT_MODE == "local":
            console.print("[dim]Existing local index found — use --rebuild to force[/dim]")
            return

    await VectorStoreService.build_from_db()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PharmaAI data setup pipeline")
    p.add_argument(
        "--source",
        choices=["auto", "kaggle", "seed"],
        default="auto",
        help="Data source (default: auto — Kaggle if creds available, else seed)",
    )
    p.add_argument("--skip-index",  action="store_true", help="Skip Qdrant indexing")
    p.add_argument("--rebuild",     action="store_true", help="Drop and rebuild everything")
    p.add_argument("--stats-only",  action="store_true", help="Print DB stats and exit")
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
