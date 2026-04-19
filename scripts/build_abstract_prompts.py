"""Build abstract-only prompts for the 20 eval papers."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT / "tests" / "fixtures"
INDEX_PATH = FIXTURES / "eval_paper_fulltext_index.json"
METADATA_PATH = FIXTURES / "hf_daily_papers_latest_week.json"


def main():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    all_meta = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    meta_by_id = {m["arxiv_id"]: m for m in all_meta}

    new_index = []
    for item in sorted(index, key=lambda x: x["idx"]):
        idx = item["idx"]
        arxiv_id = item["arxiv_id"]
        meta = meta_by_id.get(arxiv_id, {})
        title = meta.get("title", item["title"])
        abstract = meta.get("abstract", "")
        authors = meta.get("authors", "")
        if isinstance(authors, list):
            authors_str = ", ".join(authors)
        else:
            authors_str = str(authors)

        prompt = "\n".join([
            f"# Paper: {title}",
            f"Authors: {authors_str}",
            "Analysis basis: abstract_only",
            "",
            "## Abstract",
            abstract.strip(),
            "",
        ])
        path = FIXTURES / f"eval_paper_abstract_{idx}.txt"
        path.write_text(prompt, encoding="utf-8")
        new_index.append({
            "idx": idx,
            "arxiv_id": arxiv_id,
            "title": title,
            "hf_likes": item.get("hf_likes", 0),
            "pages": item.get("pages", 0),
            "prompt_chars": len(prompt),
            "prompt_file": str(path.relative_to(PROJECT)),
        })
        print(f"[{idx:02d}] {arxiv_id}: {len(prompt):,} chars")

    (FIXTURES / "eval_paper_abstract_index.json").write_text(
        json.dumps(new_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(p["prompt_chars"] for p in new_index)
    print(f"\n[OK] {len(new_index)} abstract prompts, {total:,} total chars")


if __name__ == "__main__":
    main()
