"""Run three PDF parsing modes on a single paper for comparison."""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import pymupdf


PAPER_ID = sys.argv[1] if len(sys.argv) > 1 else "2604.09531"
PROJECT = Path(__file__).resolve().parent.parent
PDF = PROJECT / "data" / "papers" / f"{PAPER_ID}.pdf"
BASE = PROJECT / "data" / "parsing_comparison" / PAPER_ID


def strip_md(md: str) -> str:
    text = md
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def run_pymupdf():
    out = BASE / "pymupdf"
    out.mkdir(parents=True, exist_ok=True)

    print("=== PyMuPDF structured extraction ===")
    t0 = time.time()
    doc = pymupdf.open(str(PDF))

    all_spans = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block["type"] == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span["text"].strip():
                            all_spans.append({
                                "text": span["text"],
                                "size": round(span["size"], 1),
                                "flags": span["flags"],
                                "page": page_num,
                            })

    size_chars: Counter[float] = Counter()
    for s in all_spans:
        size_chars[s["size"]] += len(s["text"])
    body_size = size_chars.most_common(1)[0][0]

    md_lines: list[str] = []
    txt_lines: list[str] = []
    sections: list[dict] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        if page_num > 0:
            md_lines.append("\n---\n")
            txt_lines.append(f"\n{'=' * 60}\n")

        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block["type"] != 0:
                continue
            block_text_parts = []
            block_max_size = 0.0
            block_is_bold = False
            for line in block.get("lines", []):
                line_text = ""
                for span in line.get("spans", []):
                    line_text += span["text"]
                    if span["size"] > block_max_size:
                        block_max_size = round(span["size"], 1)
                    if span["flags"] & (1 << 4):
                        block_is_bold = True
                block_text_parts.append(line_text)

            block_text = " ".join(block_text_parts).strip()
            if not block_text:
                continue

            is_heading = False
            heading_level = 0
            if block_max_size > body_size + 1.5:
                is_heading = True
                heading_level = 1 if block_max_size >= body_size + 6 else 2
            elif block_max_size > body_size + 0.3 and block_is_bold and len(block_text) < 100:
                is_heading = True
                heading_level = 3

            if is_heading:
                prefix = "#" * max(1, heading_level)
                md_lines.append(f"\n{prefix} {block_text}\n")
                txt_lines.append(f"\n{block_text}\n")
                sections.append({
                    "title": block_text,
                    "level": heading_level,
                    "page": page_num,
                    "font_size": block_max_size,
                })
            else:
                md_lines.append(block_text)
                txt_lines.append(block_text)

    num_pages = len(doc)
    doc.close()
    elapsed = time.time() - t0

    md_content = "\n".join(md_lines)
    txt_content = "\n".join(txt_lines)

    (out / "fulltext.md").write_text(md_content, encoding="utf-8")
    (out / "fulltext.txt").write_text(txt_content, encoding="utf-8")
    (out / "sections.json").write_text(
        json.dumps(sections, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "mode": "pymupdf_structured",
                "parse_seconds": round(elapsed, 4),
                "markdown_chars": len(md_content),
                "plaintext_chars": len(txt_content),
                "pages": num_pages,
                "toc_entries": len(sections),
                "body_font_size": body_size,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  Parse: {elapsed:.3f}s | MD: {len(md_content)} chars | Sections: {len(sections)}")
    for s in sections[:8]:
        print(f"    {'#' * s['level']} {s['title'][:60]}")
    if len(sections) > 8:
        print(f"    ... ({len(sections) - 8} more)")


def run_marker(mode: str):
    from marker.config.parser import ConfigParser
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    is_fast = mode == "marker_fast"
    out = BASE / mode
    out.mkdir(parents=True, exist_ok=True)
    label = "force_layout_block=Text" if is_fast else "complete layout detection"

    print(f"=== Marker {mode} ({label}) ===")
    config: dict = {
        "output_format": "markdown",
        "disable_ocr": True,
        "paginate_output": True,
    }
    if is_fast:
        config["force_layout_block"] = "Text"

    t0 = time.time()
    config_parser = ConfigParser(config)
    artifact_dict = create_model_dict()
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=artifact_dict,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    t_load = time.time() - t0

    t1 = time.time()
    rendered = converter(str(PDF))
    t_parse = time.time() - t1

    md = rendered.markdown
    meta = rendered.metadata
    toc = meta.get("table_of_contents", [])
    page_stats = meta.get("page_stats", {})

    (out / "fulltext.md").write_text(md, encoding="utf-8")

    plaintext = strip_md(md)
    (out / "fulltext.txt").write_text(plaintext, encoding="utf-8")

    sections = [
        {
            "title": e.get("title", ""),
            "level": e.get("heading_level") or 1,
            "page": e.get("page_id", 0),
        }
        for e in toc
    ]
    (out / "sections.json").write_text(
        json.dumps(sections, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "mode": f"{mode} ({label})",
                "model_load_seconds": round(t_load, 2),
                "parse_seconds": round(t_parse, 2),
                "markdown_chars": len(md),
                "plaintext_chars": len(plaintext),
                "pages": len(page_stats),
                "toc_entries": len(sections),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  Load: {t_load:.1f}s | Parse: {t_parse:.1f}s | MD: {len(md)} chars | TOC: {len(sections)}")
    for s in sections[:8]:
        print(f"    {'#' * s['level']} {s['title'][:60]}")
    if len(sections) > 8:
        print(f"    ... ({len(sections) - 8} more)")


if __name__ == "__main__":
    if not PDF.exists():
        print(f"PDF not found: {PDF}")
        sys.exit(1)

    print(f"Paper: {PAPER_ID} ({pymupdf.open(str(PDF)).page_count} pages)")
    print(f"Output: {BASE}\n")

    which = sys.argv[2] if len(sys.argv) > 2 else "all"

    if which in ("all", "pymupdf"):
        run_pymupdf()
        print()

    if which in ("all", "marker_fast"):
        run_marker("marker_fast")
        print()

    if which in ("all", "marker_full"):
        run_marker("marker_full")
        print()

    print("Done.")
