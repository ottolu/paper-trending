"""Build the live pipeline runner + scheduler from config and shared clients."""
from __future__ import annotations

import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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


def _previous_complete_week(today: datetime.date) -> tuple[str, str]:
    """(monday, sunday) ISO dates of the week before `today`'s week."""
    days_since_monday = today.isoweekday() - 1  # Mon=0
    this_monday = today - datetime.timedelta(days=days_since_monday)
    last_monday = this_monday - datetime.timedelta(days=7)
    last_sunday = this_monday - datetime.timedelta(days=1)
    return last_monday.isoformat(), last_sunday.isoformat()


def build_scheduler(
    db, stage_runner, config, pipeline_runner, collector, reporter,
    tick_interval_seconds: int = 30,
) -> AsyncIOScheduler:
    """Assemble (but do not start) the live scheduler with three jobs."""
    scheduler = AsyncIOScheduler()

    async def _tick():
        try:
            n = await pipeline_runner.tick()
            if n:
                logger.info("pipeline tick processed %d items", n)
        except Exception:
            logger.exception("pipeline tick failed")

    async def _collect():
        try:
            res = await collector.collect_hf_daily()  # defaults: yesterday, top 15
            logger.info("scheduled HF daily collect: %s", res)
        except Exception:
            logger.exception("scheduled collect failed")

    async def _report():
        try:
            week_start, week_end = _previous_complete_week(datetime.date.today())
            report_id = await reporter.generate_report(week_start, week_end)
            logger.info("scheduled report %s..%s -> id=%s", week_start, week_end, report_id)
        except Exception:
            logger.exception("scheduled report failed")

    scheduler.add_job(_tick, IntervalTrigger(seconds=tick_interval_seconds), id="pipeline_tick")
    scheduler.add_job(_collect, CronTrigger.from_crontab(config.scheduler.collector_cron), id="collect")
    scheduler.add_job(_report, CronTrigger.from_crontab(config.scheduler.reporter_cron), id="report")
    return scheduler
