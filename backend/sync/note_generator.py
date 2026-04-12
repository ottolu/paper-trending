from __future__ import annotations

import json


def _parse_json_field(value: str | list) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def generate_paper_note(
    paper: dict,
    analysis: dict,
    source: dict | None = None,
) -> str:
    arxiv_id = paper.get("arxiv_id", "")
    title = paper.get("title", "Untitled")
    published_date = paper.get("published_date") or ""
    first_seen = paper.get("first_seen_at", "")
    collected_date = first_seen[:10] if first_seen else ""

    tags = _parse_json_field(analysis.get("tags", "[]"))
    score = analysis.get("score_total", 0)
    evidence_level = analysis.get("evidence_level", "limited")
    confidence = analysis.get("confidence", 0)

    # Frontmatter
    tags_str = ", ".join(tags) if tags else ""
    lines = [
        "---",
        f"tags: [{tags_str}]",
        f"score: {score}",
        f'arxiv: "{arxiv_id}"',
        f"published_date: {published_date}" if published_date else "published_date:",
        f"collected_date: {collected_date}" if collected_date else "collected_date:",
        f"evidence_level: {evidence_level}",
        f"confidence: {confidence}",
        "---",
        "",
        f"# {title}",
        "",
    ]

    # 事实摘要
    lines.append("## 事实摘要")
    lines.append(analysis.get("factual_summary", ""))
    lines.append("")

    # 推断性方法总结
    lines.append("## 推断性方法总结")
    lines.append(analysis.get("methodology_inference", ""))
    lines.append("")

    # 创新点
    innovation_points = _parse_json_field(analysis.get("innovation_points", "[]"))
    lines.append("## 创新点")
    if innovation_points:
        for point in innovation_points:
            lines.append(f"- {point}")
    else:
        lines.append("- （无）")
    lines.append("")

    # 关键结论
    key_takeaways = _parse_json_field(analysis.get("key_takeaways", "[]"))
    lines.append("## 关键结论")
    if key_takeaways:
        for takeaway in key_takeaways:
            lines.append(f"- {takeaway}")
    else:
        lines.append("- （无）")
    lines.append("")

    # 证据引用
    evidence_citations = _parse_json_field(analysis.get("evidence_citations", "[]"))
    if evidence_citations:
        lines.append("## 证据引用")
        for cite in evidence_citations:
            claim = cite.get("claim", "")
            page = cite.get("page")
            source_type = cite.get("source", "")
            if page:
                lines.append(f"- p.{page}: {claim}")
            else:
                lines.append(f"- [{source_type}] {claim}")
        lines.append("")

    # 链接
    lines.append("## 链接")
    if arxiv_id:
        lines.append(f"- arXiv: https://arxiv.org/abs/{arxiv_id}")
    if source and source.get("source_url"):
        lines.append(f"- HuggingFace: {source['source_url']}")
    lines.append("")

    return "\n".join(lines)
