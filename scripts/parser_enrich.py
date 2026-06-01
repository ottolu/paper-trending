"""Enrichment layer: turn raw parser output into text-LLM-ready markdown.

Two gaps the bake-off exposed (see dev-note 2026-06-01-pdf-parsing-options-research):
  1. raw arXiv HTML is bloated/distracting for an LLM (MathML ~27x the LaTeX it
     encodes + nav/CSS boilerplate). FIX: linearize -> clean markdown, pulling the
     original LaTeX out of <annotation encoding="application/x-tex">.
  2. MinerU extracts figures as images + keeps the paper's caption, but writes NO
     description of the image content. A text-only reader (DeepSeek V4 Pro) can't see
     them. FIX: a VLM describes each figure; we inline the description.

Subcommands (operate on data/parser_bench/ artifacts; do NOT re-parse):
    linearize           raw arXiv HTML -> outputs/arxiv_html_clean/<id>.md
    manifest            MinerU content_list -> _enrich/<id>.figs.json (meaningful figs)
    inline --id <id>    apply captions (_enrich/<id>.captions.json) -> outputs/mineru_enriched/<id>.md

The captions themselves are produced by a VLM (here: Claude agents via the Read tool)
between `manifest` and `inline`, written to _enrich/<id>.captions.json as {name: desc}.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "data" / "parser_bench"
OUT = BENCH / "outputs"
ENR = BENCH / "_enrich"
PAPERS_JSON = BENCH / "papers.json"
TMP = BENCH / "_mineru_tmp"


# --------------------------------------------------------------------------- #
# 1. HTML linearizer                                                          #
# --------------------------------------------------------------------------- #
def linearize_html(raw: str) -> str:
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    soup = BeautifulSoup(raw, "lxml")
    # math -> $latex$ from the x-tex annotation (collapses dozens of MathML nodes)
    for m in soup.find_all("math"):
        ann = m.find("annotation", attrs={"encoding": "application/x-tex"})
        tex = (ann.get_text() if ann else (m.get("alttext") or "")).strip()
        if not tex:
            m.decompose()
            continue
        disp = m.get("display") == "block"
        m.replace_with(f"\n$$ {tex} $$\n" if disp else f" ${tex}$ ")
    # drop boilerplate / human-only chrome
    for sel in ["script", "style", "nav", "header", "footer"]:
        for t in soup.find_all(sel):
            t.decompose()
    for t in soup.find_all(class_=re.compile(r"navbar|footer|ltx_page_logo|watermark|ltx_tocentry|report")):
        t.decompose()
    art = (soup.find("article") or soup.find("div", class_="ltx_page_main")
           or soup.body or soup)
    md = markdownify(str(art), heading_style="ATX", strip=["a"])
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


def cmd_linearize(args: argparse.Namespace) -> None:
    papers = json.loads(PAPERS_JSON.read_text())
    dst = OUT / "arxiv_html_clean"
    dst.mkdir(parents=True, exist_ok=True)
    for p in papers:
        pid = p["id"]
        src = BENCH / "html" / f"{pid}.html"
        if not src.exists():
            print(f"  {pid}: no html, skip")
            continue
        raw = src.read_text(errors="replace")
        md = linearize_html(raw)
        (dst / f"{pid}.md").write_text(md)
        flag = "⚠ ar5iv-fail?" if len(md) < 2000 else ""
        print(f"  {pid}: {len(raw):>8,} -> {len(md):>8,} chars  math=${md.count('$')//2}$  {flag}")


# --------------------------------------------------------------------------- #
# 2. Figure manifest (meaningful figures only)                                 #
# --------------------------------------------------------------------------- #
def _walk(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from _walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk(v)


def _img_dir(pid: str) -> Path | None:
    hits = glob.glob(str(TMP / pid / "**" / "images"), recursive=True)
    return Path(hits[0]) if hits else None


def cmd_manifest(args: argparse.Namespace) -> None:
    ENR.mkdir(parents=True, exist_ok=True)
    ids = args.ids.split(",") if args.ids else [p["id"] for p in json.loads(PAPERS_JSON.read_text())]
    for pid in ids:
        cls = glob.glob(str(TMP / pid / "**" / "*_content_list.json"), recursive=True)
        if not cls:
            print(f"  {pid}: no content_list, skip")
            continue
        d = json.load(open(cls[0]))
        imgdir = _img_dir(pid)
        figs = []
        for b in _walk(d):
            if not (isinstance(b, dict) and b.get("type") in ("image", "chart")):
                continue
            cap = b.get("image_caption") or b.get("img_caption") or []
            cap = " ".join(cap) if isinstance(cap, list) else str(cap)
            if b.get("type") == "image" and not cap.strip():
                continue  # skip uncaptioned decorative images/logos
            name = os.path.basename(b.get("img_path", ""))
            ap = imgdir / name if imgdir and name else None
            if not (ap and ap.exists()):
                continue
            figs.append({"name": name, "path": str(ap), "caption": cap.strip(),
                         "page": b.get("page_idx"), "type": b.get("type")})
        (ENR / f"{pid}.figs.json").write_text(json.dumps(figs, ensure_ascii=False, indent=2))
        print(f"  {pid}: {len(figs)} meaningful figures -> _enrich/{pid}.figs.json")


# --------------------------------------------------------------------------- #
# 3. Inline VLM captions into the MinerU markdown                              #
# --------------------------------------------------------------------------- #
def cmd_inline(args: argparse.Namespace) -> None:
    pid = args.id
    capf = ENR / f"{pid}.captions.json"
    if not capf.exists():
        raise SystemExit(f"no captions file {capf} — run the VLM caption step first")
    caps = json.loads(capf.read_text())
    md = (OUT / "mineru" / f"{pid}.md").read_text(errors="replace")
    dst = OUT / "mineru_enriched"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for name, desc in caps.items():
        # replace the markdown image ref with itself + an inlined description block
        pat = re.compile(r"!\[\]\([^)]*" + re.escape(name) + r"\)")
        repl = f"![](images/{name})\n\n> **[Figure — VLM description]** {desc}\n"
        md, k = pat.subn(repl, md)
        n += k
    (dst / f"{pid}.md").write_text(md)
    print(f"  {pid}: inlined {n}/{len(caps)} captions -> outputs/mineru_enriched/{pid}.md")


# --------------------------------------------------------------------------- #
# 4. Assemble ONE canonical fulltext per paper (the final feed to the LLM)      #
# --------------------------------------------------------------------------- #
_DETAILS = re.compile(r"<details>\s*<summary>([^<]*)</summary>(.*?)</details>", re.S)
_IMGREF = re.compile(r"!\[\]\([^)]*\)")


def _clean_mineru(md: str) -> str:
    """MinerU enriched md -> clean text fulltext.

    - drop <details>text_image</details> (garbled in-image OCR fragments)
    - unwrap every other <details><summary>TYPE</summary>DESC</details> -> keep DESC
      (these are MinerU's own one-line chart/flowchart descriptions — useful signal)
    - strip ![](images/..) refs entirely: a text-only LLM can't fetch them, and the
      figure's information now lives in the inlined VLM description + MinerU desc + caption
    """
    def repl(m: re.Match) -> str:
        typ, body = m.group(1).strip(), m.group(2).strip()
        if typ == "text_image":
            return ""
        return f"\n*[{typ}]* {body}\n" if body else ""

    md = _DETAILS.sub(repl, md)
    md = _IMGREF.sub("", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def cmd_assemble(args: argparse.Namespace) -> None:
    papers = json.loads(PAPERS_JSON.read_text())
    dst = OUT / "fulltext"
    dst.mkdir(parents=True, exist_ok=True)
    routed = {"html": 0, "mineru": 0}
    for p in papers:
        pid = p["id"]
        clean_html = OUT / "arxiv_html_clean" / f"{pid}.md"
        # content gate: a usable native-HTML clean md wins; else the MinerU route
        if clean_html.exists() and len(clean_html.read_text(errors="replace")) > 2000:
            md = clean_html.read_text(errors="replace")
            route = "html"
        else:
            src = OUT / "mineru_enriched" / f"{pid}.md"
            if not src.exists():
                print(f"  {pid}: no mineru_enriched, skip")
                continue
            md = _clean_mineru(src.read_text(errors="replace"))
            route = "mineru"
        routed[route] += 1
        header = f"<!-- fulltext route={route} -->\n\n"
        (dst / f"{pid}.md").write_text(header + md)
        print(f"  {pid}: route={route:6} {len(md):>8,} chars -> outputs/fulltext/{pid}.md")
    print(f"\nrouted: {routed['html']} via native-HTML-clean, {routed['mineru']} via MinerU-assembled")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("linearize")
    m = sub.add_parser("manifest"); m.add_argument("--ids", default="")
    i = sub.add_parser("inline"); i.add_argument("--id", required=True)
    sub.add_parser("assemble")
    args = ap.parse_args()
    {"linearize": cmd_linearize, "manifest": cmd_manifest, "inline": cmd_inline,
     "assemble": cmd_assemble}[args.cmd](args)


if __name__ == "__main__":
    main()
