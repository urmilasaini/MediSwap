"""
data/pipeline/stats.py
───────────────────────
Pretty-print dataset statistics using Rich tables.
"""

from __future__ import annotations

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


class DataStats:

    @staticmethod
    def summary(df: pd.DataFrame, title: str = "Dataset Summary") -> None:
        console.rule(f"[bold cyan]{title}[/bold cyan]")

        # ── Overview ──────────────────────────────────────────────────────────
        overview = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        overview.add_column("Key",   style="dim")
        overview.add_column("Value", style="bold")

        overview.add_row("Total medicines",    f"{len(df):,}")
        overview.add_row("Unique brands",      f"{df['brand_name'].nunique():,}")
        overview.add_row("Unique salts",       f"{df['salt_name'].nunique():,}")
        overview.add_row("Unique manufacturers", f"{df['manufacturer'].nunique():,}")
        overview.add_row("Categories",         f"{df['category'].nunique()}")

        has_uses = (df["uses"].astype(str).str.strip() != "").sum()
        has_side = (df["side_effects"].astype(str).str.strip() != "").sum()
        has_img  = (df["image_url"].astype(str).str.strip() != "").sum()
        overview.add_row("With uses",          f"{has_uses:,}  ({has_uses/len(df)*100:.0f}%)")
        overview.add_row("With side effects",  f"{has_side:,}  ({has_side/len(df)*100:.0f}%)")
        overview.add_row("With image URL",     f"{has_img:,}  ({has_img/len(df)*100:.0f}%)")

        pct_cols = ["excellent_review_pct", "average_review_pct", "poor_review_pct"]
        if all(c in df.columns for c in pct_cols):
            avg_exc = df["excellent_review_pct"].mean()
            overview.add_row("Avg excellent rating", f"{avg_exc:.1f}%")

        console.print(overview)

        # ── Category distribution ──────────────────────────────────────────────
        cat_table = Table(
            title="Medicines per Category",
            box=box.ROUNDED,
            style="dim",
            show_lines=False,
        )
        cat_table.add_column("Category",    style="cyan",  no_wrap=True)
        cat_table.add_column("Count",       style="bold",  justify="right")
        cat_table.add_column("% of total",              justify="right")
        cat_table.add_column("Bar",         style="green")

        counts = df["category"].value_counts()
        max_c  = counts.max()
        for cat, cnt in counts.items():
            pct  = cnt / len(df) * 100
            bar  = "█" * int(cnt / max_c * 20)
            cat_table.add_row(str(cat), f"{cnt:,}", f"{pct:.1f}%", bar)

        console.print(cat_table)

        # ── Top manufacturers ──────────────────────────────────────────────────
        mfr_table = Table(
            title="Top 10 Manufacturers",
            box=box.ROUNDED,
            style="dim",
        )
        mfr_table.add_column("Manufacturer", style="cyan")
        mfr_table.add_column("Medicines",    justify="right", style="bold")

        for mfr, cnt in df["manufacturer"].value_counts().head(10).items():
            mfr_table.add_row(str(mfr), f"{cnt:,}")

        console.print(mfr_table)

        # ── Multi-salt compositions ────────────────────────────────────────────
        multi = df[df["salt_name"].str.contains(r"\+", na=False)]
        console.print(
            f"\n[dim]Multi-salt combinations: [bold]{len(multi):,}[/bold] "
            f"({len(multi)/len(df)*100:.1f}% of total)[/dim]"
        )

    @staticmethod
    def sample(df: pd.DataFrame, n: int = 5) -> None:
        """Print a few random rows."""
        table = Table(title=f"Random Sample (n={n})", box=box.SIMPLE)
        cols = ["brand_name", "composition", "manufacturer", "category"]
        for c in cols:
            table.add_column(c, style="cyan" if c == "brand_name" else "")

        for _, row in df.sample(min(n, len(df))).iterrows():
            table.add_row(*[str(row.get(c, "")) for c in cols])

        console.print(table)
