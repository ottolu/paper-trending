from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.api.deps import get_db, get_embedding_client, get_vector_store

router = APIRouter(prefix="/api/search", tags=["search"])


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = Field(10, ge=1, le=100)
    collection: str = "paper_embeddings_v1"


@router.post("/semantic")
async def semantic_search(req: SemanticSearchRequest):
    db = get_db()
    embedding_client = get_embedding_client()
    vector_store = get_vector_store()

    query_embedding = await embedding_client.embed([req.query])
    if not query_embedding:
        return {"results": []}

    results = vector_store.query(
        collection_name=req.collection,
        query_embeddings=query_embedding,
        n_results=req.top_k,
    )

    result_ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]

    items = []
    for pid, dist in zip(result_ids, distances):
        paper = await db.fetch_one(
            "SELECT id, title, abstract FROM papers WHERE id = ?", (pid,)
        )
        if paper:
            items.append({
                "paper_id": paper["id"],
                "title": paper["title"],
                "abstract": paper["abstract"],
                "distance": dist,
            })

    return {"results": items}
