# CLAUDE.md findings — 写法与模板

> 本文件随 repo 走（换机/clone 都有）。配合 CLAUDE.md「Important Rules → CLAUDE.md 单写者 + findings 收件箱」使用。

## 为什么有这套机制

CLAUDE.md 是所有 session 启动即加载的共享知识库。多个 session 并发**直接改** CLAUDE.md
必冲突、易丢经验（2026-06 三方并发改实证）。所以：**每轮只一个 CLAUDE.md owner 编辑它**，
其他 session 把发现写成 finding，owner 统一 fold。

## 队列在哪（注意：仓库外）

live finding 文件写到 **`~/pt-findings/<session>-<短主题>.md`**——**仓库外**、所有 git worktree 之上的
单一物理文件夹。为什么不放 repo：纳入 git 的文件和 CLAUDE.md 一样**分支隔离**，别的 session 在它
自己 worktree/分支上的文件，你不 merge 进 main 就看不到 → 跨 worktree 不可见，达不到「即时共享」。
而 `~/pt-findings/` 是所有 worktree 之上的同一份物理文件，谁都能即时读写。

- 首次用：`mkdir -p ~/pt-findings`
- 一 finding 一文件 → 并发写不撞，**无需时间戳**（文件名 + mtime 足够）。
- 队列是**临时**的：owner fold 完即删，不留史（永久记录在 CLAUDE.md 的 git 历史）。
- 队列单机即可：并发 session 总在同一台机器共享 worktree；跨机器是「A 干完→换 B 重 clone」的串行场景。

## 写 finding 的六条准则

1. **可定位**：指明 CLAUDE.md 的具体节/行（改存量时引原文一句），或新增该归入哪节。
2. **有证据**：必附 grounded 证据——`path:line`、命令输出、PR 号。**禁止「我觉得/应该」**。
3. **已提炼**：给结论/规则，不是原始数据；profiling/对比表进 dev-note，finding 里只留指针。
4. **标类型**：`过期-删除` / `过期-更新` / `新增经验`（owner 据此处理）。
5. **标重叠**：若知道和别人 finding 撞了就注明，方便 owner 去重。
6. **署名+日期**：哪个 session / PR、何时。

## 单条 finding 模板（复制到 `~/pt-findings/<session>-<主题>.md` 改）

```markdown
# <一句话标题：过期/矛盾/缺失 + 位置>
- 类型: 过期-删除 | 过期-更新 | 新增经验
- 位置: CLAUDE.md 「<章节>」/ L<行>（改存量时引原文）；或新增 → 归入「<章节>」
- 证据: <path:line / 命令输出 / PR#>，说明为什么过期/为什么该加
- 建议: <提炼后的规则或结论；原始数据见 dev-note xxxx>
- 来源: <session 名 / PR#>，<日期>
- 状态: pending
```

## owner 整合流程

1. 读 `~/pt-findings/` 全部 finding。
2. 逐条 fold 进 CLAUDE.md 对应章节，去重（多人撞同一处时捏合，不重复加）。
3. `git diff origin/main -- CLAUDE.md` 自查：**只增改、没删**别人的规则。
4. 跑知识完整性核对（关键规则是否都还在）。
5. commit message 列明 fold 了哪些 finding。
6. **删掉已处理的 finding 文件**，清空 `~/pt-findings/` 队列。
