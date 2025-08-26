from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "PharmaAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, validation_alias="APP_DEBUG")

    # ── Database ──────────────────────────────────────────────────────────────
    DB_PATH: str = str(BASE_DIR / "data" / "medicines.db")
    DATA_CSV: str = str(BASE_DIR / "data" / "medicines.csv")

    # ── Qdrant ────────────────────────────────────────────────────────────────
    # QDRANT_MODE: "memory" | "local" | "remote"
    # memory  → in-process, rebuilt every restart (good for dev/HF Spaces)
    # local   → file-backed at QDRANT_PATH, persists across restarts
    # remote  → connects to running Qdrant server at QDRANT_URL
    QDRANT_MODE: str = "local"
    QDRANT_PATH: str = str(BASE_DIR / "data" / "qdrant")
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "medicines"

    # ── Embeddings ────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384

    # ── Search ────────────────────────────────────────────────────────────────
    FUZZY_THRESHOLD: int = 65
    FUZZY_LIMIT: int = 10
    SEMANTIC_LIMIT: int = 6
    ALTERNATIVES_LIMIT: int = 10


settings = Settings()
