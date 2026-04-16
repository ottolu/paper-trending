"""Quick test: parse one PDF with marker-pdf (OCR disabled)."""
import asyncio
import os
import sys
import time
from pathlib import Path

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.pdf.parser import PdfParser


async def main():
    db = Database("data/tracker.db")
    await db.initialize()
    sr = StageRunner(db)

    pid = "2604.06628"

    # Fix: clean up stale pdf_parse tasks and attempts for this paper
    stale = await db.fetch_all(
        "SELECT id FROM stage_runs WHERE target_id = ? AND stage = 'pdf_parse'", (pid,)
    )
    for s in stale:
        await db.execute("DELETE FROM stage_run_attempts WHERE stage_run_id = ?", (s["id"],))
        await db.execute("DELETE FROM stage_runs WHERE id = ?", (s["id"],))
    await db.execute(
        "DELETE FROM pdf_extractions WHERE paper_id = ? AND extraction_status != 'succeeded'",
        (pid,),
    )

    pf = await db.fetch_one(
        "SELECT id FROM paper_files WHERE paper_id = ? AND is_current = 1", (pid,)
    )
    print(f"Paper file id: {pf['id']}")

    # Create fresh pdf_parse task
    await sr.create(
        target_type="paper", target_id=pid, stage="pdf_parse",
        payload={"paper_file_id": pf["id"]},
    )

    parser = PdfParser(db=db, stage_runner=sr, paper_root="data/papers")
    t0 = time.time()
    result = await parser.process_next()
    elapsed = time.time() - t0
    print(f"Parse result: {result} in {elapsed:.1f}s")

    ext = await db.fetch_one(
        "SELECT * FROM pdf_extractions WHERE paper_id = ? AND extraction_status = 'succeeded'"
        " ORDER BY id DESC LIMIT 1",
        (pid,),
    )
    if ext:
        md = Path(ext["extracted_markdown_path"]).read_text()
        print(f"\nOK: {ext['page_count']} pages, {len(md)} chars markdown")
        print(f"\nFirst 800 chars:\n{md[:800]}")
    else:
        print("FAILED")
        fail = await db.fetch_one(
            "SELECT last_error FROM stage_runs WHERE target_id=? AND stage='pdf_parse'"
            " AND status='failed' ORDER BY updated_at DESC LIMIT 1",
            (pid,),
        )
        if fail:
            print(f"Error: {fail['last_error'][:500]}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
