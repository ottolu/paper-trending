from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, model_validator


class LLMConfig(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    prompt_version: str = "analysis_v1"

    @model_validator(mode="after")
    def _resolve_api_key(self):
        if not self.api_key:
            self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "llm.api_key must be set in config file or via OPENAI_API_KEY env var"
            )
        return self


class EmbeddingConfig(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "text-embedding-3-small"
    active_version_id: int = 1

    @model_validator(mode="after")
    def _resolve_api_key(self):
        if not self.api_key:
            self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "embedding.api_key must be set in config file or via OPENAI_API_KEY env var"
            )
        return self


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
            return os.environ.get(var_name, "")
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
