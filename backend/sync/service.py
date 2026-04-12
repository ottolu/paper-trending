from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime
from pathlib import Path

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.sync.daily_summary import generate_daily_summary
from backend.sync.note_generator import generate_paper_note

logger = logging.getLogger(__name__)


def _sanitize_filename(title: str) -> str:
    sanitized = re.sub(r"[^\w\s-]", "", title)
    sanitized = re.sub(r"\s+", "-", sanitized.strip())
    return sanitized[:80] if sanitized else "untitled"


def _iso_week_string(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


class ObsidianSyncService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        vault_path: str,
        root_folder: str = "LLM-Research",
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._vault_path = Path(vault_path)
        self._root_folder = root_folder

    async def process_next(self, worker_id: str = "sync-1") -> bool:
        task = await self._stage_runner.claim("sync", worker_id)
        if not task:
            return False

        try:
            paper_id = task["target_id"]

            paper = await self._db.fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
            if not paper:
                await self._stage_runner.fail(task["id"], f"Paper {paper_id} not found")
                return True

            pa = await self._db.fetch_one(
                "SELECT * FROM paper_analysis WHERE paper_id = ?", (paper_id,)
            )
            if not pa:
                await self._stage_runner.fail(task["id"], f"No analysis for paper {paper_id}")
                return True

            analysis = await self._db.fetch_one(
                "SELECT * FROM analysis_runs WHERE id = ?", (pa["active_analysis_run_id"],)
            )
            if not analysis:
                await self._stage_runner.fail(task["id"], f"Analysis run not found for {paper_id}")
                return True

            source = await self._db.fetch_one(
                "SELECT * FROM paper_sources WHERE paper_id = ? ORDER BY id DESC LIMIT 1",
                (paper_id,),
            )

            # Determine collected date from first_seen_at
            first_seen = paper["first_seen_at"]
            collected_date = datetime.fromisoformat(first_seen).date() if first_seen else date.today()
            week_str = _iso_week_string(collected_date)
            date_str = collected_date.isoformat()

            # Build vault directory
            day_dir = self._vault_path / self._root_folder / week_str / date_str
            day_dir.mkdir(parents=True, exist_ok=True)

            # Generate and write paper note
            note_content = generate_paper_note(
                dict(paper), dict(analysis), dict(source) if source else None
            )
            note_checksum = hashlib.sha256(note_content.encode("utf-8")).hexdigest()

            filename = _sanitize_filename(paper["title"]) + ".md"
            note_path = day_dir / filename

            existing_log = await self._db.fetch_one(
                "SELECT id FROM sync_log WHERE sync_type = 'paper_note' "
                "AND logical_target = ? AND checksum = ?",
                (f"paper:{paper_id}", note_checksum),
            )
            if not existing_log:
                note_path.write_text(note_content, encoding="utf-8")
                await self._db.execute(
                    "INSERT INTO sync_log (paper_id, sync_type, logical_target, "
                    "file_path, checksum, synced_at) "
                    "VALUES (?, 'paper_note', ?, ?, ?, datetime('now'))",
                    (paper_id, f"paper:{paper_id}", str(note_path), note_checksum),
                )

            # Generate and write/update daily summary
            await self._update_daily_summary(collected_date, date_str, day_dir)

            await self._stage_runner.complete(task["id"])
            return True
        except Exception as e:
            logger.exception("Sync failed for task %s", task["id"])
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def _update_daily_summary(
        self, collected_date: date, date_str: str, day_dir: Path
    ) -> None:
        # Get all papers analyzed on this date
        rows = await self._db.fetch_all(
            "SELECT p.title, ar.score_total, ar.tags, ar.factual_summary, "
            "ar.analysis_basis, ar.evidence_level "
            "FROM paper_analysis pa "
            "JOIN papers p ON pa.paper_id = p.id "
            "JOIN analysis_runs ar ON pa.active_analysis_run_id = ar.id "
            "WHERE date(p.first_seen_at) = ?",
            (date_str,),
        )
        papers_data = [dict(r) for r in rows]

        total_collected = await self._db.fetch_one(
            "SELECT COUNT(*) as cnt FROM papers WHERE date(first_seen_at) = ?",
            (date_str,),
        )
        total_analyzed = len(papers_data)

        summary_content = generate_daily_summary(
            date_str,
            papers_data,
            total_collected=total_collected["cnt"] if total_collected else 0,
            total_analyzed=total_analyzed,
        )
        summary_checksum = hashlib.sha256(summary_content.encode("utf-8")).hexdigest()

        summary_path = day_dir / f"{date_str}-daily.md"

        existing_log = await self._db.fetch_one(
            "SELECT id FROM sync_log WHERE sync_type = 'daily_summary' "
            "AND logical_target = ? AND checksum = ?",
            (f"daily:{date_str}", summary_checksum),
        )
        if not existing_log:
            summary_path.write_text(summary_content, encoding="utf-8")
            await self._db.execute(
                "INSERT INTO sync_log (sync_type, logical_target, file_path, "
                "checksum, synced_at) "
                "VALUES ('daily_summary', ?, ?, ?, datetime('now'))",
                (f"daily:{date_str}", str(summary_path), summary_checksum),
            )
