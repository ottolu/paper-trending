"""PDF-parser bake-off harness (M2 real-numbers benchmark).

Compares PDF parsing options for the "parse paper -> feed a big LLM for deep
reading" pipeline. See docs/dev-notes/2026-06-01-pdf-parsing-options-research.md.

Outputs (all gitignored under data/parser_bench/):
    papers.json            selected sample: id, upvotes, title, keywords, n_pages, html_*
    pdfs/<id>.pdf          downloaded once, shared by every parser
    outputs/<parser>/<id>.(md|json|html)
    metrics/<parser>.json  per-paper {seconds, output_chars, n_math, n_table, n_image, ok, error}
                           + _meta {peak_rss_mb, total_seconds, parser, n_ok}
    RESULTS.md             regenerated table across ALL parsers that have a metrics file

Design notes:
- Each parser runs in its OWN subprocess (`_run`) so we can capture a clean
  per-parser peak RSS via resource.getrusage. The wall time per paper is timed
  inside the subprocess with perf_counter.
- `report` globs metrics/*.json, so MinerU/marker added later auto-appear with
  no code change. The Opus-4.8 fidelity judge is a separate later step.
- Fidelity columns here (n_math/n_table/n_image) are CHEAP STRUCTURAL PROXIES,
  not the authoritative quality signal -- that is the later LLM judge.

Usage:
    .venv/bin/python scripts/parser_bench.py select          # pick 20 papers
    .venv/bin/python scripts/parser_bench.py fetch           # download pdfs + probe html
    .venv/bin/python scripts/parser_bench.py bench --parsers pymupdf,pymupdf4llm,docling,arxiv_html
    .venv/bin/python scripts/parser_bench.py report
    # later (slow batch / different venv):
    .venv/bin/python scripts/parser_bench.py bench --parsers marker
"""
from __future__ import annotations

import argparse
import json
import re
import resource
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "data" / "parser_bench"
PDFS = BENCH / "pdfs"
OUT = BENCH / "outputs"
MET = BENCH / "metrics"
HTML = BENCH / "html"
PAPERS_JSON = BENCH / "papers.json"

UA = {"User-Agent": "Mozilla/5.0 (paper-trending parser-bench)"}
HF_WEEKLY = "https://huggingface.co/api/daily_papers?week={week}"
ARXIV_PDF = "https://arxiv.org/pdf/{id}"
ARXIV_HTML = "https://arxiv.org/html/{id}"
AR5IV_HTML = "https://ar5iv.labs.arxiv.org/html/{id}"

