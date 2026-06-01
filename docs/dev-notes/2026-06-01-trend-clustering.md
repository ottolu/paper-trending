# 趋势/热点分析：聚类方法与发现（2026-06-01）

对 120 篇全文分析论文做主题聚类 + 趋势预判。脚本 `scripts/trend_report.py`，产出 `docs/trend-report-2026-06-01.md`。

## 方法

1. 取每篇 active analysis（score_total / score_breakdown / tags / summary）+ HF likes（`paper_sources`）+ 周（`published_date` → ISO week）。
2. 从 ChromaDB 取 title+abstract 嵌入（analyzer 写入，**非全文嵌入**），HDBSCAN 聚类。
3. 每簇聚合多维信号：规模、**周动量 W19→W22**、avg_score / novelty / impact、HF likes median/max、高频标签、代表作。
4. 一次 LLM 综合（deepseek-v4-pro thinking）→ markdown：主题命名、双轨热点排名、新兴趋势预判、学术×社区错位。

## 聚类选型踩坑

- **`ReporterService.generate_report` 不能直接用**：它调 `vector_store.get(..., include=[...])`，但 `VectorStore.get` 签名没有 `include` 参数 → TypeError（潜伏 bug，未修）。趋势脚本**直接用 chromadb collection.get(include=["embeddings"])** 绕过。
- **`ClusterService.run` 撞 FK**：`cluster_runs.embedding_version_id` 外键指向 `embedding_versions`，无 id=1 行 → `FOREIGN KEY constraint failed`。趋势报告不需要持久化聚类血缘，**直接内存跑 hdbscan**，不写 cluster 表。（若要持久化，需先建 `embedding_versions` 行。）
- **min_cluster_size 调参**（120 篇）：mcs=3 → 14 簇/45 噪声；mcs=4 → 9/55；mcs=5 → 8/59。选 **mcs=3, min_samples=1**（噪声最少、主题粒度合适）。
- **L2 归一化无效**：Qwen3-Embedding-8B 输出**本就 L2 归一化**（加 normalize 后聚类结果完全不变）。所以高维欧氏 ≈ 余弦，无需额外处理。
- **噪声 ≠ 垃圾**：HDBSCAN 的 45 篇 noise 是长尾/单点。**关键决策：把长尾作为「新兴趋势候选」一并喂给 LLM**，而非丢弃——新兴方向常以单点形式出现在长尾里（实践验证：报告预判的 π-Bench / YoCausal / OSCAR 全来自长尾）。

## 发现（W19-W22, 2026 语料）

- **双轨必须分开看**：学术热度（簇规模×avg_score×novelty/impact）与社区热度（HF likes）**显著背离**，再次印证 CLAUDE.md「不做 ensemble 加权」的规则。
  - 双榜皆前三：**自进化代理技能**（SkillOpt 7.5/208↑）——质量与社区双赢。
  - 最大背离：**视频生成与扩散蒸馏**学术体量第一，社区最高仅 125↑；**VLA/具身**学术中等但 MolmoAct2 347↑ 居社区榜首（落地预期驱动）。
- **典型错位案例**（可作双轨展示的活样本）：
  - 高赞低分：Gamma-World（405↑/5.75，娱乐化多智能体世界）、MinT（219↑/5.75，训练基建）。
  - 高分低赞：**OSCAR（8.0/63↑，2-bit KV 量化，全语料最高 novelty）**、YoCausal（7.25/41↑，因果视角审视视频世界模型）、SpatialBench（7.5/68↑）。
- **预判的新兴方向**：生成式 UI 个人代理、因果视频世界模型、原生多模态（去编码器）、极限 KV 压缩。

## 全 2026 语料扩展（660 篇，W01-W22）+ UMAP 调参

把范围扩到 2026 全部已完成周（W01-W22，660 篇全文分析后），重跑聚类暴露了**高维直聚的退化**，并用 UMAP 解决：

| 配置（660 篇） | 簇数 | 噪声 |
|---|---|---|
| 直聚 eom mcs=5 | **2** | 95（退化成 2 个巨簇，无用）|
| 直聚 eom mcs=3 | 48 | 370（**56%**）|
| 直聚 leaf mcs=5 | 22 | 433（**66%**）|
| **UMAP(10d,cosine) + eom mcs=8** | **33** | **147（22%）** ✅ |
| UMAP(10d) + eom mcs=5 | 46 | 110（17%）|

