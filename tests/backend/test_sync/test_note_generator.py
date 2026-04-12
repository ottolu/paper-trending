from backend.sync.note_generator import generate_paper_note


def test_basic_note_has_frontmatter():
    paper = {
        "id": "2401.00001",
        "title": "Scaling Laws for Neural Language Models",
        "abstract": "We study empirical scaling laws.",
        "arxiv_id": "2401.00001",
        "published_date": "2024-01-15",
        "first_seen_at": "2024-01-16 08:00:00",
    }
    analysis = {
        "factual_summary": "本文研究了神经语言模型的缩放定律。",
        "methodology_inference": "通过不同模型规模的实证评估。",
        "innovation_points": '["提出新的缩放预测方法"]',
        "key_takeaways": '["更大的模型更高效"]',
        "score_total": 8.5,
        "tags": '["scaling-laws", "language-models"]',
        "evidence_level": "strong",
        "confidence": 0.85,
        "evidence_citations": '[{"claim": "缩放遵循幂律", "source": "full_text", "page": 3}]',
        "analysis_basis": "full_text",
    }
    source = {
        "source_url": "https://huggingface.co/papers/2401.00001",
    }

    note = generate_paper_note(paper, analysis, source)

    assert "---" in note
    assert "score: 8.5" in note
    assert 'arxiv: "2401.00001"' in note
    assert "published_date: 2024-01-15" in note
    assert "collected_date: 2024-01-16" in note
    assert "evidence_level: strong" in note
    assert "confidence: 0.85" in note


def test_note_has_chinese_sections():
    paper = {
        "id": "2401.00001",
        "title": "Test Paper",
        "abstract": "Abstract text.",
        "arxiv_id": "2401.00001",
        "published_date": "2024-01-15",
        "first_seen_at": "2024-01-16 08:00:00",
    }
    analysis = {
        "factual_summary": "这是事实摘要。",
        "methodology_inference": "这是方法推断。",
        "innovation_points": '["创新点一", "创新点二"]',
        "key_takeaways": '["结论一"]',
        "score_total": 7.0,
        "tags": '["nlp"]',
        "evidence_level": "moderate",
        "confidence": 0.7,
        "evidence_citations": '[]',
        "analysis_basis": "abstract_only",
    }

    note = generate_paper_note(paper, analysis)

    assert "# Test Paper" in note
    assert "## 事实摘要" in note
    assert "这是事实摘要。" in note
    assert "## 推断性方法总结" in note
    assert "这是方法推断。" in note
    assert "## 创新点" in note
    assert "- 创新点一" in note
    assert "- 创新点二" in note
    assert "## 关键结论" in note
    assert "- 结论一" in note
    assert "## 链接" in note


def test_note_with_evidence_citations():
    paper = {
        "id": "2401.00001",
        "title": "Test",
        "abstract": "A",
        "arxiv_id": "2401.00001",
        "published_date": None,
        "first_seen_at": "2024-01-16 08:00:00",
    }
    analysis = {
        "factual_summary": "摘要",
        "methodology_inference": "方法",
        "innovation_points": '[]',
        "key_takeaways": '[]',
        "score_total": 5.0,
        "tags": '[]',
        "evidence_level": "limited",
        "confidence": 0.5,
        "evidence_citations": '[{"claim": "主要发现", "source": "full_text", "page": 3}]',
        "analysis_basis": "full_text",
    }

    note = generate_paper_note(paper, analysis)

    assert "## 证据引用" in note
    assert "主要发现" in note
    assert "p.3" in note


def test_note_without_source():
    paper = {
        "id": "2401.00001",
        "title": "Test",
        "abstract": "A",
        "arxiv_id": "2401.00001",
        "published_date": None,
        "first_seen_at": "2024-01-16 08:00:00",
    }
    analysis = {
        "factual_summary": "摘要",
        "methodology_inference": "方法",
        "innovation_points": '[]',
        "key_takeaways": '[]',
        "score_total": 5.0,
        "tags": '[]',
        "evidence_level": "limited",
        "confidence": 0.5,
        "evidence_citations": '[]',
        "analysis_basis": "abstract_only",
    }

    note = generate_paper_note(paper, analysis, source=None)

    assert "arXiv: https://arxiv.org/abs/2401.00001" in note
    assert "## 链接" in note
