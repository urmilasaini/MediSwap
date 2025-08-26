import sqlite3
from pathlib import Path

from core.config import settings


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS medicines (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_name            TEXT    NOT NULL,
                composition           TEXT    NOT NULL,
                salt_name             TEXT    NOT NULL,
                manufacturer          TEXT    NOT NULL,
                strength              TEXT    NOT NULL,
                category              TEXT    NOT NULL,
                description           TEXT    DEFAULT '',
                uses                  TEXT    DEFAULT '',
                side_effects          TEXT    DEFAULT '',
                image_url             TEXT    DEFAULT '',
                excellent_review_pct  REAL    DEFAULT 0.0,
                average_review_pct    REAL    DEFAULT 0.0,
                poor_review_pct       REAL    DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_composition ON medicines(composition);
            CREATE INDEX IF NOT EXISTS idx_salt        ON medicines(salt_name);
            CREATE INDEX IF NOT EXISTS idx_category    ON medicines(category);
            CREATE INDEX IF NOT EXISTS idx_brand       ON medicines(brand_name);
        """)
        conn.commit()
        _migrate(conn)
    print(f"[DB] Ready → {settings.DB_PATH}")


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the initial schema — safe to run on existing DBs."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(medicines)")}

    new_columns = {
        "uses":                 "TEXT DEFAULT ''",
        "side_effects":         "TEXT DEFAULT ''",
        "image_url":            "TEXT DEFAULT ''",
        "excellent_review_pct": "REAL DEFAULT 0.0",
        "average_review_pct":   "REAL DEFAULT 0.0",
        "poor_review_pct":      "REAL DEFAULT 0.0",
    }

    added = []
    for col, definition in new_columns.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE medicines ADD COLUMN {col} {definition}")
            added.append(col)

    if added:
        conn.commit()
        print(f"[DB] Migrated — added columns: {added}")
