# LLM 论文追踪与趋势分析系统 — 设计文档

> 日期: 2026-04-12
> 状态: Draft v2

## 1. 目标与范围

构建一个面向大模型研发领域的个人论文追踪工具，实现：

- **每日论文采集**：从 arXiv、HuggingFace Papers 持续采集大模型相关论文
- **历史回溯**：将最近 3-6 个月的论文批量入库
- **PDF 下载与内容抽取**：下载论文 PDF，进行存储、版本管理、全文解析和可追溯内容抽取
- **LLM 深度阅读分析**：基于标题、摘要、元数据和 PDF 提取全文，对每篇论文生成结构化摘要、评分、自动标签和领域归类
- **Obsidian 知识同步**：按日期层级组织，生成中文 Note，通过 Tag 实现跨时间领域检索
- **每周趋势报告**：基于领域聚类和时间窗口做趋势判断，而非单篇论文简单罗列
- **Web UI**：提供浏览、搜索、趋势可视化和任务管理界面

### 1.1 设计边界

- 第一版**包含 PDF 全文解析与内容提取**
- 分析输出必须区分证据基础：
  - **元数据级事实**：标题、作者、发布日期、分类、来源信号
  - **全文级事实**：可从 PDF 正文、章节、图表标题、参考文献中直接定位
  - **模型推断**：LLM 基于全文阅读做出的总结、对比和归因
- 所有深入分析字段都应保留：
  - `analysis_basis = abstract_only / full_text`
  - `evidence_citations`
  - `confidence`

### 1.2 不在范围内

- 多用户/权限管理
- 移动端适配

## 2. 系统架构

### 2.1 核心理念

系统由 8 个服务 + 1 个共享数据层 + 1 个 Web 应用组成，但 v2 明确采用以下约束：

1. **论文事实数据与执行状态分离**
   `papers` 只表示论文实体；流程推进由独立的阶段任务表驱动，不再依赖单一 `papers.status` 串联所有环节。
2. **任务执行可抢占、可恢复、可幂等**
   所有后台服务都只能通过原子领取任务运行，必须记录 lease、attempt、last_error 和 idempotency key。
3. **PDF 资产与解析结果持久化管理**
   PDF 必须下载到本地受控目录，记录 checksum、来源 URL、版本、解析产物和解析引擎版本，支持重试与重解析。
4. **聚类与向量结果版本化**
   embedding 版本、聚类版本、周报版本必须显式持久化，历史输出不可被后续重跑 silently 覆盖。
5. **Reporter 只基于“已分析完成”的事实集工作**
   周报查询依据 `paper_analysis.active_analyzed_at` 和稳定的 `cluster_run_id`，不复用同步状态。

### 2.2 架构图

```
┌────────────────────────────────────────────────────────────────────────────┐
│                               共享数据层                                    │
│ SQLite (结构化元数据 / 任务 / 报表) + ChromaDB (按版本隔离的向量集合)        │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ① Collector        每日定时 + 手动       采集论文元数据，创建/更新 paper 实体 │
│  ② PDF Fetcher      轮询任务队列         下载 PDF，做文件落盘与校验            │
│  ③ PDF Parser       轮询任务队列         提取全文、章节、块、页码映射          │
│  ④ Processor        轮询任务队列         清洗、归一、去重，产出阅读输入         │
│  ⑤ Analyzer         轮询任务队列         LLM 深度阅读、embedding、临时归类     │
│  ⑥ Obsidian Sync    轮询任务队列         生成 Note / 日报 / 周报写入 Vault      │
│  ⑦ Reporter         每周定时 + 手动       生成稳定 cluster run 与周报           │
│  ⑧ Backfiller       手动触发             历史回溯，按日切片推进                  │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  ⑨ API Server + Web UI                                                     │
│     浏览论文 / 搜索 / 查看趋势 / 查看任务 / 手动触发任务 / 仪表盘            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 状态模型

#### 论文实体状态

`papers` 不再承担流程编排语义，只表示“系统是否已认识这篇论文”。

#### 阶段任务状态

所有执行阶段统一使用任务状态机：

- `pending`
- `running`
- `succeeded`
- `failed`
- `cancelled`

每个阶段任务还必须记录：

- `attempt_no`
- `worker_id`
- `lease_expires_at`
- `idempotency_key`
- `last_error`
- `last_error_at`

#### 同步状态

Obsidian 是否已同步通过 `sync_log` 和 `stage_runs(stage='sync')` 判断，不再覆盖分析完成状态。

#### PDF 资产状态

PDF 生命周期由以下阶段任务表达：

- `pdf_fetch`
- `pdf_parse`

其中：

- `pdf_fetch.succeeded` 表示 PDF 已成功下载并完成 checksum 校验
- `pdf_parse.succeeded` 表示已产出可供 Analyzer 消费的结构化全文结果

### 2.4 每日流程

```
Cron 触发 Collector
    → upsert papers / paper_sources
    → 为新论文创建 pdf_fetch 任务 (pending)
        → PDF Fetcher 原子领取任务并下载 PDF
            → 写入 paper_files / succeeded
            → 创建 pdf_parse 任务 (pending)
                → PDF Parser 原子领取任务
                    → 写入 pdf_extractions / succeeded
                    → 创建 processor 任务 (pending)
                        → Processor 原子领取任务并清洗/归一
                            → 写回 papers 标准化字段 / succeeded
                            → 创建 analyzer 任务 (pending)
                                → Analyzer 原子领取任务
                                    → 基于摘要 + PDF 全文阅读生成 paper_analysis
                                    → 写入 paper_embeddings 到当前 embedding version
                                    → 生成 provisional cluster assignment
                                    → 创建 sync 任务 (pending)
                                        → Obsidian Sync 原子领取任务
                                            → 写单篇 Note / 日报
                                            → 记录 sync_log
