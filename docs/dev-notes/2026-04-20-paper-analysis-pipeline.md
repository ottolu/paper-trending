# Paper Analysis Pipeline — 评测与调优经验

日期：2026-04-18 ~ 2026-04-20
范围：PDF 解析方案选型、LLM 评测 prompt 迭代、V3.2 / GPT-5.4 对比。

---

## 1. PDF 解析三种方案对比

在 20 篇真实 arXiv PDF 上做 profiling，单篇结果（论文 2604.09531，25 页）：

| 方案 | 解析耗时 | Markdown | 章节识别 | 20 篇预估 |
|------|---------|----------|----------|----------|
| marker 完整模式（默认） | 255s | 94K chars | 51 条（含图表标题，偏杂） | ~3.5 小时 |
| marker `force_layout_block="Text"` | 6.5s | 96K chars | **0 条** | ~3 分钟 |
| **PyMuPDF + 字号 heading 识别** | **0.67s** | 84K chars | 38 条（干净的层级） | **~17 秒** |

**核心结论：对"送给 LLM 做分析"的场景，PyMuPDF 是正确选型。**
- 三种方案的文本内容差异 < 15%
- 字号启发式识别 heading 在 arXiv 论文上稳定有效（本 project 数据是 97%+ 命中）
- marker 完整模式的 91% 耗时在 Layout Recognition（Foundation 723M 参数模型）上
- marker 仅在需要精确表格/公式重建、非原生 PDF 的场景才值得

### PyMuPDF 结构化提取 recipe

关键步骤：
1. 遍历全文 spans，按字号统计字符数分布
2. 最高频字号 = body 字号
3. heading 判定：
   - `size > body + 6pt` → h1（论文标题）
   - `size > body + 1.5pt` → h2（章节）
   - `size > body + 0.3pt` + bold + `len < 100` → h3（子章节）

实现见 `scripts/build_fulltext_prompts.py`。

### marker-pdf 性能剖析

MPS 已启用（`TORCH_DEVICE_MODEL='mps'`），瓶颈不是设备：

| 阶段 | 7 页耗时占比 | 设备 |
|------|-------------|------|
| **Recognizing Layout** | **91%** | MPS |
| Recognizing tables | 6% | CPU（TableRec 不兼容 MPS） |
| OCR Error Detection | <1% | MPS |
| Detecting bboxes | 0% | MPS |

`disable_ocr=True` 只跳过 OCR Recognition，**Layout/Line Detection 仍然会跑**。
`force_layout_block="Text"` 能完全跳过 Layout 模型推理，提速 ~160 倍但丢失 heading 结构。

### 什么情况下还需要 marker

- PDF 是扫描件（需要 OCR）
- 需要精确的表格重建（table_rec 模型）
- 需要公式 LaTeX 重建（EquationProcessor）
- 需要图片抽取

---

## 2. 分析依据对比：abstract / 截断 / 全文

V3.2 同一 prompt (v3) 在 20 篇上三种输入对比：

| 模式 | 均分(40) | stdev | 信度 | strong evidence | 弱点/篇 |
|------|---------|-------|------|----------------|---------|
| abstract-only | 23.6 | 2.78 | 0.607 | **0%** | 2.8 |
| 截断 30K | 27.15 | 2.32 | 0.848 | 50% | 3.6 |
| **完整全文** | **26.2** | **2.98** ↑ | 0.853 | **70%** | **3.8** |

**排名相关性（Spearman ρ）：**
- abstract vs 截断：**0.742**
- abstract vs 全文：**0.446**
- 截断 vs 全文：**0.505** ← 只有一半的论文排序一致！

**结论：**
1. **abstract-only 必禁用于最终分析**，系统性低估且信度不足（已写入 CLAUDE.md）
2. **截断 30K 不安全**：和全文只有中等相关，约一半论文排序会变
3. **全文模式差异化最强**（σ 最大），能正确下调短论文（ATANT 7 页 21 分）和上调大型 benchmark（GameWorld 52 页 30 分）

---

## 3. Prompt v3 vs v4 (peer-review style)

### v4 设计思路

参考 ICLR/CVPR 审稿结构（`data/tmp/paper-reading-prompt.md`），重写为：
- Persona: senior reviewer for top-tier venues
- 叙事字段 6 段式：summary / strengths / weaknesses / key_questions / limitations / overall_impression
- 保留现有 1-10 × 4 维打分 key（backward compat）
- 新增 `overall_rating` 类别（Strong Accept → Strong Reject）
- 规则约束：rating 必须与数值分数一致

见 `backend/analyzer/prompts_v4.py`。

### V3.2 × v3 vs v4

