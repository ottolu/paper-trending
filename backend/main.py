from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.api.deps import set_db, set_embedding_client, set_vector_store
from backend.config.loader import load_config
from backend.core.database import Database
from backend.core.embedding_client import EmbeddingClient
from backend.core.vector_store import VectorStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, embedding client, vector store on startup; close on shutdown."""
    config_path = os.environ.get("SETTINGS_PATH", "settings.yaml")
    if Path(config_path).exists():
        config = load_config(config_path)

        db = Database(str(Path(config.storage.data_root) / "tracker.db"))
        await db.initialize()
        set_db(db)

        embedding_client = EmbeddingClient(
            base_url=config.embedding.base_url,
            api_key=config.embedding.api_key,
            model=config.embedding.model,
        )
        set_embedding_client(embedding_client)

        vector_store = VectorStore(
            persist_directory=str(Path(config.storage.data_root) / "chromadb")
        )
        set_vector_store(vector_store)

        app.state.db = db
        app.state.config = config

    yield

    if hasattr(app.state, "db"):
        await app.state.db.close()


def create_app(db: Database | None = None) -> FastAPI:
    """Create FastAPI app. Pass db= for testing; omit for production (uses lifespan)."""
    use_lifespan = db is None
    app = FastAPI(
        title="LLM Paper Tracker",
        version="0.1.0",
        lifespan=lifespan if use_lifespan else None,
    )

    if db is not None:
        set_db(db)

    from backend.api.papers import router as papers_router
    from backend.api.reports import router as reports_router
    from backend.api.search import router as search_router
    from backend.api.jobs import router as jobs_router

    app.include_router(papers_router)
    app.include_router(reports_router)
    app.include_router(search_router)
    app.include_router(jobs_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
