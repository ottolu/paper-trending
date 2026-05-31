# HF Weekly Top-N PDF 批量 ingest（2026-06-01）

## 目标

把 HuggingFace Daily Papers 按 ISO 周归类，取最近 4 个完整周每周 top-30（按 HF upvotes），
PDF 下载到本地并走 pipeline 入库。产出脚本 `scripts/fetch_hf_weekly.py`。

## HF Weekly API（新发现）

CLAUDE.md 此前只记了 daily 端点。实测 daily_papers 端点支持 `week` 参数：

```
GET https://huggingface.co/api/daily_papers?week=2026-W22
```

- 返回该 ISO 周的 50 篇，**已按 `paper.upvotes` 降序排好**（4 周实测 ordered_desc=True）。
  所以「top-N」= 直接取前 N，无需自己排序。
- 结构与 daily 完全一致（`item.paper.{id,title,upvotes,summary,authors,publishedAt}`、`item.numComments`），
  可直接复用 `HuggingFaceFetcher.parse_response()`。
- `paper.id` 就是 arXiv id。

错误尝试（备查）：路径式 `/api/papers/week/<W>` 返回 404，只有 query 参数 `?week=` 可用。

## 设计决策：以 arXiv ID 为主键，不在磁盘上保留「周」结构

- **选定**：PDF 落 `data/papers/<arxiv_id>/files/versions/<sha256>.pdf`（pipeline 原生布局）。
  周只是**临时 sourcing 过滤器**，不进文件夹、不进列名。唯一保留的周信号是 `paper_sources.hf_likes`
  （该周 upvote 快照）。时间戳靠 `papers.published_date` + arXiv ID 自带。
- **被拒**：按周分目录 `data/weekly/<W>/rankNN_<id>.pdf`。
  理由（用户）：arXiv ID 才是第一性的——全局唯一、跨月重爬天然去重，周结构不是。
- 跨周去重：同一篇出现在两周 top-N 只会是一行（ID 主键）。本次 4 周 × 30 = 120 selections，
  去重后仍是 **120 篇唯一**（不同发表周期，无重叠）。

## 踩坑 recipe

1. **linker 对 HF-only 论文 `pdf_url=None` → 不会建 pdf_fetch**
   `PaperLinker.link()` 只在有 arXiv source 时填 `pdf_url`；HF-only 分支固定 `pdf_url=None`，
   于是 `CollectorService.upsert_paper()` 的 `if lp.pdf_url:` 不成立，不下载。
   **绕过**：这些论文本就是 arXiv 论文，直接构造 `LinkedPaper(pdf_url=f"https://arxiv.org/pdf/{id}", hf_source=rp)`，
   不走 linker。

2. **arXiv PDF URL 必须用无扩展名形式，且 PdfFetcher 不跟随重定向**
   - `https://arxiv.org/pdf/<id>` → `200 application/pdf`（直接命中）
   - `https://arxiv.org/pdf/<id>.pdf` → `301` 重定向到无扩展名形式
   - `PdfFetcher.download_and_store()` 用 `httpx.AsyncClient` 默认 **不 follow_redirects**，
     若用 `.pdf` 形式会把 301 页面当内容存下。**统一用无扩展名**（项目 `batch_download_pdfs.py` 也是这个约定）。

3. **`StageRunner.claim()` 在并发下有 SELECT→UPDATE 竞态（重要）**
   `claim()` 先 `SELECT ... status='pending' LIMIT 1`，再 `UPDATE ... WHERE id=? AND status='pending'`，
   两步非原子。多 worker 并发时两个 claim 抢到同一行 → 都执行
   `INSERT INTO stage_run_attempts(stage_run_id, attempt_no)` → 撞 `UNIQUE(stage_run_id, attempt_no)`，
   抛 `sqlite3.IntegrityError`。
   - `scripts/batch_download_pdfs.py` 用 `try/except` 把异常吞掉并 `failed += 1`，
     表面「成功」实则**静默丢任务**。
   - 本脚本改为 **串行** `process_next`（单 worker，无竞态）。120 篇走 arXiv CDN 串行约 2.5 分钟，
     完全够快，也对 arXiv 友好。
   - 若将来要并发：claim 需改成原子（如 `UPDATE ... WHERE id IN (SELECT ... LIMIT 1) RETURNING *`
     或加进程内 `asyncio.Lock` 只锁 claim 段）。

## 结果

- 120 篇唯一论文，120 个 PDF，**0 失败**，总计 ~1.2 GB，耗时 ~2.5 min（串行）。
- DB：`papers`/`paper_sources`/`paper_files` 各 120；`stage_runs` = pdf_fetch 全 succeeded、
  pdf_parse 全 pending（自动入队，本次**到此为止**，未跑 parse/analyze）。
- 各周 #1：W22 `2605.28816`(405↑) Gamma-World；W21 `2605.12882`(269↑) CiteVQA；
  W20 `2605.06169`(231↑) Mean Mode Screaming；W19 `2605.02881`(347↑) MolmoAct2。

## 复跑

```bash
.venv/bin/python -m scripts.fetch_hf_weekly --weeks 4 --top 30 --data-root data
# 默认锚定「最近 N 个完整 ISO 周」，跳过刚开始的当前周；--today YYYY-MM-DD 可覆盖
```
幂等：`stage_runner.create` 按 `logical_job_key` 去重，PDF 按 sha256 内容寻址，重跑不重复下载。

## pdf_parse 基准（同一 120 篇语料，pymupdf）

`scripts/bench_parse.py` 串行驱动 `PdfParser.process_next()`（parser_name=pymupdf）。

| 指标 | 值 |
|------|----|
| 总耗时 | **328.9s（≈5.5 min）/ 120 篇** |
| 单篇 | avg **2.7s** · median 1.4s · p90 5.5s · **max 51s** |
| 吞吐 | 0.4 篇/s · 11 页/s |
| 页数 | median 27 · mean 31.5 · max 102 · 总 3779 页 |
| 成功率 | **120/120，0 失败** |

**反直觉点：实测比 CLAUDE.md 标称 `~0.5s/篇` 慢约 5×。**
- `~0.5s` 是干净 25 页文本论文的最好情况；HF-top 语料系统性偏大——median 27 页、若干 80–102 页、最大 PDF 52MB（`2605.06548` 99 页 / `2605.18747` 102 页 / 多个 40–50MB 图多论文）。
- 慢的全在尾部：图多/页多 PDF 的块抽取 + `blocks.json`/`sections.json` 序列化是主成本，单篇可达 ~51s。pymupdf 是 CPU 单线程，且 `claim()` 竞态使并发不安全 → 只能串行。
- **规模规划按 ~2.7s/篇**：6 个月（HF weekly top-30 × 26 周 ≈ 780 篇）≈ **35 min**；1 年（× 52 周 ≈ 1560 篇）≈ **70 min**。parse 不是规模瓶颈。

**非致命噪声**：stderr 刷大量 `MuPDF error: ... cannot create appearance stream for Screen annotations` / `cmsOpenProfileFromMem failed`（来自含 Screen 注释/嵌入视频或异常色彩 profile 的 PDF），不影响成功率，跑批时 `2>&1 | grep -v` 过滤即可。

**真正的瓶颈是 analyzer（LLM），不是 parse**：旧基准 ~35–80s/篇；换 `deepseek-v4-pro` thinking 后 per-paper 时延/成本未知，且 thinking 模式丢失 `temperature=0` 确定性。决定半年/一年规模前应先拿 5–10 篇实测 analyzer 真实时延+成本再外推。