# 5 ISO weeks spread across the user's "past 6-12 months" target window.
DEFAULT_WEEKS = ["2025-W32", "2025-W41", "2025-W50", "2026-W07", "2026-W16"]
TOP_PER_WEEK = 4  # 5 weeks x 4 = 20


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _status(url: str, timeout: int = 30) -> int:
    req = urllib.request.Request(url, headers=UA, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


# --------------------------------------------------------------------------- #
# select                                                                       #
# --------------------------------------------------------------------------- #
def cmd_select(args: argparse.Namespace) -> None:
    weeks = args.weeks.split(",") if args.weeks else DEFAULT_WEEKS
    picked: dict[str, dict] = {}
    for wk in weeks:
        try:
            data = json.loads(_get(HF_WEEKLY.format(week=wk)))
        except Exception as e:  # noqa: BLE001
            print(f"  ! week {wk}: fetch failed ({e})")
            continue
        items = sorted(
            data, key=lambda it: it.get("paper", {}).get("upvotes", 0), reverse=True
        )
        n = 0
        for it in items:
            p = it.get("paper", {})
            pid = p.get("id")
            if not pid or pid in picked:
                continue
            picked[pid] = {
                "id": pid,
                "week": wk,
                "upvotes": p.get("upvotes", 0),
                "title": (p.get("title") or "").strip(),
                "keywords": p.get("ai_keywords") or [],
                "github": p.get("githubRepo") or p.get("projectPage") or "",
            }
            n += 1
            if n >= args.top:
                break
        print(f"  week {wk}: +{n} (running total {len(picked)})")
    papers = list(picked.values())
    BENCH.mkdir(parents=True, exist_ok=True)
    PAPERS_JSON.write_text(json.dumps(papers, ensure_ascii=False, indent=2))
    print(f"\nSelected {len(papers)} papers -> {PAPERS_JSON}")


# --------------------------------------------------------------------------- #
# fetch                                                                        #
# --------------------------------------------------------------------------- #
def cmd_fetch(args: argparse.Namespace) -> None:
    import pymupdf

    papers = json.loads(PAPERS_JSON.read_text())
    PDFS.mkdir(parents=True, exist_ok=True)
    HTML.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(papers, 1):
        pid = p["id"]
        pdf_path = PDFS / f"{pid}.pdf"
        if not pdf_path.exists():
            try:
                pdf_path.write_bytes(_get(ARXIV_PDF.format(id=pid)))
            except Exception as e:  # noqa: BLE001
                p["pdf_error"] = str(e)
                print(f"  [{i}/{len(papers)}] {pid} PDF FAIL {e}")
                continue
        # page count (cheap, via pymupdf) -- used to normalise s/page later
        try:
            with pymupdf.open(pdf_path) as doc:
                p["n_pages"] = doc.page_count
        except Exception as e:  # noqa: BLE001
            p["n_pages"] = None
            p["pdf_error"] = f"open: {e}"
        # arXiv HTML availability gate: native first, ar5iv fallback
        html_src, html_status = None, None
        nat = ARXIV_HTML.format(id=pid)
        if _status(nat) == 200:
            html_src, html_status = "arxiv", 200
            try:
                (HTML / f"{pid}.html").write_bytes(_get(nat))
            except Exception:  # noqa: BLE001
                html_status = "fetch_err"
        else:
            ar5 = AR5IV_HTML.format(id=pid)
            if _status(ar5) == 200:
                html_src, html_status = "ar5iv", 200
                try:
                    (HTML / f"{pid}.html").write_bytes(_get(ar5))
                except Exception:  # noqa: BLE001
                    html_status = "fetch_err"
            else:
                html_src, html_status = None, 404
        p["html_source"] = html_src
        p["html_status"] = html_status
        print(
            f"  [{i}/{len(papers)}] {pid}  pages={p.get('n_pages')}  html={html_src or 'none'}"
        )
    PAPERS_JSON.write_text(json.dumps(papers, ensure_ascii=False, indent=2))
    have_html = sum(1 for p in papers if p.get("html_source"))
    print(f"\nFetched. arXiv-HTML hit: {have_html}/{len(papers)} -> {PAPERS_JSON}")


# --------------------------------------------------------------------------- #
# parsers                                                                      #
# --------------------------------------------------------------------------- #
def parse_pymupdf(pdf: Path, pid: str) -> tuple[str, dict]:
    """Plain text extraction -- baseline proxy for the current fast path."""
    import pymupdf

    with pymupdf.open(pdf) as doc:
        md = "\n\n".join(page.get_text("text") for page in doc)
    return md, {"ext": "md"}


def parse_pymupdf4llm(pdf: Path, pid: str) -> tuple[str, dict]:
    import pymupdf4llm

    return pymupdf4llm.to_markdown(str(pdf), show_progress=False), {"ext": "md"}


_DOCLING_CONV = None


def parse_docling(pdf: Path, pid: str) -> tuple[str, dict]:
    global _DOCLING_CONV
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    if _DOCLING_CONV is None:
        opts = PdfPipelineOptions()
        opts.do_ocr = False  # native arXiv PDFs have a text layer -> OCR is pure waste
        opts.do_table_structure = True  # TableFormer is the whole point of docling
        _DOCLING_CONV = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
    res = _DOCLING_CONV.convert(str(pdf))
    md = res.document.export_to_markdown()
    (OUT / "docling").mkdir(parents=True, exist_ok=True)
    (OUT / "docling" / f"{pid}.json").write_text(
        json.dumps(res.document.export_to_dict(), ensure_ascii=False)
    )
    return md, {"ext": "md"}


_MARKER_CONV = None


def parse_marker(pdf: Path, pid: str) -> tuple[str, dict]:
    """Heavy control baseline -- matches production config (OCR off + surya MPS patch).

    Without _patch_surya_mps() surya returns garbage on Apple Silicon MPS (see
    backend/pdf/parser.py). Downloads ~2.6GB models on first use.
    """
    global _MARKER_CONV
    if _MARKER_CONV is None:
        from backend.pdf.parser import _patch_surya_mps

        _patch_surya_mps()
        from marker.config.parser import ConfigParser
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        cfg = ConfigParser(
            {"output_format": "markdown", "disable_ocr": True, "paginate_output": True}
        )
        _MARKER_CONV = PdfConverter(
            config=cfg.generate_config_dict(),
            artifact_dict=create_model_dict(),
            processor_list=cfg.get_processors(),
            renderer=cfg.get_renderer(),
        )
    from marker.output import text_from_rendered

    md, _, _ = text_from_rendered(_MARKER_CONV(str(pdf)))
    return md, {"ext": "md"}


def parse_mineru(pdf: Path, pid: str) -> tuple[str, dict]:
    """MinerU2.5 via its isolated venv + MLX backend (see .venv-mineru).

    Runs the `mineru` CLI to a temp dir and returns the largest produced .md
    (robust to the CLI's output-layout). NOTE: timed wall-clock is accurate, but
    peak RSS here is the harness worker's, NOT the mineru child process's.
    """
    mineru_bin = ROOT / ".venv-mineru" / "bin" / "mineru"
    if not mineru_bin.exists():
        raise FileNotFoundError(".venv-mineru not set up — run the MinerU setup first")
    out = BENCH / "_mineru_tmp" / pid
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(mineru_bin), "-p", str(pdf), "-o", str(out), "-b", "vlm-auto-engine"],
        check=True, capture_output=True, timeout=1800,
    )
    mds = sorted(out.rglob("*.md"), key=lambda p: len(p.read_bytes()), reverse=True)
    if not mds:
        raise RuntimeError("mineru produced no .md")
    return mds[0].read_text(errors="replace"), {"ext": "md"}


