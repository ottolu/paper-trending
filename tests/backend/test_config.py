import os
from pathlib import Path

import pytest

from backend.config.loader import load_config, AppConfig


@pytest.fixture
def test_config_path():
    return Path(__file__).parent.parent / "fixtures" / "settings_test.yaml"


def test_load_config_returns_app_config(test_config_path):
    config = load_config(test_config_path)
    assert isinstance(config, AppConfig)


def test_load_config_reads_llm_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.llm.model == "gpt-5.4"
    assert config.llm.base_url == "https://api.openai.com/v1"


def test_load_config_reads_embedding_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.embedding.model == "text-embedding-3-small"
    assert config.embedding.active_version_id == 1


def test_load_config_reads_obsidian_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.obsidian.root_folder == "LLM-Research"


def test_load_config_reads_storage_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.storage.data_root == "./data"


def test_load_config_reads_pdf_settings(test_config_path):
    config = load_config(test_config_path)
    assert config.pdf.download_timeout_seconds == 120
    assert config.pdf.parser_name == "marker"


def test_load_config_interpolates_env_vars(test_config_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
    config = load_config(test_config_path)
    assert config.llm.api_key == "sk-test-key-123"


def test_load_config_missing_env_var_raises(test_config_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        load_config(test_config_path)
