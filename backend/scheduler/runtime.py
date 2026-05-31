"""Build the live pipeline runner + scheduler from config and shared clients."""
from __future__ import annotations

import logging

from backend.analyzer.service import AnalyzerService
from backend.pdf.fetcher import PdfFetcher
from backend.pdf.parser import PdfParser
from backend.processor.service import ProcessorService
from backend.scheduler.pipeline import PipelineRunner
from backend.sync.service import ObsidianSyncService

logger = logging.getLogger(__name__)


def build_pipeline_runner(
    db, stage_runner, config, llm_client, embedding_client, vector_store
) -> PipelineRunner:
    """Construct every stage service and assemble the PipelineRunner."""
    paper_root = config.storage.paper_root
    services = {
        "pdf_fetch": PdfFetcher(
            db, stage_runner, paper_root=paper_root,
            download_timeout=config.pdf.download_timeout_seconds,
        ),
        "pdf_parse": PdfParser(
            db, stage_runner, paper_root=paper_root,
            parser_name=config.pdf.parser_name, parser_version=config.pdf.parser_version,
        ),
        "processor": ProcessorService(db, stage_runner, paper_root=paper_root),
        "analyzer": AnalyzerService(
            db, stage_runner, paper_root=paper_root,
            llm_client=llm_client, embedding_client=embedding_client,
            vector_store=vector_store,
        ),
        "sync": ObsidianSyncService(
            db, stage_runner, vault_path=config.obsidian.vault_path,
            root_folder=config.obsidian.root_folder,
        ),
    }
    return PipelineRunner(db, stage_runner, services)
