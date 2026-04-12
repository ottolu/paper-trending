from __future__ import annotations
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel

class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Paper(BaseModel):
    id: str
    arxiv_id: str | None = None
    title: str
    authors: list[str] | None = None
    abstract: str
    arxiv_categories: list[str] | None = None
    published_date: date | None = None
    first_seen_at: datetime | None = None
    updated_at: datetime | None = None

class PaperSource(BaseModel):
    id: int | None = None
    paper_id: str
    source_name: str
    source_url: str | None = None
    source_record_id: str | None = None
    match_strategy: str | None = None
    match_confidence: float | None = None
    hf_likes: int | None = None
    hf_discussions: int | None = None
    collected_at: datetime | None = None

class PaperFile(BaseModel):
    id: int | None = None
    paper_id: str
    file_type: str = "pdf"
    source_url: str | None = None
    storage_path: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = None
    mime_type: str = "application/pdf"
    is_current: bool = False
    download_status: str = "pending"
    downloaded_at: datetime | None = None
    verified_at: datetime | None = None

class PdfExtraction(BaseModel):
    id: int | None = None
    paper_id: str
    paper_file_id: int
    parser_name: str
    parser_version: str
    extraction_status: str = "pending"
    page_count: int | None = None
    extraction_root_path: str | None = None
    extracted_text_path: str | None = None
    extracted_markdown_path: str | None = None
    blocks_json_path: str | None = None
    sections_json_path: str | None = None
    figures_json_path: str | None = None
    references_json_path: str | None = None
    parse_quality_score: float | None = None
    extracted_at: datetime | None = None

class StageRun(BaseModel):
    id: int | None = None
    target_type: str
    target_id: str
    stage: str
    status: StageStatus = StageStatus.PENDING
    logical_job_key: str
    attempt_no: int = 0
    worker_id: str | None = None
    lease_expires_at: datetime | None = None
    idempotency_key: str | None = None
    payload_json: dict[str, Any] | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

class StageRunAttempt(BaseModel):
    id: int | None = None
    stage_run_id: int
    attempt_no: int
    status: str = "running"
    worker_id: str
    lease_expires_at: datetime
    input_hash: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None

class AnalysisRun(BaseModel):
    id: int | None = None
    paper_id: str
    paper_file_id: int | None = None
    pdf_extraction_id: int | None = None
    chunk_manifest_path: str | None = None
    chunk_manifest_hash: str | None = None
    input_hash: str | None = None
    factual_summary: str | None = None
    methodology_inference: str | None = None
    innovation_points: list[str] | None = None
    key_takeaways: list[str] | None = None
    score_total: float | None = None
    score_breakdown: dict[str, float] | None = None
    tags: list[str] | None = None
    evidence_level: str | None = None
    analysis_basis: str = "abstract_only"
    evidence_citations: list[dict[str, Any]] | None = None
    confidence: float | None = None
    analysis_model: str | None = None
    prompt_version: str | None = None
    status: str = "pending"
    analyzed_at: datetime | None = None

class PaperAnalysis(BaseModel):
    paper_id: str
    active_analysis_run_id: int
    active_paper_file_id: int | None = None
    active_pdf_extraction_id: int | None = None
    active_analyzed_at: datetime

class EmbeddingVersion(BaseModel):
    id: int | None = None
    provider: str
    model: str
    dimension: int
    collection_name: str
    is_active: bool = False
    created_at: datetime | None = None

class ClusterRun(BaseModel):
    id: int | None = None
    run_type: str
    embedding_version_id: int
    window_start: date | None = None
    window_end: date | None = None
    paper_count: int | None = None
    algorithm_name: str = "hdbscan"
    algorithm_version: str | None = None
    cluster_params_json: dict[str, Any] | None = None
    input_snapshot_path: str | None = None
    input_snapshot_hash: str | None = None
    code_version: str | None = None
    is_stable: bool = False
    created_at: datetime | None = None

class ClusterEntity(BaseModel):
    id: str
    first_seen_run_id: int
    current_name: str
    current_description: str | None = None
    current_parent_id: str | None = None
    status: str = "active"
    updated_at: datetime | None = None

class ClusterVersion(BaseModel):
    id: int | None = None
    cluster_entity_id: str
    cluster_run_id: int
    name: str
    description: str | None = None
    parent_cluster_entity_id: str | None = None
    change_type: str
    created_at: datetime | None = None

class PaperClusterAssignment(BaseModel):
    id: int | None = None
    paper_id: str
    cluster_run_id: int
    cluster_version_id: int
    assignment_type: str
    similarity_score: float | None = None
    assigned_at: datetime | None = None

class WeeklyReport(BaseModel):
    id: int | None = None
    week_start: date
    week_end: date
    cluster_run_id: int | None = None
    analysis_run_ids_json: list[int] | None = None
    input_snapshot_path: str | None = None
    input_snapshot_hash: str | None = None
    report_model: str | None = None
    report_prompt_version: str | None = None
    supersedes_report_id: int | None = None
    is_current: bool = True
    report_content: str | None = None
    highlights: list[str] | None = None
    created_at: datetime | None = None

class SyncLogEntry(BaseModel):
    id: int | None = None
    paper_id: str | None = None
    report_id: int | None = None
    sync_type: str
    logical_target: str
    file_path: str
    checksum: str
    synced_at: datetime | None = None

class BackfillJob(BaseModel):
    id: int | None = None
    range_start: date
    range_end: date
    cursor_date: date | None = None
    status: str = "pending"
    attempt_no: int = 0
    worker_id: str | None = None
    lease_expires_at: datetime | None = None
    last_error: str | None = None
    cursor_semantics: str = "fixed_closed_day"
    updated_at: datetime | None = None

class BackfillJobDay(BaseModel):
    id: int | None = None
    backfill_job_id: int
    work_date: date
    collect_status: str = "pending"
    pdf_fetch_status: str = "pending"
    pdf_parse_status: str = "pending"
    processor_status: str = "pending"
    analyzer_status: str = "pending"
    sync_status: str = "pending"
    is_terminal: bool = False
    updated_at: datetime | None = None
