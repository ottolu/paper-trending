# PDF 解析方案调研:2025–2026 轻量选型(喂大模型精读场景)

> 调研日期 2026-06-01。场景:把过去半年~一年的 HF Daily Papers(本质 arXiv,数千篇)在 **M2 MacBook**(Apple Silicon,仅 MPS,无 CUDA)上批量 parse,输出喂给多模态大模型(Claude Opus 4.8)做精读/分析/归档。未来会上 M5 Max / M5 Ultra,但当前以 M2 能批量跑为准。
>
> 方法:deep-research harness,5 角度并行扇出,23 来源 → 113 声明 → 对抗式验证 25 条(22 确认 / 3 推翻)。下文每条结论标注 **[已验证]**(带引用)或 **[未验证]**(研究未覆盖,需本地实测)。

## TL;DR — 颠覆性结论

**对 arXiv 论文,"该用哪个 PDF 解析器"是错的问法。最高杠杆的动作是:~90% 有 LaTeX 源的论文根本不解析 PDF,直接走 arXiv 原生 HTML / ar5iv。** 因为它从 TeX 源经 LaTeXML 生成(不是从渲染后的 PDF 反推),公式是结构化 MathML + 原始 LaTeX,表格/图从源结构重建——直接消灭了"公式乱码、表格塌成一行"这两个最伤下游 LLM 分析的失败模式。PDF 解析退化为 fallback。

## 推荐栈(M2,当前)

```
1. arXiv HTML / ar5iv   ← 主路径,~90% 有源论文。逐篇质量门控
2. Docling (IBM, MIT)   ← PDF-only / 需结构化 markdown 时的 fallback。轻、快、表格强
3. MinerU2.5 (MLX)      ← 公式/表格密集 或 Docling 搞不定的硬骨头。保真最高但慢
   pymupdf (现状)       ← 只需 heading 结构的超快预筛路径(~0.5s/篇)保留
   图/图表             ← 任何路径都单独抽成图片喂多模态 LLM,别信解析器的图内文字
```

未来 M5 Max/Ultra:把 **MinerU2.5(MLX VLM)提升为默认**——每页成本降到可接受,批量也能享受最高保真。

## 决策表

| 方案 | 模型/footprint | M2 速度(估) | 公式 | 表格 | 图 | LLM 适配 | License | 定位 |
|------|---------------|------------|------|------|----|---------|---------|------|
| **arXiv HTML / ar5iv** [已验证] | 无模型,纯 HTTP+HTML | 网络受限,~秒级/篇 | **MathML+原始LaTeX**,最高 | 源结构重建,最高 | TikZ/图保真一般(~75%) | 直接拿到结构 | arXiv/开放 | **主路径** |
| **Docling** (IBM) [已验证] | RT-DETR layout + TableFormer,~数百 MB;峰值 RAM 2.4–6.2GB | ~1.27s/页(M3 Max CPU 实测,M2 更慢;MPS/MLX 路径已落地或可追平) | 有公式处理(传言"无公式模型"已被**推翻**) | TableFormer 还原行列/跨格/无线表 | **默认丢图内文字,只留 caption**,需 opt-in 导图 | Markdown/JSON/HTML,原生 lossless 模型 | **MIT** | **PDF fallback 首选** |
| **MinerU2.5** [已验证] | 1.2B VLM,fp16≈2.4GB(有量化) | ~38s/页(M4 MLX 实测,M2 更慢)≈ pymupdf 的 76× | **→LaTeX**,OmniDocBench 超 GPT-4o/Gemini2.5Pro | **→HTML**,强 | 抽图+caption+脚注 | markdown/json | 需确认(疑 AGPL) | **硬骨头专用** |
| pymupdf(现状) | 无模型 | ~0.5s/页 | 弱(易乱码) | 弱(易塌陷) | 不处理 | 字号 heading | 开放 | 超快预筛 |
| marker(现重型 fallback) | ~2.6GB | **~255s/篇≈10s/页**(M2 实测,旧 dev-note) | 好 | 好 | 一般 | markdown | 受限(疑 GPL) | **两头不靠,bake-off 后删** |
| pymupdf4llm | 无模型 | ~pymupdf 量级 | 弱(启发式) | 基础 md 表 | 不处理 | **LLM-markdown** | 开放 | fast-path 升级候选 |