```

### 2.5 每周流程

```
Cron 触发 Reporter
    → 读取本周 analyzed_at 落在窗口内的论文
    → 基于当前 active embedding version 执行 full cluster run
    → 生成 cluster version / assignment snapshot
    → 对比上周 stable cluster run 做趋势分析
    → 生成 weekly_report
    → 创建 weekly_summary sync 任务
```

Reporter 的输入条件是：

- `paper_analysis.active_analyzed_at` 在统计窗口内
- 存在对应的 analyzer `stage_runs(status='succeeded')`
- 使用指定的 `cluster_run_id`

不依赖 `sync` 是否完成。

## 3. 数据源

| 数据源 | 获取方式 | 提供的信号 |
|--------|---------|-----------|
| **arXiv** | arXiv API (OAI-PMH / REST) | 论文元数据、摘要、PDF 链接、分类 |
| **HuggingFace Papers** | HF Daily Papers 页面抓取/API | 社区 likes、讨论数、热度排名 |

### 3.1 采集策略

- **arXiv 为主源**：按 `cs.CL`, `cs.AI`, `cs.LG` 等相关分类每日拉取新论文
- **HuggingFace 为补充**：获取社区热度信号，通过 arXiv ID 优先关联，标题匹配仅作为降级策略
- **Backfiller**：按时间窗口批量回溯 3-6 个月历史数据，支持断点续传

### 3.2 多源关联规则

- 优先使用 `arxiv_id` 精确关联
- 若只有标题可用，则记录：
  - `match_strategy = exact_title / fuzzy_title`
  - `match_confidence`
  - `source_record_id`
- 标题模糊匹配命中的条目默认进入人工可审查队列，不直接写入高置信统计

### 3.3 PDF 获取原则

- 默认优先下载 arXiv 官方 PDF
- 若存在多个 PDF 源，记录 source priority，避免覆盖已有已校验文件
- 每次下载都必须记录：
  - 原始 URL
  - HTTP 状态
  - 文件大小
  - SHA256 checksum
  - 下载时间
- 相同 checksum 的 PDF 视为同一文件版本，不重复存储

## 4. 数据模型

### 4.1 SQLite 表结构

#### papers（论文主表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 系统内部 paper_id，优先使用 arXiv ID |
| arxiv_id | TEXT UNIQUE NULLABLE | arXiv ID |
| title | TEXT | 论文标题 |
| authors | JSON | 作者列表 |
| abstract | TEXT | 摘要 |
| arxiv_categories | JSON | arXiv 分类列表 |
| published_date | DATE | 论文发布日期 |
| first_seen_at | DATETIME | 系统首次见到该论文 |
| updated_at | DATETIME | 更新时间 |

#### paper_sources（论文来源信号）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| paper_id | TEXT FK | 关联论文 |
| source_name | TEXT | arxiv / huggingface |
| source_url | TEXT | 来源链接 |
| source_record_id | TEXT | 来源侧主键 |
| match_strategy | TEXT | arxiv_id / exact_title / fuzzy_title |
| match_confidence | FLOAT | 0-1 |
| hf_likes | INTEGER | HuggingFace 点赞数 |
| hf_discussions | INTEGER | HuggingFace 讨论数 |
| collected_at | DATETIME | 采集时间 |

#### paper_files（PDF 文件资产）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| paper_id | TEXT FK | 关联论文 |
| file_type | TEXT | pdf |
| source_url | TEXT | 下载来源 URL |
| storage_path | TEXT | 本地存储路径 |
| file_size_bytes | INTEGER | 文件大小 |
| sha256 | TEXT | 文件哈希 |
| mime_type | TEXT | `application/pdf` |
| is_current | BOOLEAN | 是否当前生效文件版本 |
| download_status | TEXT | pending / downloaded / failed / superseded |
| downloaded_at | DATETIME | 下载完成时间 |
| verified_at | DATETIME | 校验时间 |

约束：

- `UNIQUE(paper_id, sha256)`
- 同一篇论文任意时刻只能有一个 `is_current = true`

#### pdf_extractions（PDF 解析结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| paper_id | TEXT FK | 关联论文 |
| paper_file_id | INTEGER FK | 对应 PDF 资产 |
| parser_name | TEXT | 解析引擎名 |
| parser_version | TEXT | 解析引擎版本 |
| extraction_status | TEXT | pending / succeeded / failed / partial |
| page_count | INTEGER | 页数 |
| extraction_root_path | TEXT | 本次解析产物根目录 |
| extracted_text_path | TEXT | 提取全文文本路径 |
| extracted_markdown_path | TEXT | 结构化 Markdown 路径 |
| blocks_json_path | TEXT | 块级结构与页码映射路径 |
| sections_json_path | TEXT | 章节结构路径 |
| figures_json_path | TEXT | 图标题/表标题提取结果 |
| references_json_path | TEXT | 参考文献提取结果 |
| parse_quality_score | FLOAT | 0-1，解析质量评分 |
| extracted_at | DATETIME | 提取完成时间 |

约束：

- 每次重解析必须创建新的 `pdf_extractions` 记录
- 解析产物目录不可变，不允许覆盖历史 extraction 文件

#### stage_runs（阶段任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| target_type | TEXT | paper / report |
| target_id | TEXT | 对应 paper_id 或 report_id |
| stage | TEXT | pdf_fetch / pdf_parse / processor / analyzer / sync |
| status | TEXT | pending / running / succeeded / failed / cancelled |
| logical_job_key | TEXT | 逻辑任务唯一键 |
| attempt_no | INTEGER | 当前尝试次数 |
| worker_id | TEXT | 执行 worker 标识 |
| lease_expires_at | DATETIME | 任务租约过期时间 |
| idempotency_key | TEXT | 幂等键 |
| payload_json | JSON | 阶段输入参数快照 |
| last_error | TEXT | 最近一次错误 |
| last_error_at | DATETIME | 最近错误时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

约束：

- `UNIQUE(logical_job_key)`
- 所有 worker 只能通过原子 claim 将 `pending -> running`
- retry 不创建新的逻辑任务，而是针对已有 `stage_run_id` 创建新的 attempt

#### stage_run_attempts（阶段执行尝试）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| stage_run_id | INTEGER FK | 对应逻辑任务 |
| attempt_no | INTEGER | 第几次尝试 |
| status | TEXT | running / succeeded / failed / cancelled |
| worker_id | TEXT | 执行 worker |
| lease_expires_at | DATETIME | 当前租约 |
| input_hash | TEXT | 本次 attempt 输入快照哈希 |
| started_at | DATETIME | 开始时间 |
| finished_at | DATETIME | 结束时间 |
| error_message | TEXT | 失败原因 |

约束：

- `UNIQUE(stage_run_id, attempt_no)`

#### analysis_runs（版本化分析结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| paper_id | TEXT FK | 关联论文 |
| paper_file_id | INTEGER FK | 使用的 PDF 文件版本 |
| pdf_extraction_id | INTEGER FK | 使用的解析结果版本 |
| chunk_manifest_path | TEXT | Analyzer 消费的 chunk 清单路径 |
| chunk_manifest_hash | TEXT | chunk 清单哈希 |
| input_hash | TEXT | 整体分析输入哈希 |
| factual_summary | TEXT | 基于摘要可直接抽取的事实摘要（中文） |
| methodology_inference | TEXT | 对方法的推断性总结（中文） |
| innovation_points | JSON | 创新点列表（中文） |
| key_takeaways | JSON | 关键结论列表（中文） |
| score_total | FLOAT | 综合评分 (0-10) |
| score_breakdown | JSON | 创新性/影响力/严谨性/实用性分项评分 |
| tags | JSON | 自动标签，如 `training/rlhf` |
| evidence_level | TEXT | factual / mixed / inferential |
| analysis_basis | TEXT | abstract_only / full_text |
| evidence_citations | JSON | 页码/章节/段落级引用 |
| confidence | FLOAT | 0-1 |
| analysis_model | TEXT | 分析模型名 |
| prompt_version | TEXT | Prompt 版本 |
| status | TEXT | pending / succeeded / failed |
| analyzed_at | DATETIME | 分析完成时间 |

#### paper_analysis（当前活跃分析投影）

| 字段 | 类型 | 说明 |
|------|------|------|
| paper_id | TEXT PK/FK | 关联论文 |
| active_analysis_run_id | INTEGER FK | 当前活跃分析版本 |
| active_paper_file_id | INTEGER FK | 当前分析绑定的 PDF 版本 |
| active_pdf_extraction_id | INTEGER FK | 当前分析绑定的解析版本 |
| active_analyzed_at | DATETIME | 当前活跃分析完成时间 |

#### embedding_versions（向量版本）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| provider | TEXT | openai / ollama / other |
| model | TEXT | embedding 模型名 |
| dimension | INTEGER | 向量维度 |
| collection_name | TEXT | Chroma collection 名称 |
| is_active | BOOLEAN | 当前是否为活跃版本 |
| created_at | DATETIME | 创建时间 |

#### cluster_runs（聚类运行）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| run_type | TEXT | daily_provisional / weekly_stable |
| embedding_version_id | INTEGER FK | 所属 embedding 版本 |
| window_start | DATE | 统计窗口起始 |
| window_end | DATE | 统计窗口结束 |
| paper_count | INTEGER | 输入论文数 |
| algorithm_name | TEXT | hdbscan |
| algorithm_version | TEXT | 聚类实现版本 |
| cluster_params_json | JSON | 聚类参数 |
| input_snapshot_path | TEXT | 输入论文集合快照路径 |
| input_snapshot_hash | TEXT | 输入快照哈希 |
| code_version | TEXT | 代码版本标识 |
| is_stable | BOOLEAN | 是否可用于报表/UI |
| created_at | DATETIME | 创建时间 |

#### cluster_entities（稳定领域实体）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 稳定领域 ID，例如 `domain_alignment` |
| first_seen_run_id | INTEGER FK | 首次出现在哪次 stable run |
| current_name | TEXT | 当前显示名称（中文） |
| current_description | TEXT | 当前描述（中文） |
| current_parent_id | TEXT FK NULLABLE | 当前父领域 |
| status | TEXT | active / merged / retired |
| updated_at | DATETIME | 更新时间 |

#### cluster_versions（领域版本快照）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| cluster_entity_id | TEXT FK | 稳定领域实体 |
| cluster_run_id | INTEGER FK | 对应聚类运行 |
| name | TEXT | 当期名称 |
| description | TEXT | 当期描述 |
| parent_cluster_entity_id | TEXT FK NULLABLE | 当期父领域 |
| change_type | TEXT | new / unchanged / renamed / merged / split |
| created_at | DATETIME | 创建时间 |

#### paper_cluster_assignments（论文领域归属）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| paper_id | TEXT FK | 关联论文 |
| cluster_run_id | INTEGER FK | 对应聚类运行 |
| cluster_version_id | INTEGER FK | 对应领域版本 |
| assignment_type | TEXT | provisional / stable |
| similarity_score | FLOAT | 归属置信度 |
| assigned_at | DATETIME | 归属时间 |

#### weekly_reports（周报）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| week_start | DATE | 周起始日 |
| week_end | DATE | 周结束日 |
| cluster_run_id | INTEGER FK | 本周绑定的 stable cluster run |
| analysis_run_ids_json | JSON | 本次报告消费的 analysis run IDs |
| input_snapshot_path | TEXT | 报告输入快照路径 |
| input_snapshot_hash | TEXT | 报告输入快照哈希 |
| report_model | TEXT | 报告生成模型 |
| report_prompt_version | TEXT | 报告 prompt 版本 |
| supersedes_report_id | INTEGER FK NULLABLE | 若为重跑，指向被替代的旧周报 |
| is_current | BOOLEAN | 当前窗口下是否为活跃周报 |
| report_content | TEXT | Markdown 格式趋势报告（中文） |
| highlights | JSON | 本周推荐论文 IDs |
| created_at | DATETIME | 生成时间 |

#### sync_log（Obsidian 同步记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| paper_id | TEXT FK NULLABLE | 单篇 Note 对应 paper_id |
| report_id | INTEGER FK NULLABLE | 周报对应 weekly_report |
| sync_type | TEXT | paper_note / daily_summary / weekly_summary |
| logical_target | TEXT | `paper:{paper_id}` / `report:{report_id}` / `daily:{date}` |
| file_path | TEXT | Obsidian 中的文件路径 |
| checksum | TEXT | 内容哈希 |
| synced_at | DATETIME | 同步时间 |

#### backfill_jobs（历史回溯任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| range_start | DATE | 回溯开始日期 |
| range_end | DATE | 回溯结束日期 |
| cursor_date | DATE | 当前已完成到的日期 |
| status | TEXT | pending / running / succeeded / failed / cancelled |
| attempt_no | INTEGER | 尝试次数 |
| worker_id | TEXT | 执行 worker |
| lease_expires_at | DATETIME | 租约时间 |
| last_error | TEXT | 最近错误 |
| cursor_semantics | TEXT | fixed_closed_day，表示该日期所有终态阶段已完成 |
| updated_at | DATETIME | 更新时间 |

#### backfill_job_days（按日回填 checkpoint）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| backfill_job_id | INTEGER FK | 对应 backfill 任务 |
| work_date | DATE | 回填日期 |
| collect_status | TEXT | pending / running / succeeded / failed |
| pdf_fetch_status | TEXT | pending / running / succeeded / failed |
| pdf_parse_status | TEXT | pending / running / succeeded / failed |
| processor_status | TEXT | pending / running / succeeded / failed |
| analyzer_status | TEXT | pending / running / succeeded / failed |
| sync_status | TEXT | pending / running / succeeded / failed |
| is_terminal | BOOLEAN | 当日链路是否已闭合 |
| updated_at | DATETIME | 更新时间 |

### 4.2 ChromaDB 向量集合

- collection 采用版本隔离命名：`paper_embeddings_v{embedding_version_id}`
- 每条向量 metadata 至少包含：
  - `paper_id`
  - `analysis_basis`
  - `embedding_version_id`
  - `analysis_model`
  - `analyzed_at`
- **切换 embedding 模型时必须创建新的 `embedding_versions` 记录**
- 新模型切换为 active 前，必须完成全量 re-embed；不同版本向量禁止混查、混聚类

### 4.3 本地文件存储组织

PDF 及其解析产物统一落到受控目录，避免散落写入：

```text
data/
├── papers/
│   └── {paper_id}/
│       ├── metadata/
│       │   └── source.json
│       ├── files/
│       │   ├── current.pdf -> ./versions/{sha256}.pdf
│       │   └── versions/
│       │       └── {sha256}.pdf
│       ├── extracted/
│       │   └── {extraction_id}/
│       │       ├── fulltext.txt
│       │       ├── fulltext.md
│       │       ├── blocks.json
│       │       ├── sections.json
│       │       ├── figures.json
│       │       └── references.json
│       └── cache/
│           └── {chunk_manifest_hash}.json
```

约束：

- `paper_id` 目录是单篇论文的唯一根目录
- 原始 PDF 与解析产物分目录存放
- PDF 必须按 checksum 版本化存储，禁止覆盖旧版本文件
- 解析产物必须按 `extraction_id` 版本化存储，禁止覆盖旧版本文件
- 文件重命名不影响 DB，只通过 `storage_path` 追踪
- 若下载到新版本 PDF，必须新建 `paper_files` 记录，并触发重新解析
- `current.pdf` 只是便捷指针，数据库中的 `paper_files.is_current` 才是唯一权威来源

## 5. 模块详细设计

### 5.1 Collector（采集器）

- **触发**：每日 cron（建议北京时间凌晨，覆盖 arXiv 前一日更新窗口） + 手动
- **流程**：
  1. 按配置的 arXiv 分类列表拉取时间窗口内的新论文
  2. 拉取 HuggingFace Daily Papers 热度信息
  3. 以 arXiv ID 优先、标题匹配兜底的策略关联两源
  4. `upsert` 到 `papers` 和 `paper_sources`
  5. 对首次入库或 PDF 缺失的论文创建 `stage_runs(stage='pdf_fetch', target_type='paper')`
- **幂等要求**：
  - `paper_id + stage + logical_input_hash` 构成幂等键
  - 同一时间窗口的重复 Collector 执行不得创建重复论文或重复任务

### 5.2 PDF Fetcher（PDF 下载器）

- **触发**：轮询 `stage_runs(stage='pdf_fetch', target_type='paper', status='pending')`
- **流程**：
  1. 原子领取任务
  2. 根据 `paper_sources` 选择 PDF URL
  3. 下载 PDF 到临时路径，校验后原子移动到 `data/papers/{paper_id}/files/versions/{sha256}.pdf`
  4. 校验 mime type、文件大小、checksum
  5. 以 `(paper_id, sha256)` 做幂等 upsert，写入 `paper_files`
  6. 标记任务为 `succeeded`
  7. 创建 `pdf_parse` 任务
- **失败策略**：
  - 支持重试与断点续传下载
  - 若 PDF 不可获取，可降级创建 `processor` 任务，后续 Analyzer 结果必须标注 `analysis_basis = abstract_only`

### 5.3 PDF Parser（PDF 解析器）

- **触发**：轮询 `stage_runs(stage='pdf_parse', target_type='paper', status='pending')`
- **流程**：
  1. 原子领取任务
  2. 对 PDF 做文本提取与结构分析
  3. 产出：
     - 全文纯文本
     - Markdown 结构化正文
     - page/block 映射
     - 章节树
     - 图表标题和参考文献索引
  4. 计算解析质量分
  5. 写入 `pdf_extractions`，并把产物写入 `extracted/{extraction_id}/`
  6. 标记任务为 `succeeded`
  7. 创建 `processor` 任务
- **解析结果要求**：
  - 必须保留页码映射，便于 LLM 输出引用
  - 允许 `partial` 成功，但 Analyzer 需降级处理缺失块

### 5.4 Processor（处理器）

- **触发**：轮询 `stage_runs(stage='processor', target_type='paper', status='pending')`
- **流程**：
  1. 原子领取一批任务，写入 `running + worker_id + lease_expires_at`
  2. 清洗与标准化（作者名归一、分类映射、来源信号归一）
  3. 读取当前活跃 `pdf_extractions`，将全文切分为可供 LLM 消费的阅读 chunk
  4. 组装阅读输入：
     - metadata
     - abstract
     - full text chunks
     - section map
     - figure/reference index
     - `chunk_manifest_hash`
  5. 进行去重判断：
     - arXiv ID 相同直接合并
     - 仅标题相似命中时，保留低置信来源记录，不直接覆盖主记录
  6. 标记任务为 `succeeded`
  7. 创建 `analyzer` 任务

### 5.5 Analyzer（分析器）

- **触发**：轮询 `stage_runs(stage='analyzer', target_type='paper', status='pending')`
- **流程**：
  1. 原子领取任务
  2. 基于摘要 + PDF 全文 chunk 做多轮阅读和归纳
  3. 调用 LLM 生成结构化输出：
     - `factual_summary`
     - `methodology_inference`
     - `innovation_points`
     - `key_takeaways`
     - `score_breakdown`
     - `tags`
     - `analysis_basis`
     - `evidence_citations`
     - `evidence_level`
     - `confidence`
  4. 先写入 `analysis_runs`
  5. 再刷新 `paper_analysis` 当前活跃投影
  6. 使用当前 active `embedding_version` 生成向量
  7. 对最新 stable cluster run 做 `approximate_predict`，生成 **provisional** assignment
  8. 标记 analyzer 任务为 `succeeded`
  9. 创建 `sync` 任务

### 5.6 聚类策略

- 不预设领域分类，由 embedding 分布驱动
- 使用 HDBSCAN，但要区分两类结果：
  - **日常 provisional assignment**
    只用于让新论文在 UI/Note 中暂时归类，不视为最终趋势基准
  - **每周 stable cluster run**
    Reporter 对指定窗口 + 全量可用向量执行 HDBSCAN，生成可复现的 stable snapshot
- `approximate_predict` 仅表示“贴近现有稳定簇”的近似归属，**不等价于在线更新 HDBSCAN 模型**
- 每次 stable cluster run 后，由 LLM 审视 cluster 分布：
  - 为新 cluster 建立 `cluster_entity`
  - 对 renamed / merged / split 做 `cluster_versions.change_type` 标记
- 每次 stable cluster run 必须冻结：
  - 输入论文集合
  - 聚类参数
  - 算法版本
  - 代码版本

### 5.6.1 Reporter / Cluster Rerun 语义

- 同一周窗口允许 rerun，但 rerun 必须：
  - 生成新的 `cluster_run`
  - 生成新的 `weekly_report`
  - 将旧周报标记为 `is_current = false`
  - 在新周报中通过 `supersedes_report_id` 指向旧周报
- UI 默认只展示 `is_current = true` 的周报；历史版本可在详情页查看

### 5.7 Obsidian Sync（知识同步）

- **触发**：轮询 `stage_runs(stage='sync', status='pending')`
- **输出**：直接写 Markdown 文件到 Obsidian Vault
- **归档口径**：
  - 单篇 Note 和日报按 **系统采集日期** 放入对应日目录
  - Note frontmatter 中单独保留 `published_date`
  - 周报按自然周归档

#### 文件夹结构

```
LLM-Research/
├── 2026-W15/
│   ├── W15-weekly-summary.md
│   ├── 2026-04-07/
│   │   ├── 2026-04-07-daily.md
│   │   ├── paper-title-a.md
│   │   └── ...
│   └── ...
└── 2026-W16/
    └── ...
