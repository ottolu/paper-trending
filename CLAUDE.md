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
| PdfParser | `backend/pdf/parser.py` | PDF 全文提取（默认 pymupdf + 字号 heading，可切换 marker） |
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

## Important Rules

- **并行开发用 git worktree 隔离，别共用工作树**：当有另一个 session/进程正在这个仓库工作（或你要并行跑长任务、改半成品时被叫去做别的），**不要在主工作树里直接切分支/改文件**——`git checkout` 是原地覆盖同一个目录，两个 agent 会互相踩（曾踩过：一个 session `checkout` 到别的分支，另一个 session 脚下文件被换、改动被搅）。正确做法：`git worktree add -b <分支> ~/pt-<名字> <起点分支>` 开一个物理隔离目录，在里面 edit/commit/push/PR，完全不碰别人正在编辑的主树。用完 `git worktree remove <目录>`（删目录不删分支；分支单独 `git branch -d`）。worktree 共享同一 `.git`，分支/提交即时互见，比 clone 省空间。⚠️ 同一分支不能同时在两个 worktree checkout。worktree 目录放 `~/pt-xxx` 等持久位置，别放 `/tmp`（重启可能被清）。

- **论文分析必须基于 PDF 全文**：不能用 abstract-only 来分析论文。所有分析都需要先经过 PDF 解析（marker-pdf）提取全文，再送入 LLM 分析。abstract-only 模式只能用于快速预筛，不能作为最终分析依据。

- **研发过程中产出的经验必须落到 `docs/dev-notes/`**：以下场景结束后，必须写/更新 dev-note，不能只存在于对话里：
  - profiling / 性能基准对比（不同方案、不同模型、不同参数的量化结果）
  - prompt 迭代的 before/after 对比（score 分布、stdev、排名相关性、narrative 深度）
  - 发现的反直觉结论或系统性错位（比如 HF likes vs 学术评分错位）
  - 设计决策的理由与被拒绝的替代方案（为什么选 A 不选 B）
  - 踩坑 recipe（比如 V3.2 `reasoning_content` fallback、marker stdin 不兼容 multiprocessing）
  - 新组件或新 prompt 的选型建议表（什么场景用什么）
  - 文件名：`docs/dev-notes/YYYY-MM-DD-<topic>.md`
  - 一个主题一篇，完成就写，不攒；CLAUDE.md 里只留提炼后的规则/结论，原始数据留在 dev-note
  - 写完后在相关 CLAUDE.md 段落末尾加"详见 dev-note"指针，让未来 session 能找到
  - 触发词：用户让"总结经验"、"记录一下"、"出个对比"、"做 profiling"、"对比看看差异"、"记到 XX 里"等，大概率需要 dev-note

## LLM / Embedding 服务

⚠️ **2026-06 起 LLM 与 Embedding 是两个不同 provider**（旧 SiliconFlow key 曾硬编码进公开仓库被盗刷、已作废；详见 dev-note 2026-06-01-deepseek-v4-gpt55-migration）：

| 用途 | Provider | Base URL | 模型 | Key 环境变量 |
|------|----------|----------|------|------------|
| LLM（分析/评分） | DeepSeek 官方 | `https://api.deepseek.com` | `deepseek-v4-pro` | `${DEEPSEEK_API_KEY}` |
| Embedding | SiliconFlow | `https://api.siliconflow.cn/v1` | `Qwen/Qwen3-Embedding-8B` | `${SILICONFLOW_API_KEY}` |

- 配置在 `settings.yaml`；key 一律走环境变量（`.env.example` 是模板，`.env` 已 gitignore）。**绝不硬编码 key**——`hooks/pre-commit` 会扫 staged diff 拦截 `sk-…`/token（`git config core.hooksPath hooks` 已启用；新 clone 需重设）。
- 旧值（已弃用）：SiliconFlow `deepseek-ai/DeepSeek-V3.2` + `thinking_budget`；`deepseek-chat`/`deepseek-reasoner` 官方也将于 2026-07-24 弃用。

### LLMClient 注意事项（provider-aware）

