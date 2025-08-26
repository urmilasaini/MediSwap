---
title: MEDISWAP
emoji: 💊
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Medicine alternative recommendation app.
tags:
  - medicine
  - healthcare
  - fastapi
  - semantic-search
  - qdrant
---

# MediSwap

## Metadata

| Field | Value |
| --- | --- |
| Project name | MediSwap |
| App name | PharmaAI |
| Version | 1.0.0 |
| Type | Medicine alternative recommendation system |
| Backend | FastAPI, Uvicorn |
| Search | RapidFuzz, semantic embeddings |
| Vector store | Qdrant |
| Embedding model | BAAI/bge-small-en-v1.5 |
| Database | SQLite |
| Entry point | `app.py` |
| Default port | `7860` |
| API docs | `http://localhost:7860/api/docs` |

## Overview

MediSwap is a FastAPI-based medicine alternative recommendation app. It supports fuzzy brand-name search and semantic search using sentence-transformer embeddings with Qdrant as the vector store.

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python app.py
```

Open the app at:

```text
http://localhost:7860
```

## Useful URLs

| URL | Purpose |
| --- | --- |
| `http://localhost:7860` | Web app |
| `http://localhost:7860/api/docs` | Swagger API docs |
| `http://localhost:7860/api/redoc` | ReDoc API docs |
| `http://localhost:7860/api/health` | Health check |
| `http://localhost:7860/api/status` | App status |

## Project Structure

```text
api/          API routes
core/         App configuration and database setup
data/         Medicine data, SQLite DB, and Qdrant storage
models/       Pydantic schemas
notebooks/    Exploration notebooks
scripts/      Data ingestion and setup scripts
services/     Search, embeddings, and vector store services
static/       Frontend files
app.py        FastAPI entry point
```

## Environment

Copy `.env.example` to `.env` and update values if needed.

Key settings:

```text
APP_NAME=PharmaAI
APP_VERSION=1.0.0
QDRANT_MODE=local
QDRANT_COLLECTION=medicines
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```
