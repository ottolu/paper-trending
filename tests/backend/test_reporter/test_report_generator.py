from backend.reporter.report_generator import generate_weekly_markdown


def test_weekly_markdown_basic():
    md = generate_weekly_markdown(
        week_str="2024-W03",
        date_range="01.15 - 01.21",
        cluster_run_id=42,
        llm_report_body="## 本周趋势\n这是趋势内容。",
        highlights=[
            {"title": "Top Paper", "reason": "突破性研究"},
        ],
    )

    assert "# 2024-W03 周报 (01.15 - 01.21)" in md
    assert "cluster_run_id: 42" in md
    assert "## 本周趋势" in md
    assert "这是趋势内容。" in md


def test_weekly_markdown_has_highlights():
    md = generate_weekly_markdown(
        week_str="2024-W03",
        date_range="01.15 - 01.21",
        cluster_run_id=1,
        llm_report_body="报告内容",
        highlights=[
            {"title": "Paper A", "reason": "重要发现"},
            {"title": "Paper B", "reason": "新方法"},
        ],
    )

    assert "## 推荐精读" in md
    assert "[[Paper A]]" in md
    assert "重要发现" in md
    assert "[[Paper B]]" in md


def test_weekly_markdown_no_highlights():
    md = generate_weekly_markdown(
        week_str="2024-W03",
        date_range="01.15 - 01.21",
        cluster_run_id=1,
        llm_report_body="报告内容",
        highlights=[],
    )

    assert "# 2024-W03 周报" in md
    assert "报告内容" in md
