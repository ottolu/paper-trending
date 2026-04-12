from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.processor.chunker import chunk_text

logger = logging.getLogger(__name__)


class ProcessorService:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        max_chunk_chars: int = 4000,
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._max_chunk_chars = max_chunk_chars

    async def process_next(self, worker_id: str = "processor-1") -> bool:
        task = await self._stage_runner.claim("processor", worker_id)
        if not task:
            return False

        try:
            paper_id = task["target_id"]
            manifest = await self._build_manifest(paper_id)

            manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
            manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()

            cache_dir = self._paper_root / paper_id / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = cache_dir / f"{manifest_hash}.json"
            manifest_path.write_text(manifest_json, encoding="utf-8")

            await self._stage_runner.complete(task["id"])
            await self._stage_runner.create(
                target_type="paper",
                target_id=paper_id,
                stage="analyzer",
                payload={
                    "chunk_manifest_path": str(manifest_path),
                    "chunk_manifest_hash": manifest_hash,
                    "analysis_basis": manifest["analysis_basis"],
                },
            )
            return True
        except Exception as e:
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def _build_manifest(self, paper_id: str) -> dict:
        paper = await self._db.fetch_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
        if not paper:
            raise ValueError(f"Paper {paper_id} not found")

        authors = json.loads(paper["authors"]) if paper["authors"] else []
        categories = json.loads(paper["arxiv_categories"]) if paper["arxiv_categories"] else []

        extraction = await self._db.fetch_one(
            "SELECT * FROM pdf_extractions WHERE paper_id = ? AND extraction_status = 'succeeded' "
            "ORDER BY id DESC LIMIT 1",
            (paper_id,),
        )

        analysis_basis = "abstract_only"
        chunks = []
        sections = []

        if extraction and extraction["extracted_text_path"]:
            text_path = Path(extraction["extracted_text_path"])
            if text_path.exists():
                full_text = text_path.read_text(encoding="utf-8")
                chunks = chunk_text(full_text, max_chars=self._max_chunk_chars, return_with_metadata=True)
                analysis_basis = "full_text"

            if extraction["sections_json_path"]:
                sections_path = Path(extraction["sections_json_path"])
                if sections_path.exists():
                    sections = json.loads(sections_path.read_text(encoding="utf-8"))

        return {
            "paper_id": paper_id,
            "title": paper["title"],
            "abstract": paper["abstract"],
            "authors": authors,
            "arxiv_categories": categories,
            "published_date": paper["published_date"],
            "analysis_basis": analysis_basis,
            "chunks": chunks,
            "sections": sections,
        }
