# CLAUDE.md

## Project Overview

Paper Trending: LLM 研究论文自动追踪、深度分析与趋势发现系统。后端 Python/FastAPI，前端 React/TypeScript。

## Quick Reference

```bash
# 后端测试
.venv/bin/pytest tests/ -v

# 代码检查
.venv/bin/ruff check .

# 启动后端
.venv/bin/uvicorn backend.main:app --reload --port 8000

# 前端开发
cd frontend && npm run dev

# 前端构建
cd frontend && npm run build
```

## Architecture

### Pipeline Stages

所有 service 通过 `stage_runs` 表驱动，按以下顺序执行：

```
collect → pdf_fetch → pdf_parse → processor → analyzer → sync
```

每个 service 实现 `process_next(worker_id) -> bool` 模式：
1. `stage_runner.claim(stage, worker_id)` 认领一条 pending 任务
2. 处理业务逻辑
3. `stage_runner.complete(run_id)` 标记成功，创建下一阶段的 stage_run
4. 失败时 `stage_runner.fail(run_id, error)` 记录错误

`PipelineRunner.tick()` 按 `STAGE_ORDER` 遍历所有阶段，驱动 `process_next()` 直到无待处理任务。

### Key Components

| 模块 | 路径 | 职责 |
|------|------|------|
| Database | `backend/core/database.py` | aiosqlite 异步封装，WAL + FK |
| StageRunner | `backend/core/stage_runner.py` | 任务状态机：create/claim/complete/fail/retry |
| LLMClient | `backend/core/llm_client.py` | OpenAI 协议的 chat/chat_json |
| EmbeddingClient | `backend/core/embedding_client.py` | OpenAI 协议的 embed |
| VectorStore | `backend/core/vector_store.py` | ChromaDB 持久化封装 |
| CollectorService | `backend/collectors/service.py` | arXiv/HuggingFace 采集 |
| PdfFetcher | `backend/pdf/fetcher.py` | PDF 下载 |
| PdfParser | `backend/pdf/parser.py` | marker-pdf 全文提取（OCR disabled, MPS patched） |
| ProcessorService | `backend/processor/service.py` | 分块 + 向量化 |
| AnalyzerService | `backend/analyzer/service.py` | LLM 深度分析 |
| ObsidianSyncService | `backend/sync/service.py` | 笔记写入 Obsidian vault |
| ReporterService | `backend/reporter/service.py` | HDBSCAN 聚类 + LLM 周报 |
| PipelineRunner | `backend/scheduler/pipeline.py` | 流水线调度 |
| BackfillService | `backend/scheduler/backfill.py` | 历史回填任务 |

### API Layer

FastAPI app 通过 `create_app(db=None)` 工厂函数创建：
- **生产环境:** `db=None`，使用 `lifespan` 从 `settings.yaml` 初始化 DB/Embedding/VectorStore
- **测试环境:** 传入 `db=<test_db>`，跳过 lifespan

依赖注入通过 `backend/api/deps.py` 的全局 getter/setter 管理（`get_db()`, `get_stage_runner()` 等）。

### Configuration

`backend/config/loader.py` 的 `load_config()` 加载 YAML 配置。API key 优先级：
1. 配置文件直接值
2. `${VAR}` 语法引用环境变量
3. 字段留空时自动读取 `OPENAI_API_KEY` 环境变量

## Coding Conventions

### Python

- **Ruff**: `line-length=100`, `target-version="py311"`
- **Import**: 使用 `from __future__ import annotations`
- **Async**: 所有 DB 操作和 service 方法都是 async
- **类型标注**: 用 `X | None` 而非 `Optional[X]`

### StageRunner Payload 注意事项

`StageRunner.create()` 存储 payload 时使用 `str(payload)` (Python repr)，不是 JSON。
读取时需要先尝试 `json.loads()`，失败后用 `ast.literal_eval()` 回退：

```python
try:
    payload = json.loads(payload_str)
except (json.JSONDecodeError, TypeError):
    payload = ast.literal_eval(payload_str)
```

### Testing

- **框架**: pytest + pytest-asyncio, `asyncio_mode = "auto"`
- **DB fixture**: 每个测试用 `tmp_path` 创建临时 SQLite
- **API 测试**: 用 `httpx.ASGITransport` 直接测试 FastAPI app，不启动真实服务器
- **FK 约束**: SQLite 开启了 `PRAGMA foreign_keys=ON`。删除有子记录的表行需先删子表（如 `stage_run_attempts` 在 `stage_runs` 之前）

标准 DB fixture 模式：
```python
@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()
```

### Frontend

