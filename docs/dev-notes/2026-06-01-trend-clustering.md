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

## 局限 / 下一步

- 嵌入是 **title+abstract**，非全文；主题聚类够用，但细粒度方法相似性会丢。要更准可改用全文 chunk 级嵌入聚合。
- 仅 4 周、120 篇，「周动量」样本小（每簇每周个位数），趋势方向是定性提示而非统计显著。扩到半年/一年后动量信号会更可靠。
- 个别长尾论文 `published_date` 落在窗口外（如 W18）——它们在 W19-22 的 HF weekly top 中出现属跨期正常现象。
- `trend_report.py` 未持久化到 `weekly_reports` 表（只写 markdown 文件）；若要进生产报告流需补 `embedding_versions` 行后走 `ReporterService`（并先修其 `include` bug）。
