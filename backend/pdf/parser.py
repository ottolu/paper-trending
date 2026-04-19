from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
from collections import Counter
from pathlib import Path

from backend.core.database import Database
from backend.core.stage_runner import StageRunner

logger = logging.getLogger(__name__)


def _patch_surya_mps():
    """Patch surya MPS bugs: .item() and .max() on MPS return garbage for certain tensors.

    See: https://github.com/datalab-to/marker/issues/993
    Patches source files directly (survives module reload, needs re-patch after pip upgrade).
    """
    import torch
    if not torch.backends.mps.is_available():
        return

    patches = [
        # encoder: seq_lengths.max().item() crashes on MPS
        (
            "surya.common.surya.encoder",
            "seq_lengths.max().item()",
            "seq_lengths.cpu().max().item()",
        ),
        # __init__: grid_thw product .max().item() crashes on MPS
        (
            "surya.common.surya",
            "(grid_thw[:, 0] * grid_thw[:, 1] * grid_thw[:, 2]).max().item()",
            "(grid_thw[:, 0] * grid_thw[:, 1] * grid_thw[:, 2]).cpu().max().item()",
        ),
        # __init__: grid element .item() in loop
        (
            "surya.common.surya",
            "(grid_thw[i][0] * grid_thw[i][1] * grid_thw[i][2]).item()",
            "(grid_thw[i][0] * grid_thw[i][1] * grid_thw[i][2]).cpu().item()",
        ),
        # __init__: torch.sum in f-string triggers __format__ -> .item() on MPS
        (
            "surya.common.surya",
            "n_image_tokens = torch.sum((input_ids == self.config.image_token_id))",
            "n_image_tokens = torch.sum((input_ids == self.config.image_token_id)).cpu()",
        ),
    ]

    applied = 0
    for module_name, old, new in patches:
        try:
            mod = __import__(module_name, fromlist=[""])
            src_file = mod.__file__
            if not src_file:
                continue
            src = Path(src_file).read_text(encoding="utf-8")
            if old in src and new not in src:
                src = src.replace(old, new)
                Path(src_file).write_text(src, encoding="utf-8")
                applied += 1
        except Exception as e:
            logger.warning("Failed to patch %s: %s", module_name, e)

    if applied:
        logger.info("Applied %d surya MPS patches", applied)


SUPPORTED_PARSERS = {"pymupdf", "marker"}


class PdfParser:
    def __init__(
        self,
        db: Database,
        stage_runner: StageRunner,
        paper_root: str,
        parser_name: str = "pymupdf",
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
            _patch_surya_mps()

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

        # Dispatch to parser backend (both sync, run in thread).
        if self._parser_name == "pymupdf":
            markdown, sections, page_count = await asyncio.to_thread(
                self._run_pymupdf, str(pdf_path)
            )
        elif self._parser_name == "marker":
            markdown, sections, page_count = await asyncio.to_thread(
                self._run_marker, str(pdf_path)
            )
        else:
            raise ValueError(
                f"Unsupported parser_name: {self._parser_name!r}. "
                f"Expected one of {SUPPORTED_PARSERS}."
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

    def _run_pymupdf(self, pdf_path: str) -> tuple[str, list[dict], int]:
        """Extract full text + heading structure via PyMuPDF + font-size heuristic.

        Fast path for native digital PDFs (arXiv). ~0.5s for a 25-page paper vs
        ~4 min for marker-pdf full layout detection. See dev-note for tradeoffs.
        """
        import pymupdf

        doc = pymupdf.open(pdf_path)

        size_chars: Counter[float] = Counter()
        for page_num in range(len(doc)):
            text_dict = doc[page_num].get_text("dict")
            for block in text_dict.get("blocks", []):
                if block["type"] != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span["text"].strip():
                            size_chars[round(span["size"], 1)] += len(span["text"])
        body_size = size_chars.most_common(1)[0][0] if size_chars else 10.0

        md_lines: list[str] = []
        sections: list[dict] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            if page_num > 0:
                md_lines.append("\n---\n")

            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block["type"] != 0:
                    continue
                parts = []
                block_max_size = 0.0
                block_bold = False
                for line in block.get("lines", []):
                    ltext = ""
                    for span in line.get("spans", []):
                        ltext += span["text"]
                        if span["size"] > block_max_size:
                            block_max_size = round(span["size"], 1)
                        if span["flags"] & (1 << 4):
                            block_bold = True
                    parts.append(ltext)
                btext = " ".join(parts).strip()
                if not btext:
                    continue

                is_heading = False
                level = 0
                if block_max_size > body_size + 1.5:
                    is_heading = True
                    level = 1 if block_max_size >= body_size + 6 else 2
                elif block_max_size > body_size + 0.3 and block_bold and len(btext) < 100:
                    is_heading = True
                    level = 3

                if is_heading:
                    prefix = "#" * max(1, level)
                    md_lines.append(f"\n{prefix} {btext}\n")
                    sections.append({
                        "title": btext,
                        "level": level,
                        "page": page_num,
                    })
                else:
                    md_lines.append(btext)

        page_count = len(doc)
        doc.close()
        markdown = "\n".join(md_lines)
        return markdown, sections, page_count

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
