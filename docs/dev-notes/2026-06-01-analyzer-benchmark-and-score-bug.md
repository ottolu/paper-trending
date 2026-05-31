# Analyzer 端到端基准 + score_total=0.0 生产 bug（2026-06-01）

扩规模（半年/一年）前，对已解析的 120 篇抽 8 篇（页数铺开）跑通 processor+analyzer，
实测新 `deepseek-v4-pro`(thinking) 的 per-paper 时延/成本。脚本 `scripts/bench_downstream.py`。

## 时延 + 成本（8 篇，full_text，0 失败）

| 论文(页) | 耗时 | 总 token | 输入/输出 |
|---|---|---|---|
| 04036 (7) | 54s | 9.8K | 7.7K/2.1K |
| 28421 (17) | 49s | 16K | 14K/2.0K |
| 28816 (21) | 65s | 20.7K | 18K/2.6K |
| 15178 (25) | 88s | 31.5K | 28K/3.5K |
| 30346 (29) | 76s | 32.2K | 29K/3.0K |
| 22109 (34) | 69s | 38K | 35K/2.7K |
| 15128 (46) | 49s | 51K | 49K/1.9K |
| 18747 (102) | 51s | 89.4K | 87.6K/1.8K |

- **per-paper：avg 63s（median 59，49–88s）。**
- **反直觉点：耗时与篇幅几乎无关**（102 页 51s，25 页 88s）——thinking 主导，不是输入长度。小论文不会更快。
- **token**：avg 36K/篇；输入随页数近线性（7.7K→87.6K），输出稳定 ~2–3.5K。
- processor（分块）≈ 瞬时；嵌入实际在 analyzer 内做（`service.py` 用 title+abstract embed）。

### 外推（串行）
| 规模 | 时间 | 成本* |
|---|---|---|
| 120 | ~2.1 h | ~$1.3 |
| 780（6mo 周 top-30） | ~13.6 h | ~$8.2 |
| 1560（1yr） | ~27.2 h | ~$16.3 |

\* 单价为**假定** $0.28/$0.42 per-M，需按 deepseek-v4-pro 实际费率替换。
analyzer 是**纯网络型（本地 0% CPU）**，并发能近线性压 wall-time（5 路 → 1yr ~5.5h），
但要先修 `claim()` 竞态（见 hf-weekly-pdf-ingest dev-note）才能安全并发。

## 系统性 bug：score_total 恒 0.0（小样本基准的最大收获）

**现象**：8 篇分析全部跑通（full_text、narrative/breakdown/tags 全部正常解析），但 `analysis_runs.score_total` 全是 0.0，且 `analysis_model`/`prompt_version` 全 NULL。

**根因**：`AnalyzerService.process_next()` 的 INSERT 用 `analysis.get("score_total", 0)`——但 v3 prompt（`prompts.py`）**故意不输出 score_total**（"Do NOT include score_total — it will be computed externally"），Python 侧从没补这步均值计算 → 恒 0.0。INSERT 列里也没有 `analysis_model`/`prompt_version`。这是**既有生产 bug**，非新模型引入。

**为何没被测试抓到**：`tests/.../test_service.py` 的 mock LLM 自己塞了 `score_total: 8.5`（且 breakdown {8,9,9,8} 均值恰好也是 8.5），测试断言 8.5 → 一直绿。典型「测后掩盖缺陷」：mock 表达的是实现假设，不是真实 prompt 行为。

**修复（TDD，2026-06-01）**：
- `prompts.py` 加 `PROMPT_VERSION = "v3"`。
- `service.py` 加纯函数 `score_total_from_breakdown(breakdown)`：`round(mean(数值项), 2)`（与 `eval_prompt.py:134` / `eval_cross_model.py:132` 一致）。INSERT 改用计算值，并补 `analysis_model=self._llm.model`、`prompt_version=PROMPT_VERSION`。
- 新增 RED 测试：mock 只给 breakdown 不给 score_total，断言存的是均值 + model/prompt_version 落库。RED→GREEN，全套 165 passed，ruff clean。
- **已有 8 条免重跑回填**：breakdown 已落库，一条 UPDATE 用同公式重算 → 5.0/5.75×2/6.25×2/6.75/7.5×2，区分度正常。

## 小样本基准的安全坑

`pdf_parse` 完成会给**每篇**自动建 `processor` stage_run（120 篇 = 120 pending）。基准要只跑 N 篇，必须先把非样本的 processor 任务**挂起**（status 改成非 `pending`，`claim()` 就跳过），跑完在 `finally` 里恢复。否则 `process_next()` 跑到没有为止会触发**全量** embedding+分析。
注意 `Database.execute()` 返回 `lastrowid` 而非 rowcount——日志里 "held N"/"restored N" 的数字是 lastrowid，不是受影响行数，别误读。

## 结论 / 选型

- **提取(pymupdf ~2.7s/篇)和下载都不是规模瓶颈；analyzer(~63s/篇、~36K tok/篇)才是时间+成本大头。**
- 扩到半年/一年前已确认：(1) 接线正确产出 full_text 分析；(2) 分数计算已修；(3) 成本可外推。
- 下一步若要压 wall-time：先修 `claim()` 原子性再并发 analyzer。

## 全量 120 篇 8× 并发实跑（claim 并发修复后）

`scripts/analyze_all.py`（worker-pool：N 个 worker 各自循环 `process_next`）。

- **120/120，0 失败**，全 full_text，无重复 analysis_runs。
- **墙钟 945s（~16 min）@ 8 路 → 有效 8s/篇**（对比串行 63s/篇，~8× 近线性加速，证明 analyzer 是网络型、并发收益足）。
- 分数分布 min 4.5 / median 6.5 / max 8.0 / mean 6.35（区分度正常，score_total 修复后非 0）。
- token in 3.68M / out 311K → **成本 $1.16**（假定 $0.28/$0.42 per-M）。外推：780 篇 ≈ $7.5、~1.6h；1560 篇 ≈ $15、~3.2h（@8×）。

### `claim()` 并发修复的踩坑过程（重要）

1. 先试 **`UPDATE ... WHERE id=(SELECT ... LIMIT 1) RETURNING *`**（单语句原子）。单测 10 并发/3 任务通过，但 **8 路实跑几秒即崩**：`sqlite3.IntegrityError` / commit 报错。根因——RETURNING 的结果集在**单一共享 aiosqlite 连接**上让该写语句保持「进行中」，另一协程并发 `commit()` 触发 "statements in progress"。**结论：单共享连接 + RETURNING + 跨协程 commit 不兼容，别用。**
2. 改用 **`asyncio.Lock`（`StageRunner._claim_lock`）串行化 SELECT→UPDATE 临界区**，回退到朴素 SQL（无 RETURNING）。锁只罩快速 DB 段，LLM 慢调用在锁外 → 并发不受损。这正是之前并发下载能跑通的写法 + 补上互斥。
3. **崩溃留僵尸**：脚本异常没走 `db.close()`，aiosqlite 的**非守护工作线程**不退出 → 进程僵死占着 DB 写锁（`database is locked`）。教训：长跑脚本务必 `try/finally: await db.close()`（已加）。
4. 清理：崩溃中途已有部分 analyzer 'running'/'succeeded' + 孤儿 analysis_runs。重置要按 FK 顺序删 `paper_analysis → analysis_runs → stage_run_attempts → sync stage_runs`，并把 analyzer 任务重置为 pending、attempt_no=0、清 attempt 历史（否则重 claim 撞 UNIQUE）。
5. ⚠️ `Database.execute()` 返回 `lastrowid` 非 rowcount——UPDATE 的「affected」数字别信。