`LLMClient` 按 base_url 自动判别 DeepSeek vs SiliconFlow：
- **DeepSeek 官方 thinking**：靠 `extra_body={"thinking":{"type":"enabled"}}` 开（V4 Pro 默认开），CoT 在 `reasoning_content`。⚠️ **thinking 模式不接受 `temperature`/`top_p`/`presence_penalty`/`frequency_penalty` 与 `response_format`**——`chat()` 对 DeepSeek thinking 路径会自动 strip 这些。
- **后果**：V4 Pro thinking 下评分**不能再用 `temperature=0`**，不再确定性。要确定性评分就设 `enable_thinking=false`（走 V4 Pro 非 thinking，temperature/response_format 恢复可用）。这是迁移引入的取舍，需按场景选。
- **SiliconFlow / Qwen**：仍走 `enable_thinking`/`thinking_budget` extra_body。
- `chat_json()` 的 `_extract_json()`（strip `<think>` → strip fences → brace-depth）足以应对 DeepSeek thinking 不支持 `response_format` 时的裸输出；内置 retry（max_retries=2）。
- **`reasoning_content` fallback 已合入 `chat()`**：`msg.content or getattr(msg, "reasoning_content", "") or ""`（之前只在评测脚本里，TODO 已消除）。

### GPT-5.5 via codex exec

- 旧 `gpt-5.4` 已升级为 `gpt-5.5`（本机 codex 默认 model 即 `gpt-5.5`，见 `~/.codex/config.toml`）。
- 两个独立 quota：OpenAI API key（`AsyncOpenAI`） vs ChatGPT 账户（`codex exec` OAuth）。用 codex OAuth token 走 API 会 429；生产跑 GPT 直接 `codex exec`，跳过 API 尝试省 ~30s/篇。

### ⚠️ 生产 LLM 接线现状（drift）

`backend/main.py` 的 `lifespan` **只初始化 DB/Embedding/VectorStore，不构造 LLMClient**——FastAPI app 本身不跑 analyzer。实际跑分析的是 `scripts/run_full_pipeline.py` / `retry_analyzer.py` / `retry_to_target.py`（各自直接构造 LLMClient，已切到 `deepseek-v4-pro` + `enable_thinking=True`）。所以"换模型"要同时改 `settings.yaml` 和这三个脚本。

### StageRunner 注意事项

- `claim()` 有 `max_attempts=5` 上限，超过后自动标记为 failed
- 重置失败任务时注意 `stage_run_attempts` 表的 UNIQUE 约束：`attempt_no` 必须大于已有记录
- ✅ **`claim()` 已并发安全（2026-06-01）**：用 `StageRunner._claim_lock`（`asyncio.Lock`）串行化 SELECT→UPDATE 临界区，多 worker 不再抢同一行。锁只罩快速 DB 段，LLM 慢调用在锁外，并发不受损（8 路 analyzer 实测 63s→8s/篇）。⚠️ **别改回 `UPDATE ... RETURNING`**：RETURNING 的结果集在单一共享 aiosqlite 连接上保持「语句进行中」，另一协程并发 `commit()` 会抛 IntegrityError/「statements in progress」崩溃（踩过）。`batch_download_pdfs.py` 仍用 try/except 吞异常静默丢任务，未改。详见 dev-note 2026-06-01-analyzer-benchmark-and-score-bug。

## PDF 解析

`PdfParser` 支持两种后端，通过 `settings.yaml` 的 `pdf.parser_name` 切换。**生产默认 `pymupdf`**：

| 方案 | 耗时（25页） | 何时用 |
|------|------------|--------|
| **pymupdf**（默认） | **~0.5s**（干净 25 页文本论文最好情况） | 批量解析、LLM 全文评测、绝大多数 arXiv 论文 |
| marker（可选） | ~4 分钟 | 需要精确表格/公式重建、扫描 PDF、需要 Layout 语义 |

⚠️ **批量实测远高于 ~0.5s 标称**：HF-top 语料偏大（median 27 页、可达 100+ 页 / 50MB 图多论文），120 篇实测 avg **2.7s/篇**、median 1.4s、p90 5.5s、max ~51s（5.5 min/120）。规模规划按 **~2.7s/篇** 算。注意 pymupdf 是 **CPU 单线程**，并发受 `claim()` 竞态限制需串行。详见 dev-note 2026-06-01-hf-weekly-pdf-ingest。

PyMuPDF 路径实现在 `PdfParser._run_pymupdf()`：
- 用字号统计识别 body size，超过 body+1.5pt 判定为 heading
- arXiv 原生 PDF 文本完整度 > 95%，heading 层级识别稳定
- 输出与 marker 一致：`fulltext.md` / `fulltext.txt` / `blocks.json` / `sections.json`

marker 路径仍然保留在 `PdfParser._run_marker()`，配置 `disable_ocr=True`：
- 首次调用需下载模型 (~2.6GB)，之后缓存在 `~/Library/Caches/datalab/`
- 不能通过 stdin heredoc 调用（multiprocessing 不兼容），必须用脚本文件
- 极端加速选项 `force_layout_block="Text"` 可跳过 Foundation 模型推理，但丢失 heading 结构
- 输出存储在 `data/papers/{paper_id}/extracted/{extraction_id}/`