```

#### 单篇 Note 模板（中文）

```markdown
---
tags: [training/rlhf, alignment, llm]
score: 8.5
arxiv: "2026.xxxxx"
published_date: 2026-04-05
collected_date: 2026-04-07
evidence_level: mixed
confidence: 0.78
---
# 论文标题

## 事实摘要
...（可从摘要或正文直接支持）

## 推断性方法总结
...（基于全文阅读推断）

## 创新点
- ...

## 关键结论
- ...

## 证据引用
- p.3 §2.1: ...
- p.7 Figure 2: ...

## 链接
- arXiv: ...
- HuggingFace: ...
```

#### 日总结模板（中文）

```markdown
# 2026-04-07 论文日报

今日采集 **15** 篇，完成分析 **12** 篇，高分文章 **3** 篇

## 高分文章
- [[paper-title-a]] (9.2) — 一句话概要 #training/rlhf
- [[paper-title-b]] (8.8) — 一句话概要 #inference/speculative-decoding

## 全部文章
| 论文 | 评分 | 暂定领域 | 阅读基础 | 证据级别 |
|------|------|----------|----------|----------|
| [[paper-title-a]] | 9.2 | #training/rlhf | full_text | mixed |
| ... | ... | ... | ... | ... |
```

#### 周总结模板（中文）

```markdown
# 2026-W15 周报 (04.07 - 04.13)

