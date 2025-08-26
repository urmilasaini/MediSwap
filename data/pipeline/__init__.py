"""
data/pipeline
─────────────
Data acquisition and preprocessing pipeline for PharmaAI.

Stages:
    download     → fetch raw CSV from Kaggle (or use seed)
    preprocess   → parse composition, infer categories, clean text
    validate     → schema and quality checks, reject bad rows
    stats        → print dataset statistics
"""

from data.pipeline.download import DataDownloader
from data.pipeline.preprocess import Preprocessor
from data.pipeline.validate import Validator
from data.pipeline.stats import DataStats

__all__ = ["DataDownloader", "Preprocessor", "Validator", "DataStats"]
