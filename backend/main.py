from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.api.deps import get_stage_runner, set_db, set_embedding_client, set_pipeline_runner, set_vector_store
from backend.collectors.service import CollectorService
from backend.config.loader import load_config
from backend.core.database import Database
from backend.core.embedding_client import EmbeddingClient
from backend.core.llm_client import LLMClient
from backend.core.vector_store import VectorStore
from backend.reporter.service import ReporterService
from backend.scheduler.runtime import build_pipeline_runner, build_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB, embedding client, vector store on startup; close on shutdown."""
    load_dotenv()  # load .env into os.environ before resolving ${...} in settings.yaml
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

        llm_client = LLMClient(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            model=config.llm.model,
            enable_thinking=config.llm.enable_thinking,
            thinking_budget=config.llm.thinking_budget,
        )
        stage_runner = get_stage_runner()
        pipeline_runner = build_pipeline_runner(
            db, stage_runner, config, llm_client, embedding_client, vector_store
        )
        set_pipeline_runner(pipeline_runner)

        if os.environ.get("PT_SCHEDULER", "on") == "on":
            collector = CollectorService(
                db, stage_runner,
                arxiv_categories=config.arxiv.categories,
                arxiv_interval=config.arxiv.request_interval_seconds,
            )
            reporter = ReporterService(
                db, stage_runner, llm_client=llm_client, vector_store=vector_store
            )
            scheduler = build_scheduler(
                db, stage_runner, config, pipeline_runner, collector, reporter
            )
            scheduler.start()
            app.state.scheduler = scheduler

    yield

    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)
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
    from backend.api.pipeline import router as pipeline_router

    app.include_router(papers_router)
    app.include_router(reports_router)
    app.include_router(search_router)
    app.include_router(jobs_router)
    app.include_router(pipeline_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
