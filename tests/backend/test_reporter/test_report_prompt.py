from backend.reporter.report_prompt import build_weekly_report_prompt


def test_prompt_has_system_and_user_messages():
    cluster_summaries = [
        {
            "cluster_name": "cluster-0",
            "paper_count": 5,
            "top_papers": [
                {"title": "Paper A", "score": 9.0, "summary": "Summary A"},
                {"title": "Paper B", "score": 8.5, "summary": "Summary B"},
            ],
            "common_tags": ["rlhf", "alignment"],
        },
    ]
    messages = build_weekly_report_prompt(
        week_str="2024-W03",
        date_range="2024-01-15 ~ 2024-01-21",
        total_papers=20,
        total_analyzed=18,
        cluster_summaries=cluster_summaries,
    )

    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"


def test_prompt_includes_cluster_data():
    cluster_summaries = [
        {
            "cluster_name": "RLHF研究",
            "paper_count": 8,
            "top_papers": [
                {"title": "RLHF论文", "score": 9.2, "summary": "关于RLHF"},
            ],
            "common_tags": ["rlhf"],
        },
    ]
    messages = build_weekly_report_prompt(
        week_str="2024-W03",
        date_range="2024-01-15 ~ 2024-01-21",
        total_papers=10,
        total_analyzed=8,
        cluster_summaries=cluster_summaries,
    )
    user_msg = messages[-1]["content"]
    assert "RLHF研究" in user_msg
    assert "RLHF论文" in user_msg


def test_prompt_requests_chinese_output():
    messages = build_weekly_report_prompt(
        week_str="2024-W03",
        date_range="2024-01-15 ~ 2024-01-21",
        total_papers=0,
        total_analyzed=0,
        cluster_summaries=[],
    )
    system_msg = messages[0]["content"]
    assert "中文" in system_msg


def test_prompt_includes_week_metadata():
    messages = build_weekly_report_prompt(
        week_str="2024-W03",
        date_range="2024-01-15 ~ 2024-01-21",
        total_papers=25,
        total_analyzed=20,
        cluster_summaries=[],
    )
    user_msg = messages[-1]["content"]
    assert "2024-W03" in user_msg
    assert "25" in user_msg