- React 19 + TypeScript + Vite + TailwindCSS v4
- TanStack Query 管理数据获取
- React Router v6 路由
- `frontend/src/api.ts` 集中管理 API 调用
- Vite 配置 `/api` 代理到 `localhost:8000`

## Database

17 张表，定义在 `backend/core/schema.sql`。核心表：
- `papers` — 论文元数据 (id=arxiv_id)
- `stage_runs` / `stage_run_attempts` — 任务调度与执行记录
- `analysis_runs` — LLM 分析结果
- `weekly_reports` — 周报
- `backfill_jobs` / `backfill_job_days` — 回填任务追踪
- `sync_log` — Obsidian 同步记录（SHA256 校验幂等）

## LLM / Embedding 服务

当前使用 SiliconFlow（OpenAI 兼容 API）：
- **Base URL**: `https://api.siliconflow.cn/v1`
- **LLM**: `Qwen/Qwen3-VL-235B-A22B-Thinking`（thinking 模型，reasoning 内容在 `reasoning_content` 字段，不混入 `content`）
- **Embedding**: `Qwen/Qwen3-Embedding-8B`
- **限流**: TPM 限制较严格，full-text 分析（每篇 10-60K tokens）时必须控制并发（建议 concurrency=1 + 间隔 5-10s）
- **配置**: `settings.yaml`（已 gitignore）

### LLMClient 注意事项

- `chat_json()` 内置 `_extract_json()`：strip `<think>` blocks → strip markdown fences → brace-depth JSON 提取
- 内置 retry（max_retries=2）
- `response_format: {"type": "json_object"}` 与 Qwen3-Thinking 兼容，不需要移除
- 评分分析调用必须设 `temperature=0`

### StageRunner 注意事项

- `claim()` 有 `max_attempts=5` 上限，超过后自动标记为 failed
- 重置失败任务时注意 `stage_run_attempts` 表的 UNIQUE 约束：`attempt_no` 必须大于已有记录

## PDF 解析

使用 marker-pdf (v1.10.2) + surya-ocr (v0.17.1)，配置 `disable_ocr=True`（arXiv PDF 是数字原生，不需要 OCR）：
- 首次调用需下载模型 (~2.6GB)，之后缓存在 `~/Library/Caches/datalab/`
- `asyncio.to_thread()` 包装（CPU 密集型同步操作）
- 不能通过 stdin heredoc 调用（multiprocessing 不兼容），必须用脚本文件
- 输出存储在 `data/papers/{paper_id}/extracted/{extraction_id}/fulltext.md`

### MPS 兼容性

surya 在 Apple Silicon MPS 上有多个 `.item()`/`.max()` 返回垃圾值的 bug（PyTorch MPS kernel 问题）。
`_patch_surya_mps()` 在 `parser.py` 中自动 patch surya 源码。**pip 升级 surya 后需重新触发 patch。**

### 性能基准（M5 24GB, 17页 PDF）

| 模式 | 每页速度 | 说明 |
|------|---------|------|
| CPU | 12.8s/页 | 无需 patch |
| MPS (patch 后) | 5.6-6.5s/页 | 生产使用，约 2x 提速 |

- Layout Recognition 占总耗时 ~70%，是主要瓶颈
- 调大 batch_size 在 MPS 上无收益（统一内存带宽瓶颈），默认值最优
- TableRec 不兼容 MPS 自动 fallback CPU，warning 可忽略

## HuggingFace API

- Daily Papers API: `https://huggingface.co/api/daily_papers?date=YYYY-MM-DD`
- **likes 字段**: `paper.upvotes`（不是 `item.numLikes`）
- discussions 字段: `item.numComments`

## Prompt 优化经验

评分 prompt 经过 v1→v2→v3 三轮迭代 + 跨模型验证（Qwen3 vs GPT-5.4），关键发现：
- 当前 prompt 在 `backend/analyzer/prompts.py`（v3，带 BARS 锚点 + weaknesses-first）
- `score_total` 不由 LLM 输出，在 Python 侧从 `score_breakdown` 子分数计算
- Qwen3 的 rigor/clarity 子分数存在系统性虚高（几乎全给 8），GPT-5.4 更有区分度
- 子分数排序跨模型一致性高 (Spearman 0.6-0.7)，说明模型判断有意义
- HF likes 与学术质量弱相关 (Spearman ~0.1)，不适合作为评分 ground truth
- 评估工具和历史结果在 `scripts/eval_prompt.py` 和 `data/eval_results/`

## Design Docs

- 设计文档: `docs/superpowers/specs/2026-04-12-llm-paper-tracker-design.md`
- 实现计划: `docs/superpowers/plans/` (Plan 1-9)
- Prompt 优化计划: `docs/prompt-optimization-plan.md`
