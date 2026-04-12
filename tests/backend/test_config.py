from pathlib import Path

import pytest

from backend.config.loader import load_config, AppConfig


@pytest.fixture(autouse=True)
def _set_env_vars(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-for-config")


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
    """${VAR} syntax in yaml resolves to the env var value."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
    config = load_config(test_config_path)
    assert config.llm.api_key == "sk-test-key-123"


def test_load_config_env_var_fallback(test_config_path, monkeypatch):
    """Empty api_key in yaml falls back to OPENAI_API_KEY env var."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fallback-key")
    config = load_config(test_config_path)
    # embedding.api_key is "" in test fixture → should fall back to env var
    assert config.embedding.api_key == "sk-fallback-key"


def test_load_config_direct_value_takes_priority(tmp_path, monkeypatch):
    """Direct value in yaml takes priority over env var."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        "llm:\n"
        '  api_key: "sk-direct-key"\n'
        "embedding:\n"
        '  api_key: "sk-direct-key"\n'
        "obsidian:\n"
        '  vault_path: "/tmp/test"\n'
    )
    config = load_config(config_file)
    assert config.llm.api_key == "sk-direct-key"
    assert config.embedding.api_key == "sk-direct-key"


def test_load_config_no_api_key_anywhere_raises(test_config_path, monkeypatch):
    """Error when api_key is not in config file and env var is also unset."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(Exception, match="api_key"):
        load_config(test_config_path)
