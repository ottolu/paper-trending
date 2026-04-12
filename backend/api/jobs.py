from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_stage_runner

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
        "accepted_at": datetime.utcnow().isoformat(),
    }