| 指标 | v3 | v4 |
|---|---|---|
| 均分 | 26.2 | 26.7 |
| **stdev** | 2.98 | **3.42** ↑ |
| 分数范围 | 19-30 | **18-32** |
| 弱点/篇 | 3.8 | **6.1** ↑ |
| summary 长度 | 440 chars | 734 chars |
| 耗时 | 79s | 97s |

v4 在 novelty/impact/clarity 上均 stdev 更大，差异化更强。

### 已知问题：短论文 bias

v4 对 7 页短论文 ATANT 从 21 抬到 26。peer-review prompt 里没有"长度/深度是否匹配声明"的约束。如果需要修，应加 rubric：`rigor` 低分里加"paper is too short for stated claims"。

---

## 4. 四象限对比：V3.2 / GPT-5.4 × v3 / v4

### 分数分布

| 象限 | mean | stdev | 范围 |
|---|---|---|---|
| V3.2 × v3 | 26.2 | 2.98 | 19-30 |
| V3.2 × v4 | 26.7 | 3.42 | **18-32** |
| GPT-5.4 × v3 | 24.9 | 2.59 | 18-29 |
| **GPT-5.4 × v4** | **23.3** | 2.49 | 17-28 |

### 关键发现：两个模型对 v4 反应相反

- **V3.2 遇 v4 → 分数拉升** (+0.5)，能打 Strong Accept
- **GPT-5.4 遇 v4 → 分数压低** (-1.6)，更像严格 reviewer

v4 overall_rating 分布：
```
V3.2 × v4                     GPT-5.4 × v4
Strong Accept    1            Weak Accept      7
Accept           8            Weak Reject     12
Weak Accept      9            Reject           1
Weak Reject      2
```

GPT-5.4 在 peer-review 模式下明显偏 Reject 端，V3.2 更温和。

### 排名一致性

```
                V3.2-v3  V3.2-v4  GPT-v3   GPT-v4
V3.2-v3         1.000    0.787    0.751    0.770
V3.2-v4         0.787    1.000    0.797    0.814
GPT-v3          0.751    0.797    1.000    0.903  ← 最高
GPT-v4          0.770    0.814    0.903    1.000
```

- **GPT-5.4 对 prompt 鲁棒**（v3↔v4 ρ=0.903）：更换 prompt 主要改变严苛度，不改变排序
- **V3.2 对 prompt 敏感**（v3↔v4 ρ=0.787）：排序会变动
- **v4 prompt 下两模型排序更一致**（0.814 vs v3 的 0.751）：peer-review 结构帮助收敛

### 选型建议

| 场景 | 推荐 |
|------|------|
| 常规推荐（给普通用户看） | **V3.2 × v3**：温和分布，覆盖面广 |
| 精选榜单（严格筛选） | **GPT-5.4 × v4**：最深的 narrative，偏 Reject |
| 成本敏感 | **GPT-5.4 × v3**：34s/篇，最快 |
| 最强 narrative | **GPT-5.4 × v4**：7.5 弱点/篇 |

耗时对比：
- V3.2 平均 80-97s/篇，GPT-5.4 平均 35-66s/篇（**快 2-2.5 倍**）

---

## 5. 工程踩坑与经验

### DeepSeek V3.2 `reasoning_content` fallback

V3.2 在长 prompt (>99K chars) 上偶发：`content=""`, `finish_reason="stop"`，但完整 JSON 输出在 `reasoning_content` 字段里。

```python
msg = response.choices[0].message
content = msg.content
if not content or not content.strip():
    content = getattr(msg, "reasoning_content", "") or ""
if not content.strip():
    raise ValueError("Empty response")
```

固定模式，已写入 `scripts/eval_fulltext_both.py:call_v32()`。

### `max_tokens` 与 `thinking_budget` 的关系

V3.2 thinking 模式下，`thinking_budget=32768` 会吃掉大量 tokens。建议：
- 常规 prompt：`max_tokens=4096` 够用
- 长叙事输出（v4 peer-review）：**提到 6144** 以留余量给 summary/weaknesses/questions

### codex exec fallback 模式

OpenAI API 的 `gpt-5.4` 用 codex OAuth token 时，默认总是 429。两个 quota 是独立的：
- API key quota（`AsyncOpenAI`）
- ChatGPT 账户 quota（`codex exec` 走 OAuth token）

实际生产跑 GPT-5.4 直接走 `codex exec`，跳过 API 尝试（省 30s/篇）。见 `scripts/eval_fulltext_gpt54_v3.py`。

`codex exec` 每天有用量上限，用完后报：
```
ERROR: You've hit your usage limit. Upgrade to Plus to continue using Codex
```
通常隔天恢复，如持续耗尽需订阅 Plus。

### marker-pdf 不能通过 stdin heredoc 调用

