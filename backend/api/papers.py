from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from backend.api.deps import get_db

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("")
async def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    score_min: float | None = Query(None),
    q: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    tag: str | None = Query(None),
    sort: str = Query("updated_at_desc"),
):
    db = get_db()
    conditions = []
    params: list = []

    if score_min is not None:
        conditions.append("ar.score_total >= ?")
        params.append(score_min)
    if q:
        conditions.append("(p.title LIKE ? OR p.abstract LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if date_from:
        conditions.append("p.first_seen_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("p.first_seen_at <= ?")
        params.append(date_to)
    if tag:
        conditions.append("ar.tags LIKE ?")
        params.append(f"%{tag}%")

    where = " AND ".join(conditions) if conditions else "1=1"

    sort_map = {
        "updated_at_desc": "p.updated_at DESC",
        "updated_at_asc": "p.updated_at ASC",
        "score_desc": "ar.score_total DESC",
        "score_asc": "ar.score_total ASC",
        "hf_likes_desc": "(SELECT MAX(hf_likes) FROM paper_sources WHERE paper_id = p.id) DESC",
    }
    order_by = sort_map.get(sort, "p.updated_at DESC")

    count_row = await db.fetch_one(
        f"SELECT COUNT(*) as cnt FROM papers p "
        f"LEFT JOIN paper_analysis pa ON pa.paper_id = p.id "
        f"LEFT JOIN analysis_runs ar ON ar.id = pa.active_analysis_run_id "
        f"WHERE {where}",
        tuple(params),
    )
    total = count_row["cnt"] if count_row else 0

    offset = (page - 1) * page_size
    rows = await db.fetch_all(
        f"SELECT p.id, p.title, p.arxiv_id, p.published_date, p.first_seen_at, "
        f"ar.score_total, ar.tags, ar.analysis_basis, ar.evidence_level, "
        f"(SELECT MAX(hf_likes) FROM paper_sources WHERE paper_id = p.id) AS hf_likes "
        f"FROM papers p "
        f"LEFT JOIN paper_analysis pa ON pa.paper_id = p.id "
        f"LEFT JOIN analysis_runs ar ON ar.id = pa.active_analysis_run_id "
        f"WHERE {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    )

    items = []
    for r in rows:
        tags = []
        if r["tags"]:
            try:
                tags = json.loads(r["tags"])
            except (json.JSONDecodeError, TypeError):
                pass
        items.append({
            "id": r["id"],
            "title": r["title"],
            "arxiv_id": r["arxiv_id"],
            "published_date": r["published_date"],
            "first_seen_at": r["first_seen_at"],
            "score_total": r["score_total"],
            "hf_likes": r["hf_likes"],
            "tags": tags,
            "analysis_basis": r["analysis_basis"],
            "evidence_level": r["evidence_level"],
        })

    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.get("/{paper_id}")
async def get_paper(paper_id: str):
    db = get_db()
    paper = await db.fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper_dict = dict(paper)
    for field in ["authors", "arxiv_categories"]:
        if paper_dict.get(field) and isinstance(paper_dict[field], str):
            try:
                paper_dict[field] = json.loads(paper_dict[field])
            except (json.JSONDecodeError, TypeError):
                pass

    analysis = None
    pa = await db.fetch_one(
        "SELECT * FROM paper_analysis WHERE paper_id = ?", (paper_id,)
    )
    if pa:
        ar = await db.fetch_one(
            "SELECT * FROM analysis_runs WHERE id = ?", (pa["active_analysis_run_id"],)
        )
        if ar:
            ar_dict = dict(ar)
            for field in ["innovation_points", "key_takeaways", "score_breakdown",
                          "tags", "evidence_citations"]:
                if ar_dict.get(field) and isinstance(ar_dict[field], str):
                    try:
                        ar_dict[field] = json.loads(ar_dict[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            analysis = ar_dict

    sources = await db.fetch_all(
        "SELECT * FROM paper_sources WHERE paper_id = ?", (paper_id,)
    )
    sources_list = [dict(s) for s in sources]
    hf_likes_vals = [s.get("hf_likes") for s in sources_list if s.get("hf_likes") is not None]
    hf_likes = max(hf_likes_vals) if hf_likes_vals else None

    return {
        **paper_dict,
        "hf_likes": hf_likes,
        "analysis": analysis,
        "sources": sources_list,
    }