> 注:MinerU ~38s/页 比 marker ~10s/页 还**慢**——MinerU 是 1.2B VLM 逐页自回归,最慢但保真最高;marker 是中速中保真。所以删 marker 的理由**不是"它最慢"**,而是它**两头不靠**(速度/footprint 被 Docling+pymupdf 压制,保真被 MinerU 压制),没有它当第一选择的场景。

## M2 实测结果(2026-06-01,20 篇真实 HF 论文 / 528 页)

harness:`scripts/parser_bench.py`;样本:5 个 ISO 周(2025-W32 → 2026-W16)各取 upvotes top-4;原始数据:`data/parser_bench/`(gitignored)。

| parser | s/篇 | s/页 | 峰值 RAM | math(代理) | table(代理) | img(代理) | 备注 |
|------|-----|-----|---------|-----------|------------|----------|------|
| **arxiv_html** | ~0(本地读) | — | 45MB | **152.7**(MathML) | **18.1**(`<table>`) | **30.3** | 取后即用,结构碾压 |
| **pymupdf**(现状) | **0.14** | 0.005 | 137MB | 0.2 | 0.7 | 0 | 最快,丢公式/表/图 |
| **pymupdf4llm** | 5.78 | 0.219 | 878MB | 1.5 | **140**(行) | 0 | 表格强,公式/图丢 |
| **docling**(OCR off) | 17.74 | 0.672 | 1712MB | 0.4 | 121(行) | **12.4** | 表格强+捕获图占位,公式 md 弱,最重 |

> math/table/img 是结构代理(跨格式单位不同:html 数 `<math>`/`<table>`,md 数 LaTeX 定界符/`|`行),非最终质量分——那是后续 Opus 4.8 裁判。MinerU2.5 / marker 待后续补跑(已 staged)。

**实测关键发现(部分修正了之前基于代理数的结论):**

1. **arXiv-HTML 在 HF 语料 20/20 命中**(16 native + 4 ar5iv),结构碾压所有 PDF 解析(152 公式 / 18 表 / 30 图 每篇)。HF 精选论文几乎都有 LaTeX 源,这条主路径比通用 arXiv 还稳。
2. **所有 PDF 解析器的 markdown 都不吐 LaTeX 公式**(math 代理全 <2:pymupdf 0.2 / pymupdf4llm 1.5 / docling 0.4)。公式被压成 unicode 或丢失。→ **公式密集的纯 PDF 论文必须靠 MinerU(公式→LaTeX),坐实其"硬骨头专用"定位。**
3. **PDF fallback 里 pymupdf4llm 性价比反超 docling**:3× 快、½ RAM、表格相当(140 vs 121 行);docling 唯一优势是捕获图占位(12.4 vs 0)+ lossless JSON。→ **修正"docling 是 PDF fallback 首选":只要文本+表格 → pymupdf4llm;要图/结构化 JSON/阅读顺序 → docling。**
4. **docling 必须关 OCR**:默认对原生 arXiv PDF 跑 RapidOCR,白白慢数倍且报 "empty result";关掉后 M2 实测 0.672s/页,反而**比公开 M3 Max CPU 数(1.27s/页)还快**(OCR-off + MPS)。
5. caveat:docling 有 formula enrichment 选项(默认关),开启后 markdown 是否吐 LaTeX 未测;公式也可能在它的 JSON 里。本表是默认 markdown 配置。arxiv_html 的 raw HTML 需一个"抽正文 + `<annotation x-tex>` 取 LaTeX + 表格转 md"的清洗步才好喂 LLM。

→ **更新推荐栈**:arXiv HTML(20/20,主路径,+清洗)→ 无 HTML/太新走 PDF:**pymupdf4llm**(默认,要图才上 docling)→ 数学密集纯 PDF:MinerU2.5(待测)→ 超快预筛:pymupdf。

## 删 marker?决定:暂缓,bake-off 后再删