> cluster_run_id: 42

## 本周趋势
...

## 推荐精读
- [[paper-title-a]] — 推荐理由 ...

## 领域动态
### #training/rlhf
本周 X 篇，较上周 +Y，趋势：...

### #inference/quantization
...

## 新兴信号
...
```

- 通过 `sync_log` 记录同步状态
- 使用 checksum 检测内容变更
- 同一 `sync_type + logical_target + checksum` 重复写入必须幂等

### 5.7.1 Review Queue 触发规则

以下情况必须进入 `Review Queue`：

- 标题模糊匹配命中，且 `match_confidence < 1.0`
- PDF 解析质量分低于阈值
- `analysis_runs.confidence` 低于阈值
- 证据引用缺失或页码映射不完整

### 5.8 Reporter（趋势报告）

- **触发**：每周 cron（建议周一上午） + 手动
- **流程**：
  1. 读取本周 `paper_analysis.active_analyzed_at` 位于窗口内的论文
  2. 使用当前 active `embedding_version` 执行 full cluster run
  3. 生成 `cluster_versions` 与 `paper_cluster_assignments(assignment_type='stable')`
  4. 对比上一周 stable cluster run
  5. 调用 LLM 生成周报：
     - 各 cluster 活跃度和变化趋势
     - 值得精读的 highlight 论文
     - 新兴方向/热点信号
     - 跨领域关联洞察
  6. 存入 `weekly_reports`
  7. 创建 `stage_runs(stage='sync', target_type='report', target_id=report_id)` 任务

### 5.9 Backfiller（历史回溯）

- **触发**：手动，指定起止日期
- **流程**：
  1. 创建 `backfill_jobs` 记录
  2. 为范围内每一天初始化 `backfill_job_days`
  3. 按天切片执行 Collector 逻辑
  4. 只有当某天在 `backfill_job_days` 中所有终态阶段完成后，才推进 `cursor_date`
  5. 后续复用 PDF Fetcher → PDF Parser → Processor → Analyzer → Sync 的任务链
- **并发约束**：
  - Backfiller 与日常 Collector 可并发运行
  - 二者必须共享同一套 paper upsert 和 stage idempotency 规则
  - 同一 `paper_id + stage + logical_input_hash` 不得产生多条有效任务
- **限流**：
  - arXiv 请求间隔默认 3 秒
  - HuggingFace 依据 rate limit header 动态退让

## 6. Web UI 与 API

### 6.1 技术选型

- **前端**：React + TypeScript + Vite + TailwindCSS
- **UI 组件**：shadcn/ui
- **图表**：Recharts
- **后端 API**：FastAPI，提供 REST API

### 6.2 核心页面

| 页面 | 功能 |
|------|------|
| **Dashboard** | 今日/本周采集概览、分析完成量、评分分布、领域热度图、近期趋势 |
| **Papers** | 论文列表，支持按评分/日期/领域筛选、关键词搜索、语义搜索 |
| **Paper Detail** | 单篇论文详情：分析结果、来源信号、PDF 下载状态、解析结果、证据引用、领域归属历史 |
| **Review Queue** | 低置信匹配、低质量解析、低置信分析的人工审核与重跑入口 |
| **Domains** | 自动发现的领域聚类可视化，展示 stable cluster run |
| **Reports** | 历史周报浏览，按周切换 cluster run |
| **Admin** | 手动触发任务、查看任务队列、失败重试、PDF 下载/重解析管理、运行日志 |

### 6.3 REST API 合同（最小可实现版本）

| Endpoint | 方法 | 说明 |
|----------|------|------|
| `/api/papers` | `GET` | 分页获取论文列表，支持 `q/date_from/date_to/tag/domain/score_min/page/page_size/sort` |
| `/api/papers/{paper_id}` | `GET` | 获取单篇论文详情、来源信号、分析结果、领域归属历史 |
| `/api/papers/{paper_id}/pdf` | `GET` | 获取 PDF 资产信息、存储状态、解析状态 |
| `/api/papers/{paper_id}/pdf/content` | `GET` | 获取全文提取摘要、章节结构、块级引用信息 |
| `/api/papers/{paper_id}/pdf/file` | `GET` | 获取当前 PDF 文件下载地址或流式预览 |
| `/api/papers/{paper_id}/pdf/pages/{page_no}` | `GET` | 获取指定页的预览/锚点定位信息 |
| `/api/papers/{paper_id}/pdf/refetch` | `POST` | 重新下载 PDF，并创建新的 `pdf_fetch` 任务 |
| `/api/papers/{paper_id}/pdf/reparse` | `POST` | 基于指定 `paper_file_id` 重新执行解析 |
| `/api/search/semantic` | `POST` | 语义搜索，输入 `query/top_k/embedding_version(optional)` |
| `/api/domains` | `GET` | 获取某个 `cluster_run_id` 下的领域树和统计 |
| `/api/reports` | `GET` | 获取周报列表 |
| `/api/reports/{report_id}` | `GET` | 获取单篇周报详情 |
| `/api/jobs/collect` | `POST` | 手动触发采集任务，返回 job id |
| `/api/jobs/backfill` | `POST` | 创建回溯任务，输入 `range_start/range_end` |
| `/api/jobs/{job_id}` | `GET` | 查看单个 job 或 backfill job 状态 |
| `/api/stages/retry` | `POST` | 对指定 `stage_run_id` 创建新的 attempt |
| `/api/review-queue` | `GET` | 获取待人工审查的低置信条目 |
| `/api/review-queue/{item_id}` | `POST` | 审核通过/驳回/合并/重新绑定并触发下游重跑 |
| `/api/health` | `GET` | 健康检查 |

### 6.4 API 响应约定

- 列表接口统一返回：
  - `items`
  - `page`
  - `page_size`
  - `total`
- 异步触发接口统一返回：
  - `job_id`
  - `status`
  - `accepted_at`
- 错误响应统一格式：

```json
{
  "error_code": "stage_conflict",
  "message": "analyzer task already running for this paper",
  "request_id": "..."
}
```

`/api/stages/retry` 请求体最小定义：

```json
{
  "stage_run_id": 123,
  "reason": "manual_retry_after_parser_fix"
}
```

## 7. LLM / Embedding 接口设计

### 7.1 设计原则

- 模型无关，仅依赖 OpenAI API 协议
- 模型切换通过配置完成，但**切换 embedding 模型不是“零代价”操作**，必须创建新版本并执行全量重嵌入
- `chat_json` 的 schema 必须固化版本，便于测试和回放
- LLM 分析应优先消费结构化 PDF 提取结果，而不是直接处理原始二进制 PDF

### 7.2 LLMClient 接口

```python
class LLMClient:
    """统一 LLM 调用接口，底层走 OpenAI API 协议"""

    def __init__(self, base_url: str, api_key: str, model: str):
        ...

    async def chat(self, messages: list[dict], **kwargs) -> str:
        ...

    async def chat_json(
        self,
        messages: list[dict],
        response_schema: dict,
        **kwargs,
    ) -> dict:
        ...
