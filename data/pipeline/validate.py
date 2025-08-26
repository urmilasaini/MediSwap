"""
data/pipeline/validate.py
──────────────────────────
Schema and quality validation for the cleaned medicine DataFrame.
Returns (valid_df, rejected_df) so bad rows can be inspected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd


# ── Rules ──────────────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    valid:    pd.DataFrame
    rejected: pd.DataFrame
    report:   dict = field(default_factory=dict)

    @property
    def valid_count(self)    -> int: return len(self.valid)
    @property
    def rejected_count(self) -> int: return len(self.rejected)
    @property
    def pass_rate(self)      -> float:
        total = self.valid_count + self.rejected_count
        return round(self.valid_count / total * 100, 1) if total else 0.0


class Validator:
    """
    Validates a preprocessed medicines DataFrame.

    Rules
    -----
    - brand_name   : non-empty, length ≥ 2
    - composition  : non-empty
    - salt_name    : non-empty
    - manufacturer : non-empty
    - category     : non-empty
    - review_pcts  : each in [0, 100], sum in [0, 105] (small floating-point slack)
    """

    REQUIRED_NON_EMPTY = ["brand_name", "composition", "salt_name", "manufacturer", "category"]
    PCT_COLUMNS        = ["excellent_review_pct", "average_review_pct", "poor_review_pct"]

    def run(self, df: pd.DataFrame, rejected_path: Optional[Path] = None) -> ValidationResult:
        from rich.console import Console
        console = Console()
        console.print("[cyan]⚙ Validating …[/cyan]")

        reasons: list[pd.Series] = []

        # Rule 1: required fields non-empty
        for col in self.REQUIRED_NON_EMPTY:
            if col in df.columns:
                bad = df[col].isna() | (df[col].astype(str).str.strip() == "")
                reasons.append(bad.rename(f"empty_{col}"))

        # Rule 2: brand_name length ≥ 2
        if "brand_name" in df.columns:
            too_short = df["brand_name"].astype(str).str.len() < 2
            reasons.append(too_short.rename("brand_name_too_short"))

        # Rule 3: review percentages in valid range
        for col in self.PCT_COLUMNS:
            if col in df.columns:
                out_of_range = (df[col] < 0) | (df[col] > 100)
                reasons.append(out_of_range.rename(f"{col}_out_of_range"))

        # Rule 4: review sum shouldn't be wildly off (> 110 = data error)
        pct_cols_present = [c for c in self.PCT_COLUMNS if c in df.columns]
        if len(pct_cols_present) == 3:
            pct_sum = df[pct_cols_present].sum(axis=1)
            bad_sum = (pct_sum > 0) & (pct_sum < 50)   # sum too low → likely bad data
            reasons.append(bad_sum.rename("review_sum_too_low"))

        # Combine all rules
        if reasons:
            reject_mask = pd.concat(reasons, axis=1).any(axis=1)
        else:
            reject_mask = pd.Series(False, index=df.index)

        valid    = df[~reject_mask].reset_index(drop=True)
        rejected = df[reject_mask].reset_index(drop=True)

        report = {
            "total":            len(df),
            "valid":            len(valid),
            "rejected":         len(rejected),
            "pass_rate_pct":    round(len(valid) / len(df) * 100, 1) if len(df) else 0,
            "rejection_reasons": {
                r.name: int(r.sum()) for r in reasons if int(r.sum()) > 0
            },
        }

        if rejected_path and not rejected.empty:
            rejected_path.parent.mkdir(parents=True, exist_ok=True)
            rejected.to_csv(rejected_path, index=False)
            console.print(f"   [dim]Rejected rows saved → {rejected_path}[/dim]")

        console.print(
            f"   [green]✓ Valid: {len(valid):,}[/green]  "
            f"[red]✗ Rejected: {len(rejected):,}[/red]  "
            f"(pass rate {report['pass_rate_pct']}%)"
        )

        if report["rejection_reasons"]:
            for reason, count in report["rejection_reasons"].items():
                console.print(f"   [dim]  {reason}: {count}[/dim]")

        return ValidationResult(valid=valid, rejected=rejected, report=report)
