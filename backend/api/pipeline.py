from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from backend.api.deps import get_collector, get_pipeline_runner

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/status")
async def pipeline_status() -> dict:
    runner = get_pipeline_runner()
    counts = await runner.get_pending_counts()
    return {"pending": counts, "total_pending": sum(counts.values())}


@router.post("/tick", status_code=202)
async def trigger_tick(background_tasks: BackgroundTasks) -> dict:
    runner = get_pipeline_runner()
    background_tasks.add_task(runner.tick)
    return {"status": "accepted", "note": "draining in background; poll /api/pipeline/status"}


class CollectRequest(BaseModel):
    target_date: date | None = None
    top: int = 15


@router.post("/collect")
async def trigger_collect(req: CollectRequest) -> dict:
    collector = get_collector()
    return await collector.collect_hf_daily(target_date=req.target_date, top=req.top)