- **结论：660 篇规模上必须先 UMAP 降维再 HDBSCAN**。4096 维 Qwen 嵌入直聚要么被 EOM 选成 2 个巨簇、要么 >50% 噪声。UMAP 降到 10 维（cosine, n_neighbors=15, min_dist=0）后噪声降到 ~20%、簇数稳定在 30-46（BERTopic 标准套路）。120 篇时直聚还能用（mcs=3 → 14 簇/45 噪声），**到几百篇必须 UMAP**。
- 选 **UMAP10 + eom mcs=8（33 簇 / 78% 覆盖 / 147 长尾）** 作为年度报告配置：簇数可读、覆盖高。`trend_report.py` 已加 `--umap-dims`（默认 10，0 关）和 `--selection-method`（eom/leaf）。
- 装了 `umap-learn`（0.5.12）；脚本对缺库优雅回退到直聚。若纳入生产需加进 `pyproject`。
- **踩坑：`_week()` 年份无关**——少数 12 月发表论文（arXiv `2512.*`，published_date 属上一年 ISO W50-53）会污染按字符串取的周跨度，标题误显示成 "W01-W52"。修复：按周号数值排序、剔除 >45 的跨年 straggler，标签回归真实窗口 W01-W22。
- 双轨结论在全年语料更稳：具身/VLA 学术+社区双热；AI-for-Science、视频深度推理社区超前于学术（点赞峰值 427/524 但簇规模/分靠后）；高效注意力/KV 压缩、音频生成学术高但社区冷。

## 报告改写：briefing → 深度趋势预判（2026-06-01）

第一版报告的「新兴趋势」只是 5 条 bullet 简报，深度不够。改写 `trend_report.py` 的 LLM prompt（计划经 Ultraplan 云端精修、本地执行，见 dev-note 2026-06-01-cloud-local-workflow），定稿为 **6 段结构**：

1. 执行摘要（先给全局结论）
2. 主题速览（33 簇命名 + 一句话，紧凑不展开）
3. 当前热点（双轨排名表，学术 vs 社区并列，不加权）
4. **🎯 新兴趋势深度预判（重心）**——挑 6–10 个方向，**每个写成展开小节**：证据链（逐周动量 W..→W.. 拐点 + novelty + 长尾单点）、上升逻辑（机制推理，非罗列）、代表论文（带 [学术分|likes]）、瓶颈与证伪信号、时间窗+置信度+追踪项。prompt 里**显式禁止退化成简报**。
5. 学术 vs 社区错位（案例 + 模式总结）
6. 追读/追踪清单

关键实现点：
- **聚类原始数据/长尾不再写进报告**（`out.write_text(header + report)`）——但 `cluster_block + noise_block` **仍拼进 `user_content` 喂给 LLM** 作分析依据，只是不输出。「数据是输入、不是产物」。
- 周动量 `week_order` 覆盖**整个语料跨度**（W01-W22），不再硬编码最近 4 周——让趋势推理看到完整周轨迹。
- 每簇代表论文 `by_score` 从 3 篇增到 5 篇，给深度推理更多素材。
- `llm.chat(messages, max_tokens=16000)` 防长输出被截（深报告 ~17K 字符）。
- 产出 `docs/trend-report-2026-detailed.md`（660 篇，10 个深度展开方向）。

## 局限 / 下一步

- 嵌入是 **title+abstract**，非全文；主题聚类够用，但细粒度方法相似性会丢。要更准可改用全文 chunk 级嵌入聚合。
- 仅 4 周、120 篇，「周动量」样本小（每簇每周个位数），趋势方向是定性提示而非统计显著。扩到半年/一年后动量信号会更可靠。
- 个别长尾论文 `published_date` 落在窗口外（如 W18）——它们在 W19-22 的 HF weekly top 中出现属跨期正常现象。
- `trend_report.py` 未持久化到 `weekly_reports` 表（只写 markdown 文件）；若要进生产报告流需补 `embedding_versions` 行后走 `ReporterService`（并先修其 `include` bug）。