marker-pdf 用 multiprocessing，通过 `python3 <<'PYEOF'` 启动会触发：
```
FileNotFoundError: '/path/<stdin>'
```
**必须写成脚本文件再调用**。

### JSON extract 健壮性

`extract_json` 偶发失败（20 篇里 1 篇，"Invalid \escape"）— 通常是模型在字符串里产生了未转义的反斜杠。重试一次一般就过。不值得专门加 unicode-escape 清洗。

---

## 6. 评测脚本索引

| 脚本 | 用途 |
|------|------|
| `scripts/build_fulltext_prompts.py` | PyMuPDF 批量提取 + 构造 full text prompt |
| `scripts/build_abstract_prompts.py` | 构造 abstract-only prompt |
| `scripts/parse_compare.py` | 单篇 3 方案 PDF 解析对比 |
| `scripts/eval_fulltext_both.py` | V3.2 和 GPT-5.4 全文评测（v3 prompt） |
| `scripts/eval_fulltext_v32_v4.py` | V3.2 × v4 peer-review prompt |
| `scripts/eval_fulltext_gpt54_v3.py` | GPT-5.4 × v3 prompt（纯 codex exec） |
| `scripts/eval_fulltext_gpt54_v4.py` | GPT-5.4 × v4 prompt（纯 codex exec） |
| `scripts/eval_abstract_v32.py` | V3.2 × abstract-only |
| `scripts/compare_v32_three_modes.py` | V3.2 三种输入模式汇总对比 |

结果文件（`tests/fixtures/`）：
- `eval_results_abstract_v32.json`
- `eval_results_deepseek_v32.json`（旧版：截断 30K）
- `eval_results_fulltext_v32.json`（V3.2 × v3）
- `eval_results_fulltext_v32_v4.json`（V3.2 × v4）
- `eval_results_fulltext_gpt54.json`（GPT-5.4 × v3）
- `eval_results_fulltext_gpt54_v4.json`（GPT-5.4 × v4）

Parsed PDF 中间件：`data/parsing_fulltext/{arxiv_id}/` 下含 `fulltext.md`、`fulltext.txt`、`sections.json`、`metadata.json`。

---

## 7. 建议的后续工作

1. **生产化 PyMuPDF 解析路径**：在 `backend/pdf/parser.py` 增加 `parser_name="pymupdf"` 分支，用于快速预分析通道（保留 marker 作为精细分析选项）
2. **在 v4 prompt 里加长度/深度一致性检查**：修复短论文被高估的 bias
3. **探索 ensemble 打分**：V3.2 × v3 + GPT-5.4 × v4 加权平均，利用两者分布差异
4. **HF likes 相关性基准**：v4 prompt 的排名和 HF likes 相关性是否高于 v3（值得单独测）
5. **长 prompt 的 V3.2 `reasoning_content` 问题**：在 SiliconFlow 侧反馈，或考虑切换到 SGLang 自部署

---

## 8. 设计决策记录：分数 vs HF likes 双轨展示

### 触发案例：Seedance 2.0 低分

字节 Seed 团队 Seedance 2.0 tech report (arXiv 2604.14148, HF likes=134)，4 个评测组合全部给低分：

| 组合 | score_total |
|------|------------|
| V3.2 × v3 | 24 |
| V3.2 × v4 | 21 (Weak Reject) |
| GPT-5.4 × v3 | 21 |
| GPT-5.4 × v4 | 20 (**Reject**) |

**4 个独立评测的 weaknesses 高度一致**，全在第一条点出：论文刻意不公开模型架构/训练数据/训练流程（商业机密），只讲能力宣传和自建 benchmark 评测，没有 ablation、没有开源模型对比、没有统计检验。

论文结构完全印证：只有 Introduction / Evaluation (2.1-2.6) / References / Contributions — **没有 Methodology 章节**。

### 根本原因：rubric 与论文类型错位

- **评测 prompt 衡量学术贡献**（novelty / rigor / impact / clarity 都依赖论文内容）
- **HF likes 衡量产品热度 / 社区兴趣**（品牌 + 视频演示效果）
- 对"大厂产品 tech report 刻意不公开方法"这一类型，两者**系统性错位**
- 这也解释了历史统计中 HF likes 与 LLM score 的 Spearman 仅 ~0.1（见 CLAUDE.md）

### 决策：双轨展示，不混合

**评分体系保持纯学术判断**：
- 不为作者机构、产品热度、HF likes 加分
- rubric 和论文内容严格对齐（跟 ICLR/NeurIPS 审稿一致）
- 四象限评测结果全部反映内容本身的学术质量

