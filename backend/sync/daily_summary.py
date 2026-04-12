from __future__ import annotations

import json

HIGH_SCORE_THRESHOLD = 8.0


def _parse_json_field(value: str | list) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _first_tag(tags_raw) -> str:
    tags = _parse_json_field(tags_raw)
    return f"#{tags[0]}" if tags else ""


def _summary_oneliner(summary: str, max_len: int = 40) -> str:
    line = summary.replace("\n", " ").strip()
    if len(line) > max_len:
        return line[:max_len] + "…"
    return line


def generate_daily_summary(
    date_str: str,
    papers: list[dict],
    total_collected: int = 0,
    total_analyzed: int = 0,
) -> str:
    sorted_papers = sorted(papers, key=lambda p: p.get("score_total", 0), reverse=True)
    high_score_papers = [p for p in sorted_papers if p.get("score_total", 0) >= HIGH_SCORE_THRESHOLD]

    lines = [
        f"# {date_str} 论文日报",
        "",
        f"今日采集 **{total_collected}** 篇，完成分析 **{total_analyzed}** 篇，"
        f"高分文章 **{len(high_score_papers)}** 篇",
        "",
    ]

    if high_score_papers:
        lines.append("## 高分文章")
        for p in high_score_papers:
            title = p.get("title", "Untitled")
            score = p.get("score_total", 0)
            summary = _summary_oneliner(p.get("factual_summary", ""))
            tag = _first_tag(p.get("tags", "[]"))
            tag_suffix = f" {tag}" if tag else ""
            lines.append(f"- [[{title}]] ({score}) — {summary}{tag_suffix}")
        lines.append("")

    lines.append("## 全部文章")
    lines.append("| 论文 | 评分 | 暂定领域 | 阅读基础 | 证据级别 |")
    lines.append("|------|------|----------|----------|----------|")
    for p in sorted_papers:
        title = p.get("title", "Untitled")
        score = p.get("score_total", 0)
        tag = _first_tag(p.get("tags", "[]"))
        basis = p.get("analysis_basis", "abstract_only")
        evidence = p.get("evidence_level", "limited")
        lines.append(f"| [[{title}]] | {score} | {tag} | {basis} | {evidence} |")
    lines.append("")

    return "\n".join(lines)