### MPS 兼容性（marker 路径）

surya 在 Apple Silicon MPS 上有多个 `.item()`/`.max()` 返回垃圾值的 bug（PyTorch MPS kernel 问题）。`_patch_surya_mps()` 在 `parser.py` 中自动 patch surya 源码（仅在 marker 路径首次加载模型时触发）。**pip 升级 surya 后需重新触发 patch。** pymupdf 路径不受影响。

### 性能基准

| 方案 | 25 页耗时 | Layout 占比 |
|------|----------|------------|
| pymupdf | ~0.5s | — |
| marker 完整模式（MPS） | ~4 min | **Layout Recognition ~91%** |
| marker `force_layout_block="Text"` | ~8s | Layout 跳过 |

- Layout Recognition 是 marker 的主要瓶颈（Foundation 723M 参数 transformer）
- 调大 batch_size 在 MPS 上无收益（统一内存带宽瓶颈），默认值最优
- TableRec 不兼容 MPS 自动 fallback CPU，warning 可忽略

详细 profiling、三方对比数据、选型实测见 `docs/dev-notes/2026-04-20-paper-analysis-pipeline.md`。

### 新方案调研(2026-06-01,喂大模型精读场景)

- **对 arXiv 论文,最高杠杆是「别解析 PDF」**:~90% 有 LaTeX 源的论文直接走 arXiv 原生 HTML / ar5iv(公式=MathML+原始 LaTeX,表格/图从 TeX 源重建),消灭公式乱码/表格塌陷——这才是主路径,PDF 解析退化为 fallback。需逐篇质量门控(~83% HTML 带 warning/error 标记;ar5iv 滞后 live ~1 月,最新论文走 PDF)。
- **M2 实测(20 篇/528 页,2026-06-01)**:arXiv-HTML 在 HF 语料 **20/20 命中**;**所有 PDF 解析器的 markdown 都不吐 LaTeX 公式**(pymupdf/pymupdf4llm/docling 的公式代理全 <2)→ 公式密集纯 PDF 必须靠 MinerU。
- **PDF fallback 默认 pymupdf4llm**(5.8s/篇,878MB,表格强):实测比 Docling **3× 快、½ RAM、表格相当**;**只有要图占位/结构化 JSON 才上 Docling**(17.7s/篇,1.7GB,但能捕获图)。Docling **必须关 OCR**(默认对原生 PDF 跑 RapidOCR,慢数倍)。硬骨头/公式密集 → MinerU2.5(MLX,已装在 `.venv-mineru`,待跑)。
- **图/图表是所有解析器最弱环**:下游 Claude Opus 4.8 是多模态,**图单独抽成图片直接喂多模态 LLM**,别信解析器的图内文字。
- 未来上 M5 Max/Ultra:把 MinerU2.5(MLX VLM)提升为默认。
- bake-off harness `scripts/parser_bench.py`(可复现,`bench --parsers ...` 自动并入 RESULTS);数据 `data/parser_bench/`。MinerU/marker + Opus 裁判待补。详见 `docs/dev-notes/2026-06-01-pdf-parsing-options-research.md`。

## HuggingFace API

- Daily Papers API: `https://huggingface.co/api/daily_papers?date=YYYY-MM-DD`
- **Weekly**: 同端点支持 `?week=YYYY-Wnn`，返回该 ISO 周 ~50 篇且**已按 upvotes 降序**，结构同 daily（可复用 `parse_response`）。路径式 `/api/papers/week/<W>` 是 404。批量按周取 top-N 入库见 `scripts/fetch_hf_weekly.py`，详见 dev-note 2026-06-01。
- **likes 字段**: `paper.upvotes`（不是 `item.numLikes`）
- discussions 字段: `item.numComments`

## Prompt 优化经验

### 文件组织（2026-04-20 整理）

- **`backend/analyzer/prompts.py`** — 生产单一来源。fulltext-aware v3 变体，BARS 锚点 + weaknesses-first，`AnalyzerService` 唯一导入这个。
- **`backend/analyzer/prompts_v2.py`** — 历史评测基线（结构上与 prompts.py 不同），仅 `eval_prompt.py` 的版本注册表引用，用于复现老实验。
- **`backend/analyzer/prompts_v4.py`** — ICLR/CVPR peer-review 风格变体，6 段叙事 + `overall_rating`，仅评测脚本使用。
- **不要**再创建 `prompts_v3.py`：生产 `prompts.py` 就是 v3，版本号只用于评测对照变体。