- **结论成立**:marker 在本场景两头不靠——Docling 更快(~1.3 vs ~4s/页 M3Max)、更轻、MIT,保真相当;MinerU2.5 保真更高。marker 还需 Apple Silicon 上 `_patch_surya_mps()` 补丁(surya 升级即失效),最脆。255s/篇 → 5000 篇 ≈ 15 天,批量不可行。**没有一个场景 marker 是最优选。**
- **但先别删代码**:① pymupdf 才是默认,marker 路径**已休眠**,2.6GB 模型未下载,留着零成本;② Docling/MinerU 在 M2 上的保真**还没本地验证**,在替代品被证明前删掉已知可用的 fallback 有风险。
- **行动**:bake-off 里把 marker 当对照 baseline 一起跑;若 Docling+MinerU 在 M2 上确实覆盖 marker 的保真位,**再删 `_run_marker()` + 依赖 + MPS patch**。删除走 git,可逆,不急于这一刻。

## 之前"未验证 6 方案"逐个定性(本轮补查证)

研究首轮没产出它们的可验证数据,是 **harness 的预算/验证过滤所致,不是我判定它们差**。补查证后:

- **pymupdf4llm** [我评估]:纯 Python 无模型,PyMuPDF 的 LLM-markdown 输出,本质是现有 pymupdf 的"免费升级"(更好 markdown + 基础表格),但公式/复杂表仍启发式无 layout 模型。**值得进 bake-off**,可能直接增强 fast path。
- **markitdown**(MS)[已查证]:PDF 走 pdfminer.six **纯文本,无 OCR 无 layout**;表格→纯文本(结构丢)、无 heading 层级;benchmark PDF 成功率仅 **25%**。**对学术论文确实偏弱**,比裸 pymupdf 的结构还差(pymupdf 至少有字号 heading)。轻量但保真垫底,本场景不推荐——用户直觉正确。
- **olmOCR / olmOCR-2**(AllenAI)[已查证]:**7B VLM**(Qwen2.5-VL),BF16≈14GB、6-bit MLX≈6.4GB,**超 1-2GB 预算**;官方为 CUDA/vLLM 高吞吐设计,Apple Silicon 能跑(MLX/GGUF)但 M2 上 7B 逐页生成比 MinerU 1.2B(~38s/页)更慢。olmOCR-Bench 82.4,而 MinerU2.5(小 ~6×)OmniDocBench ~90.67——**MinerU2.5 在效率前沿上支配 olmOCR**:更小更快、benchmark 还更高。质量不差但**对 M2 太重且被支配**,不入选。
- **Nougat**(Meta)[我评估]:2023,~350M,arXiv→md+LaTeX;慢 + OOD 页重复/幻觉 + 基本停更,被 marker/Docling/MinerU 全面超越。**跳过**。
- **GROBID** [我评估]:JVM/CRF,**强在文献结构**(参考文献/作者标题元数据/章节/引文 TEI),轻量快;**但公式/表格非强项**。对"全文+数学喂 LLM"不对口,可作**参考文献/元数据旁路**的可选补充,非主解析器。
- **Surya 直接调** [我评估]:它就是 marker 底层引擎(datalab-to/surya),裸用=自造 marker 且同样有 MPS bug。**无理由替代封装更好的 Docling/MinerU,跳过**。

**净结论**:除 **pymupdf4llm**(加入 bake-off)和 **GROBID**(仅当要参考文献抽取的旁路)外,其余对本场景确实"一般或被支配"。

## 给大模型喂料的保真度风险分析(用户核心关切)

下游是 LLM 不是人,所以"读起来顺不顺"无关,关键是结构语义不被破坏:

- **公式**:`LaTeX/MathML >> 乱码 unicode`。pymupdf 从 PDF 抽数学常把符号变成缺字/错码,LLM 直接误读。arXiv HTML 给干净 LaTeX,MinerU 给 LaTeX,Docling 有数学处理。**[已验证]** 文献(arXiv:2512.09874 等)确认 PDF 公式解析错误会实测劣化下游 LLM/RAG/QA 质量,语义评测 r=0.78 vs 字符匹配 0.34。
- **表格**:`markdown/HTML 表格 >> 纯文本表格`。结构化表格(Docling TableFormer / MinerU HTML / arXiv HTML)保住行列对应关系,LLM 才读得对;纯文本抽取把表格压成一行 word-soup,对齐丢失,LLM 容易张冠李戴。
- **图/图表**:**所有解析器最弱的一环**。多数默认丢图内文字或只留 caption(Docling 明确"丢图内文字、留 caption")。**因下游 Claude Opus 4.8 是多模态,正解是把图单独导成图片直接喂多模态 LLM**,而不是信任任何解析器对图表的 OCR/图内文字。

