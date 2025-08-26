"""
data/pipeline/preprocess.py
────────────────────────────
Clean and normalise raw medicine CSV into our canonical schema.

Handles two input formats:
  • Kaggle (singhnavjot2062001/11000-medicine-details)
      Medicine Name, Composition, Uses, Side_effects, Image URL,
      Manufacturer, Excellent Review %, Average Review %, Poor Review %
  • Seed / custom
      brand_name, composition, salt_name, manufacturer, strength,
      category, description, uses, side_effects, image_url,
      excellent_review_pct, average_review_pct, poor_review_pct
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Composition parser ─────────────────────────────────────────────────────────
# Matches patterns like: "Paracetamol (650mg)" or "Ibuprofen (400mg)"
_COMPONENT_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9\s\-\'\,\.]+?)\s*\(([^)]+)\)"
)


def parse_composition(raw: Optional[str]) -> tuple[str, str, str]:
    """
    Parse a raw composition string.

    Examples
    --------
    "Paracetamol (650mg)"
        → ("Paracetamol 650mg", "Paracetamol", "650mg")

    "Amoxycillin (250mg) + Potassium Clavulanate (125mg)"
        → ("Amoxycillin 250mg + Potassium Clavulanate 125mg",
           "Amoxycillin + Potassium Clavulanate",
           "250mg + 125mg")

    Returns
    -------
    (normalized_composition, salt_name, strength)
    """
    if not raw or not isinstance(raw, str) or not raw.strip():
        return "", "", ""

    raw = raw.strip()
    matches = _COMPONENT_RE.findall(raw)

    if not matches:
        # No parenthesised strength — return as-is
        return raw, raw, ""

    salts     = [m[0].strip() for m in matches]
    strengths = [m[1].strip() for m in matches]

    composition = " + ".join(f"{s} {st}" for s, st in zip(salts, strengths))
    salt_name   = " + ".join(salts)
    strength    = " + ".join(strengths)

    return composition, salt_name, strength


# ── Category inference ─────────────────────────────────────────────────────────

_SALT_TO_CATEGORY: dict[str, str] = {
    # Analgesics
    "paracetamol": "Analgesic", "acetaminophen": "Analgesic",
    "tramadol": "Analgesic", "codeine": "Analgesic",
    # NSAIDs
    "ibuprofen": "Anti-inflammatory", "diclofenac": "Anti-inflammatory",
    "naproxen": "Anti-inflammatory", "aceclofenac": "Anti-inflammatory",
    "mefenamic": "Anti-inflammatory", "piroxicam": "Anti-inflammatory",
    "meloxicam": "Anti-inflammatory", "celecoxib": "Anti-inflammatory",
    "aspirin": "Analgesic",
    # Antibiotics
    "amoxicillin": "Antibiotic", "amoxycillin": "Antibiotic",
    "azithromycin": "Antibiotic", "ciprofloxacin": "Antibiotic",
    "levofloxacin": "Antibiotic", "ofloxacin": "Antibiotic",
    "doxycycline": "Antibiotic", "metronidazole": "Antibiotic",
    "cefpodoxime": "Antibiotic", "cefixime": "Antibiotic",
    "ceftriaxone": "Antibiotic", "ampicillin": "Antibiotic",
    "clindamycin": "Antibiotic", "erythromycin": "Antibiotic",
    "clarithromycin": "Antibiotic", "linezolid": "Antibiotic",
    "meropenem": "Antibiotic", "piperacillin": "Antibiotic",
    "vancomycin": "Antibiotic", "tetracycline": "Antibiotic",
    "nitrofurantoin": "Antibiotic", "sulfamethoxazole": "Antibiotic",
    "rifampicin": "Antibiotic", "isoniazid": "Antibiotic",
    "ethambutol": "Antibiotic",
    # Antidiabetics
    "metformin": "Antidiabetic", "glimepiride": "Antidiabetic",
    "glibenclamide": "Antidiabetic", "sitagliptin": "Antidiabetic",
    "vildagliptin": "Antidiabetic", "pioglitazone": "Antidiabetic",
    "dapagliflozin": "Antidiabetic", "empagliflozin": "Antidiabetic",
    "saxagliptin": "Antidiabetic", "linagliptin": "Antidiabetic",
    "acarbose": "Antidiabetic", "insulin": "Antidiabetic",
    "liraglutide": "Antidiabetic",
    # Antihypertensives
    "amlodipine": "Antihypertensive", "telmisartan": "Antihypertensive",
    "losartan": "Antihypertensive", "atenolol": "Antihypertensive",
    "enalapril": "Antihypertensive", "ramipril": "Antihypertensive",
    "valsartan": "Antihypertensive", "nebivolol": "Antihypertensive",
    "metoprolol": "Antihypertensive", "olmesartan": "Antihypertensive",
    "irbesartan": "Antihypertensive", "candesartan": "Antihypertensive",
    "nifedipine": "Antihypertensive", "felodipine": "Antihypertensive",
    "hydrochlorothiazide": "Antihypertensive", "indapamide": "Antihypertensive",
    "furosemide": "Antihypertensive", "spironolactone": "Antihypertensive",
    # Statins
    "atorvastatin": "Statin", "rosuvastatin": "Statin",
    "simvastatin": "Statin", "pitavastatin": "Statin",
    "pravastatin": "Statin", "lovastatin": "Statin",
    "fluvastatin": "Statin", "ezetimibe": "Statin",
    # PPIs
    "pantoprazole": "Proton Pump Inhibitor", "omeprazole": "Proton Pump Inhibitor",
    "rabeprazole": "Proton Pump Inhibitor", "esomeprazole": "Proton Pump Inhibitor",
    "lansoprazole": "Proton Pump Inhibitor", "dexlansoprazole": "Proton Pump Inhibitor",
    # Antihistamines
    "cetirizine": "Antihistamine", "fexofenadine": "Antihistamine",
    "loratadine": "Antihistamine", "levocetirizine": "Antihistamine",
    "chlorpheniramine": "Antihistamine", "diphenhydramine": "Antihistamine",
    "desloratadine": "Antihistamine", "bilastine": "Antihistamine",
    # Bronchodilators
    "montelukast": "Bronchodilator", "salbutamol": "Bronchodilator",
    "salmeterol": "Bronchodilator", "budesonide": "Bronchodilator",
    "fluticasone": "Bronchodilator", "formoterol": "Bronchodilator",
    "tiotropium": "Bronchodilator", "ipratropium": "Bronchodilator",
    "theophylline": "Bronchodilator", "aminophylline": "Bronchodilator",
    # Thyroid
    "levothyroxine": "Thyroid", "liothyronine": "Thyroid",
    "carbimazole": "Thyroid", "propylthiouracil": "Thyroid",
    # Vitamins
    "methylcobalamin": "Vitamin", "cholecalciferol": "Vitamin",
    "cyanocobalamin": "Vitamin", "ascorbic acid": "Vitamin",
    "pyridoxine": "Vitamin", "thiamine": "Vitamin",
    "riboflavin": "Vitamin", "folic acid": "Vitamin",
    "nicotinamide": "Vitamin", "biotin": "Vitamin",
    "retinol": "Vitamin", "tocopherol": "Vitamin",
    # Antidepressants / Anxiolytics
    "escitalopram": "Antidepressant", "sertraline": "Antidepressant",
    "fluoxetine": "Antidepressant", "paroxetine": "Antidepressant",
    "duloxetine": "Antidepressant", "venlafaxine": "Antidepressant",
    "amitriptyline": "Antidepressant", "mirtazapine": "Antidepressant",
    "clonazepam": "Antidepressant", "alprazolam": "Antidepressant",
    "diazepam": "Antidepressant", "lorazepam": "Antidepressant",
    "quetiapine": "Antidepressant", "olanzapine": "Antidepressant",
    # Antifungals
    "fluconazole": "Antifungal", "ketoconazole": "Antifungal",
    "clotrimazole": "Antifungal", "terbinafine": "Antifungal",
    "itraconazole": "Antifungal", "voriconazole": "Antifungal",
    "amphotericin": "Antifungal",
    # Corticosteroids
    "prednisolone": "Corticosteroid", "dexamethasone": "Corticosteroid",
    "methylprednisolone": "Corticosteroid", "hydrocortisone": "Corticosteroid",
    "betamethasone": "Corticosteroid", "triamcinolone": "Corticosteroid",
    "beclomethasone": "Corticosteroid",
    # Antiemetics
    "domperidone": "Antiemetic", "ondansetron": "Antiemetic",
    "metoclopramide": "Antiemetic", "promethazine": "Antiemetic",
    "granisetron": "Antiemetic",
    # Antivirals
    "acyclovir": "Antiviral", "oseltamivir": "Antiviral",
    "tenofovir": "Antiviral", "lamivudine": "Antiviral",
    "sofosbuvir": "Antiviral", "remdesivir": "Antiviral",
    # Minerals
    "ferrous": "Mineral", "iron": "Mineral",
    "calcium": "Mineral", "zinc": "Mineral",
    "magnesium": "Mineral", "potassium": "Mineral",
}

_USES_TO_CATEGORY: list[tuple[str, str]] = [
    ("fever", "Analgesic"),
    ("pain relief", "Analgesic"),
    ("headache", "Analgesic"),
    ("bacterial infection", "Antibiotic"),
    ("antibiotic", "Antibiotic"),
    ("diabetes", "Antidiabetic"),
    ("blood sugar", "Antidiabetic"),
    ("blood pressure", "Antihypertensive"),
    ("hypertension", "Antihypertensive"),
    ("cholesterol", "Statin"),
    ("dyslipidemia", "Statin"),
    ("acid reflux", "Proton Pump Inhibitor"),
    ("gastric", "Proton Pump Inhibitor"),
    ("ulcer", "Proton Pump Inhibitor"),
    ("allerg", "Antihistamine"),
    ("urticaria", "Antihistamine"),
    ("asthma", "Bronchodilator"),
    ("bronchitis", "Bronchodilator"),
    ("thyroid", "Thyroid"),
    ("vitamin", "Vitamin"),
    ("b12", "Vitamin"),
    ("depress", "Antidepressant"),
    ("anxiet", "Antidepressant"),
    ("fungal", "Antifungal"),
    ("vomit", "Antiemetic"),
    ("nausea", "Antiemetic"),
    ("viral", "Antiviral"),
    ("influenza", "Antiviral"),
]


def infer_category(salt_name: str, uses: str = "") -> str:
    salt_lower = (salt_name or "").lower()
    for key, cat in _SALT_TO_CATEGORY.items():
        if key in salt_lower:
            return cat

    uses_lower = (uses or "").lower()
    for keyword, cat in _USES_TO_CATEGORY:
        if keyword in uses_lower:
            return cat

    return "General"


# ── Column mapping ─────────────────────────────────────────────────────────────

# Kaggle column names → our canonical names
_KAGGLE_COLUMNS = {
    "Medicine Name":        "brand_name",
    "Composition":          "_raw_composition",
    "Uses":                 "uses",
    "Side_effects":         "side_effects",
    "Image URL":            "image_url",
    "Manufacturer":         "manufacturer",
    "Excellent Review %":   "excellent_review_pct",
    "Average Review %":     "average_review_pct",
    "Poor Review %":        "poor_review_pct",
}

# Final canonical column order
CANONICAL_COLUMNS = [
    "brand_name", "composition", "salt_name", "manufacturer",
    "strength", "category", "description",
    "uses", "side_effects", "image_url",
    "excellent_review_pct", "average_review_pct", "poor_review_pct",
]


# ── Main class ─────────────────────────────────────────────────────────────────

class Preprocessor:
    """Transform a raw medicine CSV into our canonical schema."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or (Path(__file__).parent.parent / "processed")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, input_path: Path) -> Path:
        """Full preprocessing pipeline. Returns path to cleaned CSV."""
        from rich.console import Console
        from rich.progress import track

        console = Console()
        console.print(f"[cyan]⚙ Preprocessing: {input_path.name}[/cyan]")

        df = pd.read_csv(input_path, low_memory=False)
        console.print(f"   Raw rows: [bold]{len(df):,}[/bold]")

        df = self._rename_columns(df)
        df = self._parse_compositions(df)
        df = self._infer_categories(df)
        df = self._clean_text(df)
        df = self._clean_numerics(df)
        df = self._add_description(df)
        df = self._ensure_canonical_columns(df)
        df = self._deduplicate(df)

        out = self.output_dir / "medicines_clean.csv"
        df.to_csv(out, index=False)

        console.print(f"   Clean rows: [bold green]{len(df):,}[/bold green]")
        console.print(f"[green]✓ Saved → {out}[/green]")
        return out

    # ── Steps ──────────────────────────────────────────────────────────────

    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        rename = {k: v for k, v in _KAGGLE_COLUMNS.items() if k in df.columns}
        return df.rename(columns=rename)

    def _parse_compositions(self, df: pd.DataFrame) -> pd.DataFrame:
        raw_col = "_raw_composition" if "_raw_composition" in df.columns else "composition"

        parsed = df[raw_col].apply(parse_composition)
        df["composition"] = parsed.apply(lambda x: x[0])
        df["salt_name"]   = parsed.apply(lambda x: x[1])
        df["strength"]    = parsed.apply(lambda x: x[2])

        if "_raw_composition" in df.columns:
            df.drop(columns=["_raw_composition"], inplace=True)

        return df

    def _infer_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        if "category" not in df.columns:
            df["category"] = df.apply(
                lambda r: infer_category(
                    r.get("salt_name", ""), r.get("uses", "")
                ),
                axis=1,
            )
        else:
            # Fill any blanks
            mask = df["category"].isna() | (df["category"] == "")
            df.loc[mask, "category"] = df.loc[mask].apply(
                lambda r: infer_category(r.get("salt_name", ""), r.get("uses", "")),
                axis=1,
            )
        return df

    def _clean_text(self, df: pd.DataFrame) -> pd.DataFrame:
        text_cols = [
            "brand_name", "composition", "salt_name", "manufacturer",
            "strength", "category", "description", "uses",
            "side_effects", "image_url",
        ]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
        return df

    def _clean_numerics(self, df: pd.DataFrame) -> pd.DataFrame:
        pct_cols = ["excellent_review_pct", "average_review_pct", "poor_review_pct"]
        for col in pct_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).round(1)
        return df

    def _add_description(self, df: pd.DataFrame) -> pd.DataFrame:
        if "description" not in df.columns:
            df["description"] = df.get("uses", pd.Series([""] * len(df))).apply(
                lambda u: (u or "")[:160]
            )
        else:
            df["description"] = df["description"].fillna("").astype(str).str.strip()
        return df

    def _ensure_canonical_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in CANONICAL_COLUMNS:
            if col not in df.columns:
                default = 0.0 if col.endswith("_pct") else ""
                df[col] = default
        return df[CANONICAL_COLUMNS]

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df[df["brand_name"].str.len() > 0]
        df = df[df["composition"].str.len() > 0]
        df = df.drop_duplicates(subset=["brand_name"], keep="first")
        df = df.reset_index(drop=True)
        removed = before - len(df)
        if removed:
            from rich.console import Console
            Console().print(f"   [dim]Removed {removed} duplicates / blank rows[/dim]")
        return df
