from backend.sync.daily_summary import generate_daily_summary


def test_daily_summary_basic():
    papers = [
        {
            "title": "High Score Paper",
            "score_total": 9.2,
            "tags": '["training/rlhf"]',
            "factual_summary": "一句话概要高分",
            "analysis_basis": "full_text",
            "evidence_level": "strong",
        },
        {
            "title": "Medium Score Paper",
            "score_total": 6.5,
            "tags": '["inference"]',
            "factual_summary": "一句话概要中分",
            "analysis_basis": "abstract_only",
            "evidence_level": "moderate",
        },
    ]

    md = generate_daily_summary("2024-01-15", papers, total_collected=5, total_analyzed=2)

    assert "# 2024-01-15 论文日报" in md
    assert "**5**" in md
    assert "**2**" in md
    assert "**1**" in md  # 1 high-score paper (>=8.0)


def test_daily_summary_high_score_section():
    papers = [
        {
            "title": "Top Paper",
            "score_total": 9.0,
            "tags": '["nlp"]',
            "factual_summary": "非常重要的发现",
            "analysis_basis": "full_text",
            "evidence_level": "strong",
        },
    ]

    md = generate_daily_summary("2024-01-15", papers, total_collected=1, total_analyzed=1)

    assert "## 高分文章" in md
    assert "[[Top Paper]]" in md
    assert "(9.0)" in md


def test_daily_summary_table():
    papers = [
        {
            "title": "Paper A",
            "score_total": 7.5,
            "tags": '["tag1"]',
            "factual_summary": "摘要A",
            "analysis_basis": "full_text",
            "evidence_level": "strong",
        },
    ]

    md = generate_daily_summary("2024-01-15", papers, total_collected=1, total_analyzed=1)

    assert "## 全部文章" in md
    assert "| 论文 | 评分 | 暂定领域 | 阅读基础 | 证据级别 |" in md
    assert "[[Paper A]]" in md
    assert "7.5" in md


def test_daily_summary_empty():
    md = generate_daily_summary("2024-01-15", [], total_collected=0, total_analyzed=0)
    assert "# 2024-01-15 论文日报" in md
    assert "**0**" in md


def test_daily_summary_sorts_by_score():
    papers = [
        {
            "title": "Low",
            "score_total": 5.0,
            "tags": '["a"]',
            "factual_summary": "低分",
            "analysis_basis": "abstract_only",
            "evidence_level": "limited",
        },
        {
            "title": "High",
            "score_total": 9.5,
            "tags": '["b"]',
            "factual_summary": "高分",
            "analysis_basis": "full_text",
            "evidence_level": "strong",
        },
    ]

    md = generate_daily_summary("2024-01-15", papers, total_collected=2, total_analyzed=2)

    high_pos = md.index("[[High]]")
    low_pos = md.index("[[Low]]")
    assert high_pos < low_pos
