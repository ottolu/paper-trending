from __future__ import annotations

WEEKLY_REPORT_SYSTEM_PROMPT = """你是一位 AI 研究趋势分析专家。基于本周收集和分析的论文数据，生成一份中文周报。

周报需要包含：
1. 本周趋势概述（整体方向和热点）
2. 推荐精读的论文（附推荐理由）
3. 各领域动态（按聚类分组，描述活跃度和变化）
4. 新兴信号（新出现的研究方向或跨领域关联）

输出格式为 Markdown，使用中文撰写。不要输出 JSON，直接输出 Markdown 正文。"""


def build_weekly_report_prompt(
    week_str: str,
    date_range: str,
    total_papers: int,
    total_analyzed: int,
    cluster_summaries: list[dict],
    prev_week_clusters: list[dict] | None = None,
) -> list[dict]:
    user_parts = [
        f"# {week_str} 周报数据 ({date_range})",
        "",
        f"本周采集论文 {total_papers} 篇，完成分析 {total_analyzed} 篇。",
        "",
    ]

    if cluster_summaries:
        user_parts.append("## 聚类分组")
        for i, cs in enumerate(cluster_summaries):
            name = cs.get("cluster_name", f"cluster-{i}")
            count = cs.get("paper_count", 0)
            tags = ", ".join(cs.get("common_tags", []))
            user_parts.append(f"\n### {name} ({count} 篇)")
            if tags:
                user_parts.append(f"常见标签: {tags}")
            top_papers = cs.get("top_papers", [])
            if top_papers:
                user_parts.append("代表性论文:")
                for p in top_papers:
                    title = p.get("title", "")
                    score = p.get("score", 0)
                    summary = p.get("summary", "")
                    user_parts.append(f"- {title} (评分 {score}): {summary}")
    else:
        user_parts.append("本周无聚类数据。")

    if prev_week_clusters:
        user_parts.append("\n## 上周聚类（对比参考）")
        for cs in prev_week_clusters:
            name = cs.get("cluster_name", "unknown")
            count = cs.get("paper_count", 0)
            user_parts.append(f"- {name}: {count} 篇")

    user_parts.append("\n请根据以上数据生成本周周报。")

    return [
        {"role": "system", "content": WEEKLY_REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
