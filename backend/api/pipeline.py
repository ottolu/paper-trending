from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import get_pipeline_runner

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/status")
async def pipeline_status() -> dict:
    runner = get_pipeline_runner()
    counts = await runner.get_pending_counts()
    return {"pending": counts, "total_pending": sum(counts.values())}
