from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_stage_runner
from backend.scheduler.pipeline import STAGE_ORDER

router = APIRouter(tags=["jobs"])


class RetryRequest(BaseModel):
    stage_run_id: int
    reason: str = ""


@router.post("/api/stages/retry")
async def retry_stage(req: RetryRequest):
    stage_runner = get_stage_runner()
    try:
        await stage_runner.retry(req.stage_run_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "accepted",
        "stage_run_id": req.stage_run_id,
        "accepted_at": datetime.now(UTC).isoformat(),
    }


class RetryFailedRequest(BaseModel):
    stage: str


@router.post("/api/stages/retry-failed")
async def retry_failed_stage(req: RetryFailedRequest):
    if req.stage not in STAGE_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {req.stage}")
    stage_runner = get_stage_runner()
    count = await stage_runner.retry_failed(req.stage)
    return {
        "status": "accepted",
        "stage": req.stage,
        "reset": count,
        "accepted_at": datetime.now(UTC).isoformat(),
    }
