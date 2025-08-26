# ── Base ──────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System deps for sentence-transformers / torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install Python deps ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source ───────────────────────────────────────────────────────────────
COPY . .

# ── Pre-build: ingest data ────────────────────────────────────────────────────
RUN python scripts/setup.py --source seed --skip-index

# ── (Optional) Pre-build vector index for local Qdrant mode ──────────────────
# Uncomment if you want the index baked into the image.
# RUN python scripts/build_index.py

# ── Expose HF Spaces default port ────────────────────────────────────────────
EXPOSE 7860

# ── Run ───────────────────────────────────────────────────────────────────────
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
