from backend.analyzer.prompts import build_analysis_prompt


def test_build_prompt_with_full_text():
    manifest = {
        "paper_id": "2401.00001",
        "title": "Test Paper",
        "abstract": "This is the abstract.",
        "authors": ["Author A"],
        "arxiv_categories": ["cs.CL"],
        "analysis_basis": "full_text",
        "chunks": [
            {"text": "Introduction text.", "index": 0, "char_count": 18},
            {"text": "Methods text.", "index": 1, "char_count": 13},
        ],
        "sections": [{"title": "Introduction", "level": 1}],
    }
    messages = build_analysis_prompt(manifest)
    assert len(messages) >= 2
    assert messages[0]["role"] == "system"
    assert "JSON" in messages[0]["content"]
    user_msg = messages[-1]["content"]
    assert "Test Paper" in user_msg
    assert "This is the abstract." in user_msg
    assert "Introduction text." in user_msg


def test_build_prompt_abstract_only():
    manifest = {
        "paper_id": "2401.00002",
        "title": "Abstract Only Paper",
        "abstract": "Only abstract available.",
        "authors": ["Author B"],
        "arxiv_categories": ["cs.AI"],
        "analysis_basis": "abstract_only",
        "chunks": [],
        "sections": [],
    }
    messages = build_analysis_prompt(manifest)
    user_msg = messages[-1]["content"]
    assert "Only abstract available." in user_msg
    assert "abstract_only" in user_msg.lower() or "abstract only" in user_msg.lower()


def test_prompt_requests_required_fields():
    manifest = {
        "paper_id": "2401.00001",
        "title": "T",
        "abstract": "A",
        "authors": [],
        "arxiv_categories": [],
        "analysis_basis": "abstract_only",
        "chunks": [],
        "sections": [],
    }
    messages = build_analysis_prompt(manifest)
    system_msg = messages[0]["content"]
    for field in ["factual_summary", "methodology_inference", "innovation_points",
                   "key_takeaways", "score_total", "tags"]:
        assert field in system_msg
