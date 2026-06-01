# 云端 Ultraplan ↔ 本地执行 + 多 session 并发协作（2026-06-01）

本 session 用了「云端精修计划 → 本地执行」的分工，并踩了多个 Claude session 共用一个工作树的坑。记录可复用的协作模式，避免后续 session 重蹈。

## 云端会话（Ultraplan / Claude Code on the web）的硬约束

云端远程会话在一台**全新 clone 仓库**的容器里跑，与本地环境有三个关键差异：

1. **没有 `data/`**：`tracker.db` / `data/papers`（PDF）/ `data/chromadb`（嵌入）全被 gitignore，云端 clone 里根本没有。
2. **没有 `.env`**：API key 不在仓库里。
3. **可能没有 push 凭证**：本次实测云端 session 报「没配置 SSH 或 GitHub 权限，无法 push」。

**后果**：任何依赖数据库/向量库/语料的脚本（`trend_report.py`、`analyze_all.py`、`bench_*` 等）在云端**跑不起来**——它只能读代码、改代码、写计划。

## 可复用的协作模式

> **云端负责「想」（精修 plan / 改脚本），本地负责「做」（用真实数据跑）。两端只通过 git/patch 交接。**

本次具体路径：
1. 本地写初版 plan（`~/.claude/plans/*.md`）。
2. 交给 Ultraplan 云端精修 prompt/计划。
3. 云端无 push 权限 → **导出 `git diff` patch** 回本地（本次落在 `~/Downloads/*.patch`）。
4. 本地 `git apply <patch>` → `ruff check` → **用真实 660 篇数据跑** `trend_report.py` 生成报告。
5. 本地 commit + push + 开 PR。

patch 落地检查清单：
- `git apply --stat <patch>` 看动了哪些文件、范围对不对。
- `git apply --check <patch>` 确认能干净 apply（base 对得上）；冲突则说明 patch 的 base 与当前分支不一致。
- apply 后跑 `ruff` + 相关测试，别假设云端代码必然干净。

## 登录坑

- 云端远程会话（Ultraplan）需用 **Claude.ai 账户 OAuth 登录**，**不是** Anthropic Console / API key。凭证不对会报 `cannot launch remote session — Please run /login and sign in with your Claude.ai account (not Console)`。
- 排查：先确认环境无 `ANTHROPIC_API_KEY` 等在「抢」凭证（本次实测全 unset），问题出在 CLI 存的登录凭证类型 → `/login`（必要时先 `/logout`）重新走订阅 OAuth。

## 多 session 共用工作树的坑（重要）

本次两个 Claude session 共用同一个工作树 `~/paper-trending`，反复出问题：

- 一个 session `git checkout phase2-trigger-endpoints`，**主工作树磁盘文件被原地换成 phase2 的**；另一个 session（我）以为还在 `feat/weekly-trend-pipeline`，结果脚下文件被换、还冒出 phase2 的半成品改动。
- 两边的未提交改动混在同一棵树里：commit 时极易把对方的半成品一起带进来。我多次提交时不得不**显式 `git add` 指定文件**、排除对方的改动。
- `git checkout` 切分支会因对方未提交改动而 `aborting`；想隔离自己的改动时 `git stash` 也会误伤对方。

**解法 = git worktree 物理隔离**（已写进 CLAUDE.md Important Rules）：
- `git worktree add -b <分支> ~/pt-<名字> <起点分支>` 开独立目录干活，commit/push/PR 全在里面，**完全不碰对方正在编辑的主树**。
- 本次的文档更新、深度报告提交、CLAUDE.md 规则提交，全部走独立 worktree（`/tmp/wt-trend`、`~/pt-claudemd`、`~/pt-docs`），互不干扰、各自独立 PR。
- 注意：`Database.execute()` 返回 `lastrowid` 非 rowcount；脚本异常未走 `db.close()` 会留 aiosqlite **非守护线程**僵死、占着 DB 写锁（`database is locked`）→ 长跑脚本务必 `try/finally: await db.close()`。

## 一句话结论

- 数据相关的活留本地，云端只规划/改码；两端用 patch/PR 交接。
- 多 agent 并行用 worktree 隔离，别共用工作树。
- 详见 CLAUDE.md「Important Rules」两条（worktree / 云端会话）。