def parse_arxiv_html(pdf: Path, pid: str) -> tuple[str, dict]:
    """Not a PDF parse: read the pre-fetched arXiv/ar5iv HTML (source-derived)."""
    fp = HTML / f"{pid}.html"
    if not fp.exists():
        raise FileNotFoundError("no html (not available for this paper)")
    return fp.read_text(errors="replace"), {"ext": "html"}


PARSERS = {
    "pymupdf": parse_pymupdf,
    "pymupdf4llm": parse_pymupdf4llm,
    "docling": parse_docling,
    "marker": parse_marker,
    "mineru": parse_mineru,
    "arxiv_html": parse_arxiv_html,
}

_MATH = re.compile(r"\$\$|\$[^$\n]+\$|\\\(|\\\[|\\begin\{(equation|align|gather|multline|math)")
_HTML_MATH = re.compile(r"<math\b|\\\(|\$")
_MD_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.M)
_HTML_TABLE = re.compile(r"<table\b")
_MD_IMG = re.compile(r"!\[|<!--\s*image\s*-->")
_HTML_IMG = re.compile(r"<img\b|<figure\b")


def fidelity_counts(text: str, kind: str) -> dict:
    if kind == "html":
        return {
            "n_math": len(_HTML_MATH.findall(text)),
            "n_table": len(_HTML_TABLE.findall(text)),
            "n_image": len(_HTML_IMG.findall(text)),
        }
    return {
        "n_math": len(_MATH.findall(text)),
        "n_table": len(_MD_TABLE_ROW.findall(text)),
        "n_image": len(_MD_IMG.findall(text)),
    }