**展示侧并列暴露 `hf_likes`**：
- Dashboard / Papers 列表 / PaperDetail 页都应显示 HF likes 作为独立信号
- 用户自行综合判断"产品热门 vs 学术价值"
- Seedance 2.0 这种论文靠 HF likes 仍能上榜，但不污染评分体系

### 被拒绝的替代方案及理由

| 方案 | 拒绝理由 |
|------|---------|
| 为 tech report 加专属 rubric (v5) | 需要分类检测，破坏跨论文可比性 |
| Ensemble 评分 `final = 0.7×LLM + 0.3×log(HF)` | 混合不同语义的信号，让分数失去解释性 |
| 提高 impact 权重（大厂工作显然 impact 高） | 变成奖励作者机构，偏离内容评审本意 |

### 实现状态（2026-04-20 完成）

- [x] `backend/api/papers.py`：列表响应加 `hf_likes` 字段（`SELECT MAX(hf_likes) FROM paper_sources`），详情响应同样加 `hf_likes` 顶层字段；新增 `sort=hf_likes_desc` 选项
- [x] `frontend/src/api.ts`：`PaperListItem` 和 `PaperDetail` 都加 `hf_likes: number | null`
- [x] `frontend/src/pages/Papers.tsx`：表格加 `HF ♥` 列（≥50 时高亮 pink）
- [x] `frontend/src/pages/PaperDetail.tsx`：头部作者/sources 行追加 `♥ {hf_likes} on HuggingFace`，与 Score 卡片并列不混合
- [x] `frontend/src/pages/Dashboard.tsx`：新增 "Community Buzz" 专区，按 `hf_likes_desc` 排序，与 Recent Papers 两列并排；卡片同时展示 Score 和 ♥，明确两个信号独立
- 验收：`pytest tests/backend/test_api/test_papers.py` 7/7 通过；`ruff check` 通过；`frontend npm run build` 成功

---

## 9. 生产切换：PyMuPDF 作为默认解析器 + Prompts 目录整理

### PyMuPDF 生产化（2026-04-20）

`PdfParser` 增加了 `_run_pymupdf()` 分支，`parse()` 按 `self._parser_name` dispatch：

- `settings.yaml` 默认 `parser_name: "pymupdf"`（从 "marker" 改）
- 构造函数放宽 parser 校验（允许 "stub" 等测试名），实际 dispatch 时未识别则报错
- 输出格式保持一致（`fulltext.md` / `fulltext.txt` / `blocks.json` / `sections.json`），下游 ProcessorService 无需改动
- 测试 `tests/backend/test_pdf/test_parser.py` 由用 `parser_name="stub"` + 假 PDF 改为用 `parser_name="pymupdf"` + `pymupdf.open() -> new_page()` 生成的最小合法 PDF，5/5 通过

旧 fake PDF 测试其实在我改动前就是坏的（marker-pdf 吃不下 `%PDF-1.4 test content`），本次顺手修好。

### Prompts 文件整理（2026-04-20）

之前状态：`prompts.py`（生产）/ `prompts_v2.py` / `prompts_v3.py`（archived）/ `prompts_v4.py`，命名混乱 — `prompts.py` 实际是 "fulltext-aware v3"，但旁边又有个独立的 `prompts_v3.py`。

清理后：
- **`prompts.py`** — 生产单一来源（production 等价于 v3 with fulltext-aware）
- **`prompts_v2.py`** — 保留（历史评测基线，仍被 `scripts/eval_prompt.py` 引用）
- **`prompts_v4.py`** — 保留（peer-review 评测变体）
- **`prompts_v3.py`** — 删除（`prompts.py` 才是 v3）

更新 `scripts/eval_prompt.py` 的 version registry：`v1`/`v3`/`current`/`production` 都映射到 `prompts`，加了 `v4` 入口。
更新 `scripts/eval_cross_model.py`：从 `backend.analyzer.prompts_v3` 改为 `backend.analyzer.prompts`。

**规则：版本号只用于评测对照变体（如 `_v4` peer-review），生产不带版本号。**

### CLAUDE.md 一致性修正

修掉下列和真实代码不一致的描述：
- LLM 模型：`Qwen/Qwen3-VL-235B-A22B-Thinking` → `deepseek-ai/DeepSeek-V3.2`
- 并发建议：`concurrency=1 + 间隔 5-10s` → `MAX_CONCURRENCY=3 实测稳定`
- Layout Recognition 耗时占比：`~70%` → `~91%`（今天实测）
- PDF 解析：`marker 默认` → `pymupdf 默认，marker 可选`
- Prompt 文件描述：清晰标注哪个是生产、哪个是评测变体
- 新增：V3.2 `reasoning_content` fallback **尚未**集成到 `LLMClient.chat_json()`（只评测脚本有），作为 TODO 标注
