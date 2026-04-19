"""Batch PyMuPDF extraction for 20 eval papers + build new fulltext prompts (no truncation).

Outputs:
  data/parsing_fulltext/{arxiv_id}/fulltext.md
  data/parsing_fulltext/{arxiv_id}/fulltext.txt
  data/parsing_fulltext/{arxiv_id}/sections.json
  data/parsing_fulltext/{arxiv_id}/metadata.json
  tests/fixtures/eval_paper_fulltext_{idx}.txt  (complete prompt)
  tests/fixtures/eval_paper_fulltext_index.json
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import pymupdf

PROJECT = Path(__file__).resolve().parent.parent
PAPER_DIR = PROJECT / "data" / "papers"
OUT_DIR = PROJECT / "data" / "parsing_fulltext"
FIXTURES = PROJECT / "tests" / "fixtures"
INDEX_PATH = FIXTURES / "eval_paper_index.json"
METADATA_PATH = FIXTURES / "hf_daily_papers_latest_week.json"


def extract_pdf(pdf_path: Path) -> dict:
    doc = pymupdf.open(str(pdf_path))

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
                txt_lines.append(f"\n{btext}\n")
                sections.append({
                    "title": btext,
                    "level": level,
                    "page": page_num,
                    "font_size": block_max_size,
                })
            else:
                md_lines.append(btext)
                txt_lines.append(btext)

    num_pages = len(doc)
    doc.close()

    return {
        "markdown": "\n".join(md_lines),
        "plaintext": "\n".join(txt_lines),
        "sections": sections,
        "num_pages": num_pages,
        "body_font_size": body_size,
    }


def build_prompt(meta: dict, plaintext: str) -> str:
    title = meta.get("title", "")
    abstract = meta.get("abstract", "")
    authors_raw = meta.get("authors", "")
    if isinstance(authors_raw, list):
        authors_str = ", ".join(authors_raw)
    else:
        authors_str = str(authors_raw)

    parts = [
        f"# Paper: {title}",
        f"Authors: {authors_str}",
        "Analysis basis: full_text",
        "",
        "## Abstract",
        abstract.strip(),
        "",
        "## Full Text",
        plaintext.strip(),
        "",
    ]
    return "\n".join(parts)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    all_meta = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    meta_by_id = {m["arxiv_id"]: m for m in all_meta}

    new_index = []

    for item in sorted(index, key=lambda x: x["idx"]):
        idx = item["idx"]
        arxiv_id = item["arxiv_id"]
        pdf_path = PAPER_DIR / f"{arxiv_id}.pdf"
        out_dir = OUT_DIR / arxiv_id
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{idx:02d}] {arxiv_id} ... ", end="", flush=True)
        t0 = time.time()
        result = extract_pdf(pdf_path)
        elapsed = time.time() - t0

        (out_dir / "fulltext.md").write_text(result["markdown"], encoding="utf-8")
        (out_dir / "fulltext.txt").write_text(result["plaintext"], encoding="utf-8")
        (out_dir / "sections.json").write_text(
            json.dumps(result["sections"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / "metadata.json").write_text(
            json.dumps({
                "mode": "pymupdf_structured",
                "parse_seconds": round(elapsed, 3),
                "markdown_chars": len(result["markdown"]),
                "plaintext_chars": len(result["plaintext"]),
                "pages": result["num_pages"],
                "sections": len(result["sections"]),
                "body_font_size": result["body_font_size"],
            }, ensure_ascii=False, indent=2), encoding="utf-8",
        )

        meta = meta_by_id.get(arxiv_id, {})
        prompt = build_prompt(meta, result["plaintext"])
        prompt_path = FIXTURES / f"eval_paper_fulltext_{idx}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")

        print(f"{result['num_pages']}p, {elapsed:.2f}s, prompt={len(prompt):,} chars, sections={len(result['sections'])}")

        new_index.append({
            "idx": idx,
            "arxiv_id": arxiv_id,
            "title": item["title"],
            "hf_likes": item.get("hf_likes", 0),
            "pages": result["num_pages"],
            "prompt_chars": len(prompt),
            "sections": len(result["sections"]),
            "prompt_file": str(prompt_path.relative_to(PROJECT)),
            "parsed_dir": str(out_dir.relative_to(PROJECT)),
        })

    index_path = FIXTURES / "eval_paper_fulltext_index.json"
    index_path.write_text(json.dumps(new_index, ensure_ascii=False, indent=2), encoding="utf-8")

    total_chars = sum(p["prompt_chars"] for p in new_index)
    total_pages = sum(p["pages"] for p in new_index)
    print(f"\n[OK] {len(new_index)} papers parsed: {total_pages} pages, {total_chars:,} total prompt chars")
    print(f"     Index: {index_path.relative_to(PROJECT)}")


if __name__ == "__main__":
    main()
