# Prompt Optimization Plan (v3 — consolidated from 4-way review)

## Goal
Optimize the analyzer prompt to produce meaningful score discrimination and high-quality structured analysis.

## Background
- HuggingFace Daily Papers 是用户自主上传的论文，非编辑精选，质量参差不齐
- 当前 150 篇测试中，评分集中在 7-8 分（84 篇 8 分，63 篇 7 分），几乎无区分度
- 这是 prompt 缺陷，不是数据集选择偏差

## Test Set
从已有 150 篇 HF Daily Papers 中选 30 篇，按 HF likes 分层抽样：
- 10 篇 high-likes（likes 排名前 20%）
- 10 篇 mid-likes
- 10 篇 low-likes（likes 排名后 20%）

另留 10 篇作为 held-out validation set（不参与 prompt 调优，每轮检查分布漂移）。

## Ground Truth / 外部信号
- HF likes 作为质量代理信号（不完美，但唯一可用的外部信号）
- 手动标注 15 对 "A 明显优于 B" 的论文对

## Metrics（每轮追踪）

### 核心指标
| 指标 | 说明 | 目标 |
|------|------|------|
| Rank correlation (Spearman) | LLM score vs HF likes | > 0.4 |
| Pairwise accuracy | 手动标注对，LLM 是否一致 | > 75% |
| Score stddev | 分数标准差 | > 1.5 |
| Score range | max - min | > 4 |
| Coefficient of variation | stddev / mean | > 0.2 |

### 辅助指标
- Pairwise consistency：同一论文跑 2 次，分数绝对差（目标 < 0.5）
- Valid JSON rate（解析成功率）
- Schema validity rate（字段完整、类型正确、范围合法）
- 分类别方差：不同领域（NLP/CV/RL）是否都被压到同一分数段

## Convergence Criterion
相邻两轮：rank correlation 提升 < 0.02 AND pairwise accuracy 变化 < 2% → 提前退出。

---

## Round 0: Infrastructure + Baseline

### 0.1 修 `chat_json` 鲁棒性
- 加 `_extract_json()`：strip `<think>` blocks → strip markdown fences → regex 提取最大 `{...}` → json.loads
- 加 retry 循环（max_retries=3）
- Pydantic schema 校验输出（字段存在、类型、范围）

### 0.2 修 analyzer 调用
- 显式设 `temperature=0`（消除采样噪声，让轮间对比有意义）
- 加 `asyncio.Semaphore(5)` 并发（150 篇从 68min → ~15min）

### 0.3 修 StageRunner
- 检查是否有 max_attempts 上限，避免坏任务无限重试

### 0.4 Prompt 版本化
- 每轮 prompt 存档：prompt hash + model + temperature + 所有输出
- 方便回溯对比

### 0.5 跑 baseline
- 用当前 prompt（仅修了基础设施）跑 30 篇测试集 + 10 篇 held-out
- 记录所有 metrics 作为 Round 0 基准

---

## Round 1-5: Full Review Cycles

每轮都是完整的 "审查输出 → 诊断全部问题 → 全面修复" 循环，不预设改什么。

### Round 1 预期重点（基于 4-way review 的共识）

**评分校准：**
- 加 BARS 锚点描述（每个分数段对应具体的论文特征）
  - 1-3: 增量工作/已知方法换领域/有明显缺陷
  - 4-5: 扎实执行但无显著创新
  - 6-7: 有意义的贡献，值得关注
  - 8-9: 强创新，可能被广泛引用
  - 10: 改变领域方向的里程碑式工作
- 加显式分布约束："Most papers should score 4-7. Score 8+ requires clear evidence of novelty."
- 加反锚定指令："List limitations and weaknesses BEFORE assigning scores."
- score_total 改为 Python 侧从子分数加权计算，从 LLM 输出中移除

**Thinking 模型适配：**
- 移除 "Output ONLY valid JSON"
- 改为 "Think through your analysis step by step, then output a single JSON object."
- Parser 负责 strip 推理内容

**内容质量：**
- evidence_citations 在 abstract_only 模式下改为可选（避免鼓励编造）
- tags 加数量约束（5-8 个），要求分层（1-2 个大类 + 3-6 个具体标签）
- innovation_points 要求与 prior work 对比

**Few-shot 校准：**
- 加 2-3 个示例（低分/中分/高分各一个），附评分理由

### 每轮流程
1. 审查全部 30 篇输出（评分 + 内容 + 格式）
2. 诊断所有问题
3. 全面修改 prompt
4. 重跑 30 篇测试集 + 10 篇 held-out
5. 量化对比（metrics 表格）+ 定性抽检
6. 检查收敛条件
