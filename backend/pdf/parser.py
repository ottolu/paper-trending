from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
import tempfile
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
        parser_name: str = "marker",
        parser_version: str = "v1",
    ):
        self._db = db
        self._stage_runner = stage_runner
        self._paper_root = Path(paper_root)
        self._parser_name = parser_name
        self._parser_version = parser_version
        self._converter = None

    def _get_converter(self):
        """Lazy-load marker converter (expensive, do once)."""
        if self._converter is None:
            from marker.config.parser import ConfigParser
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict

            logger.info("Loading marker-pdf models (first call, may take a moment)...")
            config = {
                "output_format": "markdown",
                "disable_ocr": True,  # arXiv PDFs are native digital, skip OCR
                "paginate_output": True,
            }
            config_parser = ConfigParser(config)
            self._converter = PdfConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=create_model_dict(),
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
            )
            logger.info("Marker-pdf models loaded (OCR disabled for native PDFs).")
        return self._converter

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
            logger.error("PDF parse failed for %s: %s", task["target_id"], e)
            await self._stage_runner.fail(task["id"], str(e))
            return True

    async def parse(self, paper_id: str, paper_file_id: int) -> dict:
        paper_file = await self._db.fetch_one(
            "SELECT * FROM paper_files WHERE id = ?", (paper_file_id,)
        )
        if not paper_file:
            raise ValueError(f"paper_file {paper_file_id} not found")

        pdf_path = Path(paper_file["storage_path"])

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

        # Run marker-pdf in a thread (CPU-intensive sync operation)
        markdown, sections, page_count = await asyncio.to_thread(
            self._run_marker, str(pdf_path)
        )

        # Derive plain text from markdown (strip formatting)
        fulltext = self._markdown_to_text(markdown)
        blocks = self._extract_blocks_from_markdown(markdown)

        text_path = extraction_dir / "fulltext.txt"
        md_path = extraction_dir / "fulltext.md"
        blocks_path = extraction_dir / "blocks.json"
        sections_path = extraction_dir / "sections.json"

        text_path.write_text(fulltext, encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        blocks_path.write_text(json.dumps(blocks, ensure_ascii=False), encoding="utf-8")
        sections_path.write_text(json.dumps(sections, ensure_ascii=False), encoding="utf-8")

        await self._db.execute(
            "UPDATE pdf_extractions SET extraction_status = 'succeeded', "
            "page_count = ?, extraction_root_path = ?, extracted_text_path = ?, "
            "extracted_markdown_path = ?, blocks_json_path = ?, "
            "sections_json_path = ? WHERE id = ?",
            (
                page_count,
                str(extraction_dir),
                str(text_path),
                str(md_path),
                str(blocks_path),
                str(sections_path),
                extraction_id,
            ),
        )

        logger.info(
            "Parsed %s: %d pages, %d chars markdown, %d sections",
            paper_id, page_count, len(markdown), len(sections),
        )

        return {
            "extraction_id": extraction_id,
            "extraction_root_path": str(extraction_dir),
        }

    def _run_marker(self, pdf_path: str) -> tuple[str, list[dict], int]:
        """Run marker-pdf conversion (sync, call from thread)."""
        converter = self._get_converter()
        rendered = converter(pdf_path)

        markdown = rendered.markdown
        metadata = rendered.metadata

        # Extract sections from table_of_contents
        sections = []
        toc = metadata.get("table_of_contents", [])
        for entry in toc:
            sections.append({
                "title": entry.get("title", ""),
                "level": entry.get("heading_level", 1),
                "page": entry.get("page_id", 0),
            })

        # Count pages from metadata
        page_stats = metadata.get("page_stats", {})
        page_count = len(page_stats) if page_stats else 0

        return markdown, sections, page_count

    def _markdown_to_text(self, markdown: str) -> str:
        """Strip markdown formatting to get plain text."""
        text = markdown
        # Remove image references
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        # Remove links but keep text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Remove heading markers
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Remove bold/italic
        text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
        # Remove horizontal rules
        text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _extract_blocks_from_markdown(self, markdown: str) -> list[dict]:
        """Extract structured blocks from markdown."""
        blocks = []
        current_section = ""
        for line in markdown.split("\n"):
            heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
            if heading_match:
                current_section = heading_match.group(2)
                blocks.append({
                    "type": "heading",
                    "level": len(heading_match.group(1)),
                    "content": current_section,
                })
            elif line.startswith("|") and "|" in line[1:]:
                # Table row
                if not blocks or blocks[-1]["type"] != "table":
                    blocks.append({
                        "type": "table",
                        "section": current_section,
                        "content": line + "\n",
                    })
                else:
                    blocks[-1]["content"] += line + "\n"
            elif line.strip():
                if not blocks or blocks[-1]["type"] != "text":
                    blocks.append({
                        "type": "text",
                        "section": current_section,
                        "content": line + "\n",
                    })
                else:
                    blocks[-1]["content"] += line + "\n"
        return blocks
