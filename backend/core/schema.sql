PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    arxiv_id TEXT UNIQUE,
    title TEXT NOT NULL,
    authors JSON,
    abstract TEXT NOT NULL,
    arxiv_categories JSON,
    published_date DATE,
    first_seen_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_record_id TEXT,
    match_strategy TEXT,
    match_confidence REAL,
    hf_likes INTEGER,
    hf_discussions INTEGER,
    collected_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    file_type TEXT NOT NULL DEFAULT 'pdf',
    source_url TEXT,
    storage_path TEXT,
    file_size_bytes INTEGER,
    sha256 TEXT,
    mime_type TEXT DEFAULT 'application/pdf',
    is_current BOOLEAN DEFAULT FALSE,
    download_status TEXT DEFAULT 'pending',
    downloaded_at DATETIME,
    verified_at DATETIME,
    UNIQUE(paper_id, sha256)
);

CREATE TABLE IF NOT EXISTS pdf_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    paper_file_id INTEGER NOT NULL REFERENCES paper_files(id),
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    extraction_status TEXT DEFAULT 'pending',
    page_count INTEGER,
    extraction_root_path TEXT,
    extracted_text_path TEXT,
    extracted_markdown_path TEXT,
    blocks_json_path TEXT,
    sections_json_path TEXT,
    figures_json_path TEXT,
    references_json_path TEXT,
    parse_quality_score REAL,
    extracted_at DATETIME
);

CREATE TABLE IF NOT EXISTS stage_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    logical_job_key TEXT UNIQUE NOT NULL,
    attempt_no INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    lease_expires_at DATETIME,
    idempotency_key TEXT,
    payload_json JSON,
    last_error TEXT,
    last_error_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS stage_run_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_run_id INTEGER NOT NULL REFERENCES stage_runs(id),
    attempt_no INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    worker_id TEXT NOT NULL,
    lease_expires_at DATETIME NOT NULL,
    input_hash TEXT,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    error_message TEXT,
    UNIQUE(stage_run_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    paper_file_id INTEGER REFERENCES paper_files(id),
    pdf_extraction_id INTEGER REFERENCES pdf_extractions(id),
    chunk_manifest_path TEXT,
    chunk_manifest_hash TEXT,
    input_hash TEXT,
    factual_summary TEXT,
    methodology_inference TEXT,
    innovation_points JSON,
    key_takeaways JSON,
    score_total REAL,
    score_breakdown JSON,
    tags JSON,
    evidence_level TEXT,
    analysis_basis TEXT NOT NULL DEFAULT 'abstract_only',
    evidence_citations JSON,
    confidence REAL,
    analysis_model TEXT,
    prompt_version TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    analyzed_at DATETIME
);

CREATE TABLE IF NOT EXISTS paper_analysis (
    paper_id TEXT PRIMARY KEY REFERENCES papers(id),
    active_analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    active_paper_file_id INTEGER REFERENCES paper_files(id),
    active_pdf_extraction_id INTEGER REFERENCES pdf_extractions(id),
    active_analyzed_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS embedding_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    collection_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    embedding_version_id INTEGER NOT NULL REFERENCES embedding_versions(id),
    window_start DATE,
    window_end DATE,
    paper_count INTEGER,
    algorithm_name TEXT NOT NULL DEFAULT 'hdbscan',
    algorithm_version TEXT,
    cluster_params_json JSON,
    input_snapshot_path TEXT,
    input_snapshot_hash TEXT,
    code_version TEXT,
    is_stable BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_entities (
    id TEXT PRIMARY KEY,
    first_seen_run_id INTEGER NOT NULL REFERENCES cluster_runs(id),
    current_name TEXT NOT NULL,
    current_description TEXT,
    current_parent_id TEXT REFERENCES cluster_entities(id),
    status TEXT NOT NULL DEFAULT 'active',
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_entity_id TEXT NOT NULL REFERENCES cluster_entities(id),
    cluster_run_id INTEGER NOT NULL REFERENCES cluster_runs(id),
    name TEXT NOT NULL,
    description TEXT,
    parent_cluster_entity_id TEXT REFERENCES cluster_entities(id),
    change_type TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_cluster_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL REFERENCES papers(id),
    cluster_run_id INTEGER NOT NULL REFERENCES cluster_runs(id),
    cluster_version_id INTEGER NOT NULL REFERENCES cluster_versions(id),
    assignment_type TEXT NOT NULL,
    similarity_score REAL,
    assigned_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    cluster_run_id INTEGER REFERENCES cluster_runs(id),
    analysis_run_ids_json JSON,
    input_snapshot_path TEXT,
    input_snapshot_hash TEXT,
    report_model TEXT,
    report_prompt_version TEXT,
    supersedes_report_id INTEGER REFERENCES weekly_reports(id),
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    report_content TEXT,
    highlights JSON,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT REFERENCES papers(id),
    report_id INTEGER REFERENCES weekly_reports(id),
    sync_type TEXT NOT NULL,
    logical_target TEXT NOT NULL,
    file_path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    synced_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS backfill_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    range_start DATE NOT NULL,
    range_end DATE NOT NULL,
    cursor_date DATE,
    status TEXT NOT NULL DEFAULT 'pending',
    attempt_no INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    lease_expires_at DATETIME,
    last_error TEXT,
    cursor_semantics TEXT DEFAULT 'fixed_closed_day',
    updated_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS backfill_job_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backfill_job_id INTEGER NOT NULL REFERENCES backfill_jobs(id),
    work_date DATE NOT NULL,
    collect_status TEXT NOT NULL DEFAULT 'pending',
    pdf_fetch_status TEXT NOT NULL DEFAULT 'pending',
    pdf_parse_status TEXT NOT NULL DEFAULT 'pending',
    processor_status TEXT NOT NULL DEFAULT 'pending',
    analyzer_status TEXT NOT NULL DEFAULT 'pending',
    sync_status TEXT NOT NULL DEFAULT 'pending',
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_papers_published_date ON papers(published_date);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_paper_sources_paper_id ON paper_sources(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_files_paper_id ON paper_files(paper_id);
CREATE INDEX IF NOT EXISTS idx_pdf_extractions_paper_id ON pdf_extractions(paper_id);
CREATE INDEX IF NOT EXISTS idx_stage_runs_status_stage ON stage_runs(status, stage);
CREATE INDEX IF NOT EXISTS idx_stage_runs_target ON stage_runs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_paper_id ON analysis_runs(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_analysis_analyzed_at ON paper_analysis(active_analyzed_at);
CREATE INDEX IF NOT EXISTS idx_cluster_assignments_paper ON paper_cluster_assignments(paper_id);
CREATE INDEX IF NOT EXISTS idx_cluster_assignments_run ON paper_cluster_assignments(cluster_run_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_target ON sync_log(logical_target);
CREATE INDEX IF NOT EXISTS idx_backfill_job_days_job ON backfill_job_days(backfill_job_id);