# --------------------------------------------------------------------------- #
# _run (subprocess worker: one parser over all papers)                         #
# --------------------------------------------------------------------------- #
def cmd_run(args: argparse.Namespace) -> None:
    parser = args.parser
    fn = PARSERS[parser]
    papers = json.loads(PAPERS_JSON.read_text())
    outdir = OUT / parser
    outdir.mkdir(parents=True, exist_ok=True)
    MET.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, dict] = {}
    t_all = time.perf_counter()
    for i, p in enumerate(papers, 1):
        pid = p["id"]
        pdf = PDFS / f"{pid}.pdf"
        rec: dict = {"ok": False}
        t0 = time.perf_counter()
        try:
            text, meta = fn(pdf, pid)
            dt = time.perf_counter() - t0
            (outdir / f"{pid}.{meta['ext']}").write_text(text, errors="replace")
            rec = {
                "ok": True,
                "seconds": round(dt, 3),
                "output_chars": len(text),
                **fidelity_counts(text, meta["ext"] if meta["ext"] == "html" else "md"),
            }
        except Exception as e:  # noqa: BLE001
            rec = {"ok": False, "seconds": round(time.perf_counter() - t0, 3), "error": str(e)[:300]}
        metrics[pid] = rec
        flag = "ok" if rec["ok"] else f"ERR {rec.get('error','')[:60]}"
        print(f"  [{parser}] [{i}/{len(papers)}] {pid} {rec.get('seconds')}s {flag}")
    # peak RSS of THIS subprocess (macOS: bytes; linux: KB)
    maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mb = maxrss / 1e6 if sys.platform == "darwin" else maxrss / 1024
    n_ok = sum(1 for r in metrics.values() if r["ok"])
    metrics["_meta"] = {
        "parser": parser,
        "n_ok": n_ok,
        "n_total": len(papers),
        "peak_rss_mb": round(peak_mb, 1),
        "total_seconds": round(time.perf_counter() - t_all, 1),
    }
    (MET / f"{parser}.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"  [{parser}] done: {n_ok}/{len(papers)} ok, peak {peak_mb:.0f}MB -> metrics/{parser}.json")


# --------------------------------------------------------------------------- #
# bench (orchestrator: spawn one subprocess per parser)                        #
# --------------------------------------------------------------------------- #
def cmd_bench(args: argparse.Namespace) -> None:
    parsers = args.parsers.split(",")
    for parser in parsers:
        if parser not in PARSERS:
            print(f"  ! unknown parser '{parser}', skipping")
            continue
        print(f"\n=== bench: {parser} ===")
        py = args.python or sys.executable
        rc = subprocess.run(
            [py, str(Path(__file__).resolve()), "_run", "--parser", parser]
        ).returncode
        if rc != 0:
            print(f"  ! {parser} subprocess exited {rc}")
    cmd_report(args)


# --------------------------------------------------------------------------- #
# report (glob all metrics -> RESULTS.md)                                      #
# --------------------------------------------------------------------------- #
def _mean(xs: list) -> float:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def cmd_report(args: argparse.Namespace) -> None:
    papers = json.loads(PAPERS_JSON.read_text()) if PAPERS_JSON.exists() else []
    pages = {p["id"]: p.get("n_pages") for p in papers}
    total_pages = sum(v for v in pages.values() if v) or None
    rows = []
    for mf in sorted(MET.glob("*.json")):
        m = json.loads(mf.read_text())
        meta = m.pop("_meta", {})
        oks = [r for r in m.values() if r.get("ok")]
        secs = [r["seconds"] for r in oks]
        rows.append({
            "parser": meta.get("parser", mf.stem),
            "ok": f"{len(oks)}/{len(m)}",
            "total_s": meta.get("total_seconds"),
            "s_paper": round(_mean(secs), 2),
            "s_page": round(sum(secs) / total_pages, 3) if total_pages and secs else None,
            "ram_mb": meta.get("peak_rss_mb"),
            "math": round(_mean([r.get("n_math") for r in oks]), 1),
            "table": round(_mean([r.get("n_table") for r in oks]), 1),
            "img": round(_mean([r.get("n_image") for r in oks]), 1),
            "chars": int(_mean([r.get("output_chars") for r in oks])),
        })
    have_html = sum(1 for p in papers if p.get("html_source"))
    lines = [
        "# Parser bake-off — M2 results",
        "",
        f"Sample: **{len(papers)} papers**, {total_pages or '?'} pages total. "
        f"arXiv-HTML hit rate: **{have_html}/{len(papers)}**.",
        "",
        "Fidelity columns (math/table/img) are cheap STRUCTURAL PROXIES, not the "
        "authoritative quality signal — that is the later Opus-4.8 judge.",
        "",
        "| parser | ok | total_s | s/paper | s/page | peak RAM(MB) | ~math | ~table | ~img | chars |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['parser']} | {r['ok']} | {r['total_s']} | {r['s_paper']} | "
            f"{r['s_page']} | {r['ram_mb']} | {r['math']} | {r['table']} | {r['img']} | {r['chars']} |"
        )
    lines += ["", "_Generated by scripts/parser_bench.py report._"]
    (BENCH / "RESULTS.md").write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\n-> {BENCH / 'RESULTS.md'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select"); s.add_argument("--weeks", default=""); s.add_argument("--top", type=int, default=TOP_PER_WEEK)
    sub.add_parser("fetch")
    r = sub.add_parser("_run"); r.add_argument("--parser", required=True)
    b = sub.add_parser("bench"); b.add_argument("--parsers", required=True); b.add_argument("--python", default="")
    sub.add_parser("report")
    args = ap.parse_args()
    {"select": cmd_select, "fetch": cmd_fetch, "_run": cmd_run, "bench": cmd_bench, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
