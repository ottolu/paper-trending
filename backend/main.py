from __future__ import annotations

from fastapi import FastAPI

from backend.api.deps import set_db
from backend.core.database import Database


def create_app(db: Database | None = None) -> FastAPI:
    app = FastAPI(title="LLM Paper Tracker", version="0.1.0")

    if db is not None:
        set_db(db)

    from backend.api.papers import router as papers_router
    app.include_router(papers_router)

    from backend.api.reports import router as reports_router
    app.include_router(reports_router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
