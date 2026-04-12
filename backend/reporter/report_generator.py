from __future__ import annotations


def generate_weekly_markdown(
    week_str: str,
    date_range: str,
    cluster_run_id: int | None,
    llm_report_body: str,
    highlights: list[dict] | None = None,
) -> str:
    lines = [
        f"# {week_str} 周报 ({date_range})",
        "",
    ]

    if cluster_run_id is not None:
        lines.append(f"> cluster_run_id: {cluster_run_id}")
        lines.append("")

    if highlights:
        lines.append("## 推荐精读")
        for h in highlights:
            title = h.get("title", "")
            reason = h.get("reason", "")
            lines.append(f"- [[{title}]] — {reason}")
        lines.append("")

    lines.append(llm_report_body)
    lines.append("")

    return "\n".join(lines)