### 关键结论

- `score_total` 不由 LLM 输出，Python 侧从 `score_breakdown` 算 = `round(mean(四项), 2)`（`backend/analyzer/service.py:score_total_from_breakdown`，与 `eval_prompt.py` 一致）。⚠️ 此前生产 `AnalyzerService` **漏了这步**（直接 `analysis.get("score_total",0)` → 恒 0.0），2026-06-01 已修并回填；同时补记 `analysis_model`/`prompt_version`。详见 dev-note 2026-06-01-analyzer-benchmark-and-score-bug。
- **analyzer 实测（deepseek-v4-pro thinking，8 篇全文、页数铺开）**：~63s/篇（与篇幅几乎无关，thinking 主导）、~36K tok/篇（输入随页数涨、输出稳定 ~2-3.5K）。纯网络型、本地 0% CPU；规模外推与并发取舍见同篇 dev-note。
- 子分数排序跨模型一致性高 (Spearman 0.75-0.90)，说明模型判断有意义
- HF likes 与学术质量弱相关 (Spearman ~0.1)，不适合作为评分 ground truth — 用双轨展示，见下文
- 评估工具在 `scripts/eval_prompt.py` 和 `scripts/eval_fulltext_*.py`

### 选型建议（20 篇全文评测实测）

| 场景 | 组合 | 特点 |
|------|------|------|
| 常规推荐（面向用户） | V3.2 × v3 | 温和，σ=2.98，80s/篇 |
| 精选榜单（严格筛选） | **GPT-5.4 × v4** | 最深 narrative（7.5 弱点/篇），偏 Reject |
| 成本敏感/快速通道 | GPT-5.4 × v3 | 35s/篇，最快 |

### Analysis basis 规则

- **abstract-only 禁用于最终分析**：系统性低估（均分 -2.6），信度只有 0.6
- **截断 30K 不安全**：和全文 Spearman 仅 0.505，约一半论文排序会变
- **全文模式必选**：差异化最强（σ 最大），能正确判断短论文/大 benchmark

### 评分 vs HF likes：双轨展示，不混合

- LLM 评分**只衡量论文内容本身的学术质量**（novelty/rigor/impact/clarity），不因作者机构、产品热度、HF likes 加分
- HF likes 作为**独立的社区兴趣信号**并列展示，不混入 `score_total`
- 不要做 ensemble 加权（如 `0.7×LLM + 0.3×log(likes)`）— 混合不同语义信号会让分数失去解释性
- 不要为 "product tech report" 类型加专属 rubric — 需要分类检测，破坏跨论文可比性
- 典型错位案例：字节 Seedance 2.0（HF likes=134，4 个评测组合都 Reject / Weak Reject）— 刻意不公开方法的产品 tech report 系统性低分是**正确行为**，详见 dev-note
- **2026-06 趋势分析实证双轨背离**：W19-W22 共 120 篇聚类后，学术热度榜与 HF likes 榜显著错位（如 Gamma-World 405↑/5.75 vs OSCAR 8.0/63↑），再次确认不可加权混合。聚类/趋势脚本 `scripts/trend_report.py`，详见 dev-note 2026-06-01-trend-clustering。

详细 profiling 与对比数据：`docs/dev-notes/2026-04-20-paper-analysis-pipeline.md`

## 趋势 / 聚类分析

`scripts/trend_report.py`：120 篇 → HDBSCAN(title+abstract 嵌入，mcs=3) → 双轨信号 → LLM 综合报告。⚠️ 两个 reporter 潜伏 bug（趋势脚本已绕过，未修）：`VectorStore.get()` 不接受 `include` 参数（`ReporterService.generate_report` 调用会 TypeError）；`ClusterService.run` 写 `cluster_runs` 需要 `embedding_versions` FK 行（缺则 FOREIGN KEY 失败）。Qwen3-Embedding 输出本就 L2 归一化。HDBSCAN 噪声当「新兴趋势候选」喂 LLM，别丢弃。详见 dev-note 2026-06-01-trend-clustering。

## Design Docs

- 设计文档: `docs/superpowers/specs/2026-04-12-llm-paper-tracker-design.md`
- 实现计划: `docs/superpowers/plans/` (Plan 1-9)
- Prompt 优化计划: `docs/prompt-optimization-plan.md`
- 开发笔记: `docs/dev-notes/`
