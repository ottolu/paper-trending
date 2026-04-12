from __future__ import annotations

import ast
import hashlib
import json
import logging
from pathlib import Path

import httpx

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


class PdfFetcher:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        download_timeout: int = 120,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._timeout = download_timeout

    async def process_next(self, worker_id: str = "pdf-fetcher-1") -> bool:
        task = await self._stage_runner.claim("pdf_fetch", worker_id)
        if not task:
            return False

        try:
            payload_raw = task["payload_json"]
            if not payload_raw:
                payload = {}
            else:
                try:
                    payload = json.loads(payload_raw)
                except (json.JSONDecodeError, ValueError):
                    payload = ast.literal_eval(payload_raw)

            pdf_url = payload.get("pdf_url", "")
            paper_id = task["target_id"]

            if not pdf_url:
                await self._stage_runner.fail(task["id"], "No pdf_url in payload")
                return True

            result = await self.download_and_store(paper_id, pdf_url)

            await self._stage_runner.complete(task["id"])
            await self._stage_runner.create(
                target_type="paper",
                target_id=paper_id,
                stage="pdf_parse",
                payload={"paper_file_id": result["paper_file_id"]},
            )
            return True
        except Exception as e:
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def download_and_store(self, paper_id: str, pdf_url: str) -> dict:
        async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()

        pdf_bytes = response.content
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        file_size = len(pdf_bytes)

        paper_dir = self._paper_root / paper_id / "files" / "versions"
        paper_dir.mkdir(parents=True, exist_ok=True)
        target_path = paper_dir / f"{sha256}.pdf"

        if not target_path.exists():
            target_path.write_bytes(pdf_bytes)

        storage_path = str(target_path)

        existing = await self._db.fetch_one(
            "SELECT id FROM paper_files WHERE paper_id = ? AND sha256 = ?",
            (paper_id, sha256),
        )

        if existing:
            return {
                "paper_file_id": existing["id"],
                "sha256": sha256,
                "file_size": file_size,
            }

        await self._db.execute(
            "UPDATE paper_files SET is_current = 0 WHERE paper_id = ? AND is_current = 1",
            (paper_id,),
        )

        paper_file_id = await self._db.execute(
            "INSERT INTO paper_files (paper_id, file_type, source_url, storage_path, "
            "file_size_bytes, sha256, mime_type, is_current, download_status, "
            "downloaded_at, verified_at) "
            "VALUES (?, 'pdf', ?, ?, ?, ?, 'application/pdf', 1, 'downloaded', "
            "datetime('now'), datetime('now'))",
            (paper_id, pdf_url, storage_path, file_size, sha256),
        )

        return {
            "paper_file_id": paper_file_id,
            "sha256": sha256,
            "file_size": file_size,
        }
