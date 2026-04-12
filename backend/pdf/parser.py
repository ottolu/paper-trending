from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


class PdfParser:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        parser_name: str = "stub",
        parser_version: str = "v0.1",
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._parser_name = parser_name
        self._parser_version = parser_version

    async def process_next(self, worker_id: str = "pdf-parser-1") -> bool:
        task = await self._stage_runner.claim("pdf_parse", worker_id)
        if not task:
            return False

        try:
            payload_str = task["payload_json"]
            if payload_str:
                try:
                    payload = json.loads(payload_str)
                except (json.JSONDecodeError, TypeError):
                    payload = ast.literal_eval(payload_str)
            else:
                payload = {}

            paper_file_id = payload.get("paper_file_id")
            paper_id = task["target_id"]

            if not paper_file_id:
                await self._stage_runner.fail(task["id"], "No paper_file_id in payload")
                return True

            await self.parse(paper_id=paper_id, paper_file_id=paper_file_id)

            await self._stage_runner.complete(task["id"])
            await self._stage_runner.create(
                target_type="paper",
                target_id=paper_id,
                stage="processor",
            )
            return True
        except Exception as e:
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def parse(self, paper_id: str, paper_file_id: int) -> dict:
        paper_file = await self._db.fetch_one(
            "SELECT * FROM paper_files WHERE id = ?", (paper_file_id,)
        )
        if not paper_file:
            raise ValueError(f"paper_file {paper_file_id} not found")

        pdf_path = Path(paper_file["storage_path"])
        pdf_bytes = pdf_path.read_bytes()

        extraction_id = await self._db.execute(
            "INSERT INTO pdf_extractions (paper_id, paper_file_id, parser_name, "
            "parser_version, extraction_status, extracted_at) "
            "VALUES (?, ?, ?, ?, 'pending', datetime('now'))",
            (paper_id, paper_file_id, self._parser_name, self._parser_version),
        )

        extraction_dir = (
            self._paper_root / paper_id / "extracted" / str(extraction_id)
        )
        extraction_dir.mkdir(parents=True, exist_ok=True)

        fulltext = self._extract_text(pdf_bytes)
        markdown = self._extract_markdown(pdf_bytes)
        blocks = self._extract_blocks(pdf_bytes)
        sections = self._extract_sections(pdf_bytes)

        text_path = extraction_dir / "fulltext.txt"
        md_path = extraction_dir / "fulltext.md"
        blocks_path = extraction_dir / "blocks.json"
        sections_path = extraction_dir / "sections.json"

        text_path.write_text(fulltext, encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        blocks_path.write_text(json.dumps(blocks), encoding="utf-8")
        sections_path.write_text(json.dumps(sections), encoding="utf-8")

        await self._db.execute(
            "UPDATE pdf_extractions SET extraction_status = 'succeeded', "
            "extraction_root_path = ?, extracted_text_path = ?, "
            "extracted_markdown_path = ?, blocks_json_path = ?, "
            "sections_json_path = ? WHERE id = ?",
            (
                str(extraction_dir),
                str(text_path),
                str(md_path),
                str(blocks_path),
                str(sections_path),
                extraction_id,
            ),
        )

        return {
            "extraction_id": extraction_id,
            "extraction_root_path": str(extraction_dir),
        }

    def _extract_text(self, pdf_bytes: bytes) -> str:
        return f"[stub] Extracted text from {len(pdf_bytes)} bytes"

    def _extract_markdown(self, pdf_bytes: bytes) -> str:
        return f"# Extracted Document\n\n[stub] Markdown from {len(pdf_bytes)} bytes"

    def _extract_blocks(self, pdf_bytes: bytes) -> list[dict]:
        return [{"page": 1, "type": "text", "content": f"[stub] block from {len(pdf_bytes)} bytes"}]

    def _extract_sections(self, pdf_bytes: bytes) -> list[dict]:
        return [{"title": "Introduction", "level": 1, "page": 1}]