## arXiv HTML 路径的工程细节(主路径,必须质量门控)[已验证]

- **覆盖率天花板 ~90%**:arXiv 90% 投稿是 TeX 源;ar5iv 04.2024 快照 2,170,799 篇 HTML。**剩 ~10% 纯 PDF 投稿拿不到源生 HTML,仍需 PDF 解析。**
- **逐篇质量不均**:`no_problem` 仅 ~17%(366,232)、`warning` ~60%(1,304,052)、`error` ~23%(500,515)。但 **`error` ≠ 转换失败**(仍产出 HTML,仅 ~3% 彻底失败);~83% 带 warning/error 标记 → **必须逐篇程序化质检后再决定走 HTML 还是 PDF fallback。**
- **时效**:ar5iv 滞后 live arXiv ~1 个月,**最新的 HF Daily Papers 可能还没 HTML**,这部分走 PDF 路径。源覆盖到 2026-04(够覆盖用户目标窗口,"仅 2023-12 后才有 HTML"的说法已被**推翻**,历史语料有回填)。
- `<math>` 元素同时带 MathML 和 `<annotation encoding="application/x-tex">` 原始 TeX,消费端两种都能拿。

## 重要 caveat(别把代理数字当 M2 实测)

- **所有速度都是 M3 Max / M4 代理,不是用户的 M2。** Docling 1.27s/页是 M3 Max **CPU 多线程**(非 MPS),M2 更慢;但 Docling 的 MPS/MLX 路径在基准之后才落地(TableFormer MPS 提速 14–17×、M 系自动选 GraniteDocling-258M-mlx),当前 M2 实跑可能追平甚至超过那个旧 CPU 数字。MinerU ~38s/页是第三方 M4 数,M2 未测。
- Docling 速度/内存来自 IBM 一方自测(arXiv:2501.17887 / 2408.09869),版本已迭代;超大文档(数千页)新版内存可能 ×3,但 8–30 页 arXiv 论文 footprint 仍温和。
- MinerU MLX 有版本钉子(mlx 0.31.1 可用,0.31.2 报错)、历史 Apple Silicon 抽风(M1 "Illegal hardware instruction"、MPS batch 比例 bug);**纯 CPU 是可靠 fallback 但慢得多**。
- **3 条被推翻的声明**(别采信):① Docling 无公式模型(0-3,假);② arXiv HTML 仅 2023-12 后(0-3,假);③ MinerU2.5-Pro-2604 命名(1-2,未证)。

## Open items(研究未覆盖,需直接实测)

1. **真·M2 数字**:Docling 与 MinerU2.5(MLX)在用户这台 M2 上,对一批真实 HF 论文的 实测 秒/页、峰值 RAM、以及"数千篇要跑几小时"的真实吞吐。
2. **pymupdf4llm / Nougat / GROBID / markitdown / olmOCR / Surya** 在 公式/表格/图保真 × footprint × M2 速度 上的真实位置——本次无可验证数据,决策表对它们是空的。
3. **用户语料的 HTML 命中率**:过去 6–12 个月 HF 语料里 clean/warning/error 级 HTML 各占多少,质量门控阈值怎么定。
4. **保真度到底值不值**:在这批语料上,喂 markdown/HTML 表格 + LaTeX/MathML 公式,相比纯文本,是否实测提升 Claude Opus 4.8 的分析质量?break-even 在哪?

## 来源(主)

- Docling 技术报告 arXiv:2501.17887;arXiv:2408.09869v5(速度/内存/图丢失行为)
- MinerU github.com/opendatalab/mineru + changelog(MLX 后端 v2.6.3,2025-10-31)
- ar5iv.labs.arxiv.org;SIGMathLing ar5iv 数据集;arXiv:2402.08954(arXiv 官方 HTML 工程)
- 公式保真对下游影响:arXiv:2512.09874、2401.12599;OmniDocBench(CVPR2025)

---
完整研究 JSON(105 agent / ~340 万 token):session task `w4sqckqoe` 输出。
