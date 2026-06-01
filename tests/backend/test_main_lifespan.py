import textwrap

from starlette.testclient import TestClient


def _write_settings(path, data_root):
    path.write_text(
        textwrap.dedent(
            f"""
            llm:
              base_url: "https://api.deepseek.com"
              api_key: "${{DEEPSEEK_API_KEY}}"
              model: "deepseek-v4-pro"
              enable_thinking: true
            embedding:
              base_url: "https://api.siliconflow.cn/v1"
              api_key: "${{SILICONFLOW_API_KEY}}"
              model: "Qwen/Qwen3-Embedding-8B"
            obsidian:
              vault_path: "{data_root}/obsidian"
            storage:
              data_root: "{data_root}"
              paper_root: "{data_root}/papers"
            pdf:
              parser_name: "pymupdf"
            arxiv:
              categories: ["cs.CL"]
            scheduler:
              collector_cron: "0 2 * * *"
              reporter_cron: "0 9 * * 1"
            """
        )
    )


def test_lifespan_starts_and_status_endpoint_works(tmp_path, monkeypatch):
    # PT_SCHEDULER=off so we exercise the full construction path without
    # actually starting APScheduler. Dummy keys: clients are constructed but
    # no network calls happen during startup.
    monkeypatch.setenv("PT_SCHEDULER", "off")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test")
    settings = tmp_path / "settings.yaml"
    _write_settings(settings, tmp_path)
    monkeypatch.setenv("SETTINGS_PATH", str(settings))

    from backend.main import create_app

    app = create_app()  # db=None -> real lifespan runs on ASGI startup
    with TestClient(app) as client:  # entering the context manager runs lifespan startup
        r = client.get("/api/pipeline/status")

    assert r.status_code == 200
    body = r.json()
    assert set(body["pending"].keys()) == {
        "pdf_fetch", "pdf_parse", "processor", "analyzer", "sync",
    }
    assert body["total_pending"] == 0  # fresh tmp DB


def test_lifespan_registers_collector_and_reporter(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_SCHEDULER", "off")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test")
    settings = tmp_path / "settings.yaml"
    _write_settings(settings, tmp_path)
    monkeypatch.setenv("SETTINGS_PATH", str(settings))

    from backend.api import deps
    from backend.main import create_app

    app = create_app()
    with TestClient(app):  # runs lifespan startup
        assert deps.get_collector() is not None
        assert deps.get_reporter() is not None
