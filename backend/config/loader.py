from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    prompt_version: str = "analysis_v1"


class EmbeddingConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    active_version_id: int = 1


class ObsidianConfig(BaseModel):
    vault_path: str
    root_folder: str = "LLM-Research"


class StorageConfig(BaseModel):
    data_root: str = "./data"
    paper_root: str = "./data/papers"


class PDFConfig(BaseModel):
    download_timeout_seconds: int = 120
    max_file_size_mb: int = 100
    parser_name: str = "marker"
    parser_version: str = "v1"
    keep_raw_pdf: bool = True


class ArxivConfig(BaseModel):
    categories: list[str] = ["cs.CL", "cs.AI", "cs.LG"]
    request_interval_seconds: int = 3


class SchedulerConfig(BaseModel):
    collector_cron: str = "0 2 * * *"
    reporter_cron: str = "0 9 * * 1"


class AppConfig(BaseModel):
    llm: LLMConfig
    embedding: EmbeddingConfig
    obsidian: ObsidianConfig
    storage: StorageConfig = StorageConfig()
    pdf: PDFConfig = PDFConfig()
    arxiv: ArxivConfig = ArxivConfig()
    scheduler: SchedulerConfig = SchedulerConfig()


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _interpolate_env_vars(data: Any) -> Any:
    if isinstance(data, str):
        match = _ENV_VAR_PATTERN.fullmatch(data)
        if match:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                raise ValueError(
                    f"Environment variable {var_name} is required but not set"
                )
            return value
        return data
    if isinstance(data, dict):
        return {k: _interpolate_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_interpolate_env_vars(item) for item in data]
    return data


def load_config(path: Path | str) -> AppConfig:
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)
    resolved = _interpolate_env_vars(raw)
    return AppConfig(**resolved)
