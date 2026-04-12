from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from backend.api.deps import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = get_db()

    count_row = await db.fetch_one("SELECT COUNT(*) as cnt FROM weekly_reports")
    total = count_row["cnt"] if count_row else 0

    offset = (page - 1) * page_size
    rows = await db.fetch_all(
        "SELECT id, week_start, week_end, cluster_run_id, is_current, created_at "
        "FROM weekly_reports ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )

    items = [dict(r) for r in rows]
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.get("/{report_id}")
async def get_report(report_id: int):
    db = get_db()
    row = await db.fetch_one("SELECT * FROM weekly_reports WHERE id = ?", (report_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    result = dict(row)
    for field in ["analysis_run_ids_json", "highlights"]:
        if result.get(field) and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result
