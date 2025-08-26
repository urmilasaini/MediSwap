"""
data/pipeline/download.py
─────────────────────────
Download medicine data from Kaggle or fall back to seed CSV.

Kaggle dataset (11 000+ medicines):
    singhnavjot2062001/11000-medicine-details

Columns:
    Medicine Name, Composition, Uses, Side_effects,
    Image URL, Manufacturer,
    Excellent Review %, Average Review %, Poor Review %

Setup Kaggle credentials (one time):
    Option 1 – kaggle.json:
        Place ~/.kaggle/kaggle.json   (from https://www.kaggle.com/settings → API)
    Option 2 – environment variables:
        export KAGGLE_USERNAME=your_username
        export KAGGLE_KEY=your_key
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from rich.console import Console

console = Console()

# Primary Kaggle source
KAGGLE_DATASET  = "singhnavjot2062001/11000-medicine-details"
KAGGLE_FILENAME = "Medicine_Details.csv"

# Fallback: bundled seed generator
RAW_DIR       = Path(__file__).parent.parent / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "processed"


class DataDownloader:

    def __init__(self) -> None:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # ── Public ─────────────────────────────────────────────────────────────

    def get(self, force: bool = False) -> Path:
        """
        Return path to a raw CSV file ready for preprocessing.
        Tries Kaggle first; falls back to seed generator.
        """
        target = RAW_DIR / KAGGLE_FILENAME
        if target.exists() and not force:
            console.print(f"[dim]↩ Using cached raw file: {target}[/dim]")
            return target

        if self._has_kaggle_credentials():
            try:
                return self._download_kaggle(target)
            except Exception as exc:
                console.print(f"[yellow]⚠ Kaggle download failed: {exc}[/yellow]")

        console.print("[yellow]⚠ Kaggle credentials not found → using seed dataset[/yellow]")
        return self._generate_seed(target)

    # ── Kaggle ─────────────────────────────────────────────────────────────

    @staticmethod
    def _has_kaggle_credentials() -> bool:
        kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
        return (
            kaggle_json.exists()
            or (os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))
        )

    @staticmethod
    def _download_kaggle(target: Path) -> Path:
        import kaggle  # noqa: F401 – raises ImportError if package missing

        console.print(f"[cyan]↓ Downloading Kaggle dataset: {KAGGLE_DATASET}[/cyan]")
        from kaggle.api.kaggle_api_extended import KaggleApiExtended

        api = KaggleApiExtended()
        api.authenticate()
        api.dataset_download_files(KAGGLE_DATASET, path=str(RAW_DIR), unzip=False, quiet=False)

        zip_path = RAW_DIR / f"{KAGGLE_DATASET.split('/')[-1]}.zip"
        if zip_path.exists():
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(RAW_DIR)
            zip_path.unlink()

        if not target.exists():
            # Dataset might use a slightly different filename — find any CSV
            csvs = list(RAW_DIR.glob("*.csv"))
            if csvs:
                csvs[0].rename(target)
            else:
                raise FileNotFoundError("No CSV found after Kaggle unzip")

        rows = sum(1 for _ in open(target)) - 1
        console.print(f"[green]✓ Downloaded: {target.name}  ({rows:,} rows)[/green]")
        return target

    # ── Seed fallback ───────────────────────────────────────────────────────

    @staticmethod
    def _generate_seed(target: Path) -> Path:
        from data.pipeline.seed_generator import generate_csv

        console.print("[cyan]⚙ Generating seed dataset …[/cyan]")
        generate_csv(target)
        rows = sum(1 for _ in open(target)) - 1
        console.print(f"[green]✓ Seed CSV ready: {target.name}  ({rows:,} rows)[/green]")
        return target
