from __future__ import annotations

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

_db_instance: Database | None = None
_stage_runner_instance: StageRunner | None = None
_embedding_client = None
_vector_store = None


def set_db(db: Database) -> None:
    global _db_instance, _stage_runner_instance
    _db_instance = db
    _stage_runner_instance = StageRunner(db)


def get_db() -> Database:
    assert _db_instance is not None, "Database not initialized"
    return _db_instance


def get_stage_runner() -> StageRunner:
    assert _stage_runner_instance is not None, "StageRunner not initialized"
    return _stage_runner_instance


def set_embedding_client(client) -> None:
    global _embedding_client
    _embedding_client = client


def get_embedding_client():
    assert _embedding_client is not None, "EmbeddingClient not initialized"
    return _embedding_client


def set_vector_store(store) -> None:
    global _vector_store
    _vector_store = store


def get_vector_store():
    assert _vector_store is not None, "VectorStore not initialized"
    return _vector_store
