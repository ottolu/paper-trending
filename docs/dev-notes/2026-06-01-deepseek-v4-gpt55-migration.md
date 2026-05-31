# 2026-06-01 — SiliconFlow key 泄露事故 + DeepSeek V4 Pro / GPT-5.5 迁移

## 1. 安全事故：SiliconFlow API key 泄露被盗刷

### 现象
用户 SiliconFlow 账户余额被刷光。

### 根因（已定位）
真实 key `sk-sazy…jlp` 被**硬编码明文**写进 5 处被 git 跟踪的脚本，并随 commit
推到**公开** GitHub 仓库 `github.com/ottolu/paper-trending`：

- `scripts/eval_prompt.py`、`scripts/retry_analyzer.py`、`scripts/retry_to_target.py`(×2)、`scripts/run_full_pipeline.py`

引入 commit：`231db11`（2026-04-16）、`94bb336`（2026-04-18），**两者都带 `Co-Authored-By: Claude Opus 4.6`**
——是过去的 Claude session 写 eval/retry 脚本时把 key 写死并 push 的。公开仓库的 key 会被扫号机器人在分钟级抓走。key 在公开仓库里暴露约 6 周。

### 处置
- **唯一有效止血 = 在 SiliconFlow 吊销该 key**（公开过的 key 必须当永久作废，改历史救不回）。用户操作。
- 代码侧：5 处硬编码全部改为 `os.environ["SILICONFLOW_API_KEY"]`（与既有 `eval_fulltext_both.py` 等一致）。
- 仓库/历史：用户选择**不动**（不 force-push、不改公开性）——key 吊销后历史残留无害。
- 全仓 secret 广扫：除这一把 SF key 外**无其它密钥**（无 openai/hf/aws/slack）。`settings.yaml` 本来就用 `${SILICONFLOW_API_KEY}`，安全。

### 防复发
新增 `hooks/pre-commit`（`git config core.hooksPath hooks` 启用）：扫 staged diff 里的
`sk-…{32,}`/`sk-proj-`/`hf_`/`gh[pousr]_`/`AKIA…`/`xox[baprs]-` 高信号 token，命中即 block；
过滤 `${VAR}`/`sk-test`/`example` 等占位；误报可 `ALLOW_SECRET=1 git commit`。已正/负用例实测通过。
⚠️ `core.hooksPath` 是本地 git config，**新 clone 需重新 `git config core.hooksPath hooks`**。

## 2. 模型迁移

| | 旧 | 新 |
|---|---|---|
| LLM provider | SiliconFlow | **DeepSeek 官方** `https://api.deepseek.com` |
| LLM 模型 | `deepseek-ai/DeepSeek-V3.2`（settings）/ `Qwen/Qwen3-VL-235B-A22B-Thinking`（脚本，漂移） | `deepseek-v4-pro` |
| LLM key | `${SILICONFLOW_API_KEY}` | `${DEEPSEEK_API_KEY}` |
| Embedding | SiliconFlow `Qwen3-Embedding-8B` | **不变**（仍 SiliconFlow，需新 SF key） |
| GPT 评测 | `gpt-5.4` | `gpt-5.5`（codex 默认 model 即 5.5） |

V4 Pro：1.6T 参数（49B 激活），1M context，官方 75% 折扣期。`deepseek-chat`/`deepseek-reasoner` 2026-07-24 弃用。

## 3. 踩坑 recipe：DeepSeek 官方 thinking 方言 ≠ SiliconFlow

SiliconFlow/Qwen 用 `extra_body={"enable_thinking":True,"thinking_budget":N}`；
**DeepSeek 官方完全不同**（来源：api-docs.deepseek.com/guides/thinking_mode）：

- 开关：`extra_body={"thinking":{"type":"enabled"}}`，**V4 Pro 默认就开**。
- CoT 走 `reasoning_content`（与 `content` 同级）。
- ⚠️ **thinking 模式拒绝 `temperature`/`top_p`/`presence_penalty`/`frequency_penalty`**；`response_format` json_object 兼容性文档未明确（DeepSeek reasoner 历史上不支持）。

`LLMClient` 改为 **provider-aware**（按 base_url 含 `deepseek.com` 判别）：DeepSeek 路径注入
`thinking` 对象，并在 thinking 开时 strip 上述 4 个采样参数 + `response_format`，靠 `_extract_json()` 兜底解析。
SiliconFlow 路径保持原 `enable_thinking`/`thinking_budget`。`reasoning_content` fallback 合入 `chat()` 返回值
（兑现了 CLAUDE.md 里挂了很久的 TODO；之前只在评测脚本里有）。

## 4. 设计决策：评分确定性 vs thinking 质量

CLAUDE.md 旧规则"评分分析必须 `temperature=0`"在 V4 Pro thinking 模式下**无法满足**（该模式禁 temperature）。
取舍：
- **方案 A（当前默认）**：V4 Pro thinking on，放弃 temperature=0 → 评分不再确定性，但拿到最强推理。
- **方案 B（备选）**：`enable_thinking=false` 走 V4 Pro 非 thinking，恢复 temperature=0 确定性评分，牺牲推理深度。

当前选 A（用户明确要 V4 Pro 这个 thinking 旗舰）。若后续发现评分排名复现性（Spearman 对照那套方法论）受影响，一行
flag 即可切 B。**未拍死，按场景留口子。**

## 5. 漂移发现：生产其实不经 FastAPI 跑 analyzer

`backend/main.py:lifespan` 只初始化 DB/Embedding/VectorStore，**不构造 LLMClient**。真正跑分析的是
`scripts/run_full_pipeline.py` / `retry_analyzer.py` / `retry_to_target.py`，各自直接 new LLMClient。
所以换模型必须同时改 `settings.yaml`（未来若接线生效）+ 这三个脚本（当下实际生效）。三个脚本已切 V4 Pro。

## 6. 验证状态

- ✅ pytest 162 passed（含全部 `llm_client` 单测）；`backend/core/llm_client.py` 与三个 ops 脚本 ruff 干净。
- ⚠️ **未做 live 冒烟**：旧 SF key 已废、`DEEPSEEK_API_KEY` 尚未注入，无法真打 DeepSeek API。
  需用户设 `DEEPSEEK_API_KEY`（LLM）+ 新 `SILICONFLOW_API_KEY`（embedding）后跑一次单篇 analyzer 验证。
- 既有（非本次引入）问题：`test_huggingface.py::test_parse_daily_papers` 失败（`hf_likes` 解析返回 None，stash 验证为预存）；eval 脚本有 10 个预存 ruff 风格 error（E402/F401/F541/E741）。
