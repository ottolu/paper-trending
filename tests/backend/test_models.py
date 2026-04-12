from datetime import datetime, date
from backend.core.models import (
    Paper, PaperSource, PaperFile, StageRun, StageStatus,
    AnalysisRun, PaperAnalysis, EmbeddingVersion, WeeklyReport, SyncLogEntry,
)

def test_paper_creation():
    paper = Paper(id="2026.12345", title="Test Paper", abstract="An abstract about LLMs", published_date=date(2026, 4, 1))
    assert paper.id == "2026.12345"
    assert paper.arxiv_id is None
    assert paper.authors is None

def test_paper_with_all_fields():
    paper = Paper(id="2026.12345", arxiv_id="2026.12345", title="Test Paper", authors=["Alice", "Bob"], abstract="An abstract", arxiv_categories=["cs.CL", "cs.AI"], published_date=date(2026, 4, 1), first_seen_at=datetime(2026, 4, 7, 10, 0, 0))
    assert paper.authors == ["Alice", "Bob"]
    assert paper.arxiv_categories == ["cs.CL", "cs.AI"]

def test_paper_source_creation():
    source = PaperSource(paper_id="2026.12345", source_name="arxiv", source_url="https://arxiv.org/abs/2026.12345", match_strategy="arxiv_id", match_confidence=1.0)
    assert source.match_strategy == "arxiv_id"
    assert source.hf_likes is None

def test_paper_file_creation():
    pf = PaperFile(paper_id="2026.12345", source_url="https://arxiv.org/pdf/2026.12345", sha256="abc123", file_size_bytes=1024000)
    assert pf.file_type == "pdf"
    assert pf.is_current is False
    assert pf.download_status == "pending"

def test_stage_run_creation():
    sr = StageRun(target_type="paper", target_id="2026.12345", stage="pdf_fetch", logical_job_key="paper:2026.12345:pdf_fetch:v1")
    assert sr.status == StageStatus.PENDING
    assert sr.attempt_no == 0

def test_stage_status_enum():
    assert StageStatus.PENDING == "pending"
    assert StageStatus.RUNNING == "running"
    assert StageStatus.SUCCEEDED == "succeeded"
    assert StageStatus.FAILED == "failed"
    assert StageStatus.CANCELLED == "cancelled"

def test_analysis_run_creation():
    ar = AnalysisRun(paper_id="2026.12345", analysis_basis="full_text", analysis_model="gpt-5.4", prompt_version="analysis_v1")
    assert ar.analysis_basis == "full_text"
    assert ar.score_total is None
    assert ar.confidence is None

def test_paper_analysis_creation():
    pa = PaperAnalysis(paper_id="2026.12345", active_analysis_run_id=1, active_analyzed_at=datetime(2026, 4, 7, 12, 0, 0))
    assert pa.active_paper_file_id is None

def test_embedding_version_creation():
    ev = EmbeddingVersion(provider="openai", model="text-embedding-3-small", dimension=1536, collection_name="paper_embeddings_v1")
    assert ev.is_active is False

def test_weekly_report_creation():
    wr = WeeklyReport(week_start=date(2026, 4, 7), week_end=date(2026, 4, 13), report_content="# Weekly Report")
    assert wr.is_current is True
    assert wr.supersedes_report_id is None

def test_sync_log_entry_creation():
    entry = SyncLogEntry(paper_id="2026.12345", sync_type="paper_note", logical_target="paper:2026.12345", file_path="LLM-Research/2026-W15/2026-04-07/test-paper.md", checksum="sha256:abc")
    assert entry.report_id is None