```

### 7.3 EmbeddingClient 接口

```python
class EmbeddingClient:
    """统一 Embedding 调用接口，底层走 OpenAI API 协议，可替换为本地模型"""

    def __init__(self, base_url: str, api_key: str, model: str):
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...
```

### 7.4 默认配置

```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-5.4"
  prompt_version: "analysis_v1"

embedding:
  base_url: "https://api.openai.com/v1"
  api_key: "${OPENAI_API_KEY}"
  model: "text-embedding-3-small"
  active_version_id: 1

obsidian:
  vault_path: "/path/to/your/obsidian/vault"
  root_folder: "LLM-Research"

storage:
  data_root: "./data"
  paper_root: "./data/papers"

pdf:
  download_timeout_seconds: 120
  max_file_size_mb: 100
  parser_name: "marker"
  parser_version: "v1"
  keep_raw_pdf: true
```

切换模型示例（如使用本地 Ollama）：

```yaml
embedding:
  base_url: "http://localhost:11434/v1"
  api_key: "ollama"
  model: "nomic-embed-text"
  active_version_id: 2
```

## 8. 技术决策汇总

| 决策 | 选择 | 理由 |
|------|------|------|
| 后端框架 | FastAPI | 异步原生，适合 IO 密集的采集和 LLM 调用 |
| 数据库 | SQLite | 个人工具足够，零运维 |
| 向量存储 | ChromaDB | 轻量，本地嵌入式，Python 原生 |
| 调度器 | APScheduler | Python 原生，轻量，支持 cron 表达式 |
| 任务编排 | DB 任务表 + lease | 比单一 `status` 更适合重试、幂等和并发控制 |
| PDF 存储 | 本地受控目录 + DB 索引 | 支撑下载、校验、重解析和文件管理 |
| PDF 解析 | 结构化提取 + 页码映射 | 让 LLM 深度阅读可引用、可追溯 |
| LLM | OpenAI API 协议 (默认 GPT-5.4) | 模型无关设计，可配置替换 |
| Embedding | OpenAI API 协议 + 显式版本表 | 支撑模型切换和全量重建 |
| 聚类算法 | HDBSCAN | 不需预设 cluster 数，但只把 weekly full run 视作 stable 结果 |
| 前端框架 | React + Vite + TypeScript | 轻量快速，生态成熟 |
| UI 组件 | shadcn/ui + TailwindCSS | 现代、可定制 |
| 图表 | Recharts | React 生态，声明式 API |
| Obsidian 集成 | 直接写文件到 Vault 目录 | Obsidian 本质是 Markdown 文件夹 |
| 开发原则 | TDD + API Contract First | 先固定接口和测试再写实现 |
| 输出语言 | 中文 | 所有 Obsidian Note、周报均为中文 |

## 9. 错误处理与重试

| 场景 | 策略 |
|------|------|
| arXiv API 超时/限流 | 指数退避重试，最多 3 次，间隔 3s/9s/27s |
| HuggingFace 请求失败 | 同上；若持续失败则保留 arXiv 数据并将 HF 信号标记缺失 |
| PDF 下载失败 | `stage_runs(stage='pdf_fetch')` 标记为 `failed`，允许重试或降级为 `abstract_only` |
| PDF 校验失败 | 记录坏文件 checksum，删除损坏文件，重新创建下载任务 |
| PDF 解析失败 | `stage_runs(stage='pdf_parse')` 标记为 `failed`；若允许降级，则继续 processor 但标记无全文 |
| LLM API 调用失败 | `stage_runs(stage='analyzer', target_type='paper')` 标记为 `failed`，记录 `last_error`，允许 Admin 重试 |
| Obsidian Vault 路径不可写 | 启动时检查路径有效性；sync task 标记为 `failed`，不影响 `paper_analysis` |
| worker 崩溃或超时 | 由 `lease_expires_at` 回收任务，允许其他 worker 重新领取 |
| embedding 模型切换中断 | 保留旧 active version，直到新 version 完成全量重嵌入并手动切换 |
| 单篇论文处理异常 | 单任务失败，不阻塞同批次其他任务 |

失败任务可在 Admin 页面查看并手动重试。

## 10. 测试策略

### 10.1 测试分层

- **单元测试**
  - 采集器解析逻辑
  - PDF 下载器校验逻辑
  - PDF 解析结果规范化
  - 标题匹配与去重逻辑
  - Prompt 组装与 JSON schema 校验
  - Obsidian Markdown 生成
- **集成测试**
  - SQLite + Chroma + FastAPI 在本地临时目录联调
  - PDF 下载 → 解析 → 分析链路联调
  - job lease / retry / idempotency 行为
  - backfill 与日常 collector 并发时的幂等性
- **契约测试**
  - REST API 响应结构
  - LLM `chat_json` 输出 schema
- **Golden 测试**
  - Note 模板输出
  - 周报 Markdown 输出

### 10.2 非确定性控制

- LLM 输出通过固定 prompt version + schema 约束
- 聚类测试不验证“语义正确性”，只验证：
  - 版本记录是否生成
  - assignment 是否可追溯
  - 周报是否绑定正确 `cluster_run_id`
- 需要补一条最小 E2E smoke test：
  - 采集 -> PDF 下载 -> 解析 -> 分析 -> 同步 -> 周报 -> UI/API 可见

### 10.3 最低验收标准

- 同一论文重复采集 3 次不会产生重复 paper 或重复阶段任务
- analyzer 失败后重试只产生一份最终分析结果
- 同一 PDF 重复下载不会产生重复文件资产记录
- PDF 重解析会产出新 extraction 记录且不破坏历史分析
- sync 失败不会回滚 analysis
- 切换 embedding version 后旧周报仍可复现
- 证据引用可以通过 API/UI 跳回对应 PDF 页码或块锚点

## 11. 项目结构

```
paper-trending/
├── backend/
│   ├── config/
│   │   └── settings.yaml
│   ├── core/
│   │   ├── database.py
│   │   ├── vector_store.py
│   │   ├── llm_client.py
│   │   ├── embedding_client.py
│   │   └── models.py
│   ├── collectors/
│   │   ├── base.py
│   │   ├── arxiv.py
│   │   └── huggingface.py
│   ├── pdf/
│   │   ├── fetcher.py
│   │   ├── parser.py
│   │   └── storage.py
│   ├── processor/
│   │   └── processor.py
│   ├── analyzer/
│   │   ├── scorer.py
│   │   ├── tagger.py
│   │   ├── analyzer.py
│   │   └── clusterer.py
│   ├── obsidian/
│   │   ├── templates/
│   │   ├── generator.py
│   │   └── syncer.py
│   ├── reporter/
│   │   └── reporter.py
│   ├── backfiller/
│   │   └── backfiller.py
│   ├── jobs/
│   │   ├── lease_manager.py
│   │   └── stage_runner.py
│   ├── api/
│   │   ├── papers.py
│   │   ├── domains.py
│   │   ├── reports.py
│   │   ├── jobs.py
│   │   └── admin.py
│   ├── scheduler/
│   │   └── scheduler.py
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Papers.tsx
│   │   │   ├── PaperDetail.tsx
│   │   │   ├── Domains.tsx
│   │   │   ├── Reports.tsx
│   │   │   └── Admin.tsx
│   │   ├── api/
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── tests/
│   ├── backend/
│   │   ├── test_collectors/
│   │   ├── test_processor/
│   │   ├── test_analyzer/
│   │   ├── test_obsidian/
│   │   ├── test_reporter/
│   │   ├── test_backfiller/
│   │   ├── test_jobs/
│   │   └── test_api/
│   └── frontend/
├── data/
├── requirements.txt
└── pyproject.toml
```
