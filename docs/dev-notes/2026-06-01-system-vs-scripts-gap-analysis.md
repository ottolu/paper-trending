# 2026-06-01 — 正式系统 vs scripts 差距分析与演进路线

> 背景：第一版系统 vibe 出来后，长期的测试/评估都堆在 `scripts/` 里，正式 `backend/`+`frontend/` 与脚本之间出现了明显漂移。本文盘点现状、定位差距、给出分阶段路线。原始盘点由三个并行 Explore 探子产出（scripts / backend+API / frontend），此处为综合结论。

## 一句话结论

核心能力**都实现了**，真正缺的是上面两层：**自动编排**和**对外暴露**。系统现在本质是"**手动脚本驱动的批处理 + 一个只读查询 API**"，还不是会自己跑的常规系统。

## 全景：每个能力卡在第几层

| 能力 | 实现 | 接进运行的 app | 有 API | 前端有 UI |
|---|:--:|:--:|:--:|:--:|
| collect / pdf_fetch / pdf_parse / processor | ✅ | ❌ 只脚本 | ❌ | ❌ |
| analyzer（LLM 分析+评分） | ✅ | ❌ 只脚本 | ❌ 无触发 | ✅ 展示结果 |
| sync（Obsidian 笔记） | ✅ | ❌ | ❌ | ❌ |
| reporter（周报：HDBSCAN 聚类+LLM） | ✅ | ❌ | ⚠️ 只读列表，**不能生成** | ✅ 列表/详情（裸文本） |
| backfill（历史回填） | ⚠️ 仅数据模型 | ❌ | ❌ | ❌ |
| semantic search | ✅ | ✅ endpoint 在线 | ✅ | ❌ **后端就绪、前端没入口** |
| stage retry / 运维 | ✅ | — | ✅ `/api/stages/retry` | ❌ |

## 三个差距（按杠杆从大到小）

### ① 最大：没有"自动编排"——系统不会自己跑
- `backend/scheduler/pipeline.py` 的 `PipelineRunner.tick()` 写好了，但**从没被实例化**。
- `backend/config/loader.py:SchedulerConfig` 的 cron（`collector_cron="0 2 * * *"`、`reporter_cron="0 9 * * 1"`）**被 parse 了却没人用**——没有任何调度器循环。
- `backend/main.py:lifespan` 只建 DB / Embedding / VectorStore，**不建任何 pipeline service、不建 LLMClient、不起后台任务**。
- 结果：app 启动后只伺候"已经算好的数据"，论文怎么进来全靠手动跑 `scripts/fetch_hf_weekly.py` 等。

👉 **好消息：骨架已经在了**（PipelineRunner / scheduler 配置 / 各 service 都按 `process_next` 模式写好），这是"接线激活"，不是从零写。

### ② 后端能力没暴露
- `ReporterService.generate_report()` 全实现了（聚类+LLM+markdown），但**没有 API 端点**调它。
- 没有 `POST /pipeline/tick`、`/reports/generate`、`/papers/{id}/analyze`、`/collect`。
- semantic search（`POST /api/search/semantic`）后端在线、但前端无入口（且依赖 analyzer 已写入 embedding）。

### ③ 前端 ~60–70%
现有：Dashboard、Papers 列表（搜索+score_min 筛选+分页）、PaperDetail（分析展示）、Reports（列表+裸文本）。
缺：语义搜索 UI、`score_breakdown` 可视化（数据取了没画）、tag/日期筛选、周报 markdown 渲染、jobs/pipeline 状态页、`evidence_citations` 展示、5 个排序里只暴露 2 个。

## scripts → backend：值得收编的能力

| 脚本 | 能力 | 该收编到哪 | 优先级 |
|---|---|---|---|
| `fetch_hf_weekly.py` | HF 采集（top-N by upvotes、排队 pdf_fetch） | `CollectorService.collect_hf_daily()` **每日**定时任务（top-15/天、只入新论文；weekly 只是早期 bootstrap） | 高 |
| `run_full_pipeline.py` | 端到端跑四 stage | `PipelineRunner` + 调度 | 高 |
| `retry_analyzer.py` / `retry_to_target.py` | 失败任务带退避重试 | ops 层，泛化到任意 stage | 中 |
| `batch_download_pdfs.py` | 批量补下 PDF | 并入 collector / pipeline | 中 |
| `eval_prompt.py` | 评测框架（多 prompt 版本+指标） | `backend/evaluation/`（评测变常规再说） | 中 |
| 其余 ~15 个 eval/ablation/debug/bench | 一次性研究/调试 | 归档 | 低 |

**关键洞察**：收编脚本 ≈ **激活后端已有的休眠编排层 + 把 HF 周采集逻辑搬进去**。主要是接线 + 搬家，不是重写。

⚠️ 已知坑（来自 CLAUDE.md）：`StageRunner.claim()` 的 SELECT→UPDATE 非原子，多 worker 并发会撞 `stage_run_attempts` UNIQUE。所以自动编排的 worker 循环**先串行驱动**（单 tick 串行 drain），并发化要等 claim 改原子（`UPDATE ... RETURNING`）。

## 演进路线（4 phase）

- **Phase 1（最高杠杆）让它自己跑**：APScheduler 接进 `lifespan`，实例化 `PipelineRunner` 按间隔 drain + **每日**采集（`CollectorService.collect_hf_daily`，top-15/天、复用已有 `HuggingFaceFetcher.fetch`）+ 每周出周报。→ 手动脚本 → 自动流水线。**详见 `docs/superpowers/plans/2026-06-01-phase1-automation-orchestration.md`**。
- **Phase 2 暴露能力**：`POST /pipeline/tick`、`/reports/generate`、`/papers/{id}/analyze`、jobs 状态；backfill 接执行引擎；retry 泛化成 ops 端点。
- **Phase 3 前端补齐**：语义搜索页、score_breakdown 可视化、tag/日期筛选、周报渲染、pipeline/jobs 状态页。
- **Phase 4 评测收敛 + 清理**：`eval_prompt` → `backend/evaluation/`；归档一次性 eval/debug 脚本；统一 LLMClient vs codex 的调用抽象。

## 当前状态校准（写给未来 session）

- 运行 `uvicorn backend.main:app` 起的是**只读查询 API**，不采集、不分析、不出报告。
- 数据进系统的唯一现实路径是手动跑 `scripts/`。
- LLM = DeepSeek V4 Pro 官方；Embedding = SiliconFlow（见 2026-06-01 迁移 dev-note）。
