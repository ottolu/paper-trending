"""Benchmark the pdf_parse stage (pymupdf) over all pending pdf_parse tasks.

Times each PdfParser.process_next() call and reports throughput + page stats.
Local-only (no LLM/embedding), so it's safe to run without API keys.
"""
from __future__ import annotations

import asyncio
import statistics
import time

from backend.core.database import Database
from backend.core.stage_runner import StageRunner
from backend.pdf.parser import PdfParser

DB = "data/tracker.db"
ROOT = "data/papers"


async def main() -> None:
    db = Database(DB)
    await db.initialize()
    sr = StageRunner(db)
    parser = PdfParser(
        db=db, stage_runner=sr, paper_root=ROOT, parser_name="pymupdf", parser_version="v1"
    )

    pending = await sr.list_by_status("pdf_parse", "pending", limit=10000)
    n = len(pending)
    print(f"pending pdf_parse tasks: {n}")

    times: list[float] = []
    t0 = time.time()
    while True:
        s = time.time()
        ok = await parser.process_next("bench-parser")
        if not ok:
            break
        times.append(time.time() - s)
        if len(times) % 20 == 0:
            print(f"  {len(times)}/{n}  ({time.time() - t0:.1f}s elapsed)")
    total = time.time() - t0

    succ = await db.fetch_one(
        "SELECT COUNT(*) c, COALESCE(SUM(page_count),0) p, COALESCE(AVG(page_count),0) ap "
        "FROM pdf_extractions WHERE extraction_status='succeeded'"
    )
    failed = await db.fetch_all(
        "SELECT target_id, last_error FROM stage_runs WHERE stage='pdf_parse' AND status='failed'"
    )

    print("=" * 56)
    if times:
        st = sorted(times)
        p90 = st[int(len(st) * 0.9) - 1]
        print(
            f"parsed {len(times)} files in {total:.1f}s | "
            f"avg {statistics.mean(times) * 1000:.0f}ms  median {statistics.median(times) * 1000:.0f}ms  "
            f"p90 {p90 * 1000:.0f}ms  max {max(times) * 1000:.0f}ms"
        )
        print(
            f"throughput: {len(times) / total:.1f} papers/s  "
            f"({succ['p'] / max(total, 1e-9):.0f} pages/s)"
        )
    print(
        f"extractions succeeded={succ['c']}  total_pages={succ['p']}  avg_pages/paper={succ['ap']:.1f}"
    )
    print(f"failed={len(failed)}")
    for f in failed[:10]:
        print("  FAIL", f["target_id"], "->", (f["last_error"] or "")[:90])
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
