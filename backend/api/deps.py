from __future__ import annotations

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

_db_instance: Database | None = None
_stage_runner_instance: StageRunner | None = None


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
