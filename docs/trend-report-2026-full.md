# AI 研究趋势报告 — HF Weekly W01-W22 (2026)

> 语料：660 篇全文分析论文 | 33 个主题簇（147 篇离群） | HDBSCAN(mcs=8, eom) | 模型 deepseek-v4-pro

好的，这是对 2026 年 W01-W22 期间 HuggingFace 高热论文的分析报告。

---

### **2026 W01-W22 AI 研究趋势报告**

#### **1. 主题命名**

以下是基于聚类结果对 33 个主要研究主题的命名：

*   **cluster-0: 具身智能与视觉-语言-动作模型** (Embodied AI & VLA Models)
*   **cluster-27: 多模态评估与视觉推理基准** (Multimodal Evaluation & Visual Reasoning Benchmarks)
*   **cluster-3: 音频生成与语音交互基准** (Audio Generation & Speech Interaction Benchmarks)
*   **cluster-16: 高效长上下文与稀疏注意力机制** (Efficient Long-Context & Sparse Attention Mechanisms)
*   **cluster-22: 视频世界模型与可控生成** (Video World Models & Controllable Generation)
*   **cluster-6: 自我进化与技能迁移的智能体** (Self-Evolving & Skill-Transferable Agents)
*   **cluster-11: 面向科学发现的自主研究智能体** (Autonomous Research Agents for Scientific Discovery)
*   **cluster-4: 记忆增强的多模态智能体** (Memory-Augmented Multimodal Agents)
*   **cluster-31: 统一多模态理解与生成** (Unified Multimodal Understanding & Generation)
*   **cluster-2: 深度视频理解与因果推理** (Deep Video Understanding & Causal Reasoning)
*   **cluster-9: 高级代码生成与软件工程智能体** (Advanced Code Generation & SWE Agents)
*   **cluster-12: 图形用户界面智能体与世界模型** (GUI Agents & World Models)
*   **cluster-26: 推理模型的知识蒸馏与对齐** (Knowledge Distillation & Alignment for Reasoning Models)
*   **cluster-29: 推理模型的强化学习优化策略** (RL Optimization Strategies for Reasoning Models)
*   **cluster-10: 智能体搜索与深度信息检索** (Agentic Search & Deep Information Retrieval)
*   **cluster-13: 多智能体安全与治理** (Multi-Agent Safety & Governance)
*   **cluster-8: 长视频生成与实时扩散蒸馏** (Long Video Generation & Real-time Diffusion Distillation)
*   **cluster-15: 递归语言模型与测试时训练** (Recursive LMs & Test-Time Training)
*   **cluster-23: 智能图像编辑与自动优化** (Intelligent Image Editing & Auto-Optimization)
*   **cluster-18: 面向工作流的智能体基准** (Workflow-Oriented Agent Benchmarks)
*   **cluster-28: 推理模型中的创造力与多样性** (Creativity & Diversity in Reasoning Models)
*   **cluster-25: 工具增强的多模态推理** (Tool-Augmented Multimodal Reasoning)
*   **cluster-5: 视觉空间智能与3D场景理解** (Visual Spatial Intelligence & 3D Scene Understanding)
*   **cluster-24: 思维链机制与推理自省** (Chain-of-Thought Mechanisms & Reasoning Introspection)
*   **cluster-7: 面向代码生成的强化学习** (Reinforcement Learning for Code Generation)
*   **cluster-30: 高效图像生成与表示压缩** (Efficient Image Generation & Representation Compression)
*   **cluster-19: 智能体工作流与架构综述** (Agent Workflow & Architecture Surveys)
*   **cluster-20: 人物交互与视频合成** (Human-Object Interaction & Video Synthesis)
*   **cluster-21: 新视角合成与3D重建** (Novel View Synthesis & 3D Reconstruction)
*   **cluster-17: 混合专家与测试时规模化推理** (Mixture-of-Experts & Test-Time Scaling for Reasoning)
*   **cluster-32: 统一多模态推理与空间智能** (Unified Multimodal Reasoning & Spatial Intelligence)
*   **cluster-1: 基础世界模型与综述** (Foundational World Models & Surveys)
*   **cluster-14: 通用智能体能力的基准测试** (Benchmarking Generalist Agent Capabilities)

---

#### **2. 当前热点 Topic (排名)**

*说明：学术热度综合考虑簇规模、平均分和新颖性/影响力；社区热度依据 HF likes。两者独立呈现。*

| 排名 | 学术热点 (Academic Hotness) | 社区热点 (Community Buzz) | 分析 |
| :--- | :--- | :--- | :--- |
| **1** | **具身智能与视觉-语言-动作模型 (VLA)** <br>规模大(35)，影响力高(6.1)，代表论文如 `Qwen-VLA` 和 `MolmoAct2`，表明学界正集中攻克通用机器人模型。 | **深度视频理解与因果推理** <br>`A Very Big Video Reasoning Suite` (524↑) 和 `Demystifing Video Reasoning` (372↑) 引爆社区，表明公众对超越简单描述、进行深度因果推理的视频AI抱有极大热情。 | **背离**：学术上更注重系统构建(VLA)，而社区对挑战认知边界(“推理”而非“生成”)的视频理解表现出极高热度。视频推理成为现象级话题。 |
| **2** | **高效长上下文与稀疏注意力机制** <br>高学术分(8.0， `OSCAR`)和创新的注意力机制研究(`FASA`， `Attention Residuals`)使其成为底层架构研究的最前沿。 | **具身智能与视觉-语言-动作模型 (VLA)** <br>`MolmoAct2` (347↑) 和 `CARLA-Air` (343↑) 等论文的高点赞数，说明社区对能在真实世界中部署和操作的AI系统极为期待。 | **一致**：VLA 主题同时获得了学界和社区的青睐，是公认的硬科技方向，预示着“从数字世界走向物理世界”的趋势。 |
| **3** | **自我进化与技能迁移的智能体** <br>该簇论文(`SkillOpt`, 208↑)质量高且概念新颖(新颖性6.4)，聚焦于让智能体在开放世界中自我提升，学术价值显著。 | **面向代码生成的强化学习** <br>`GrandCode` (630↑) 以现象级热度登顶，`InCoder-32B` (311↑)紧随其后，表明社区对能解决实际编程挑战、提升生产力的AI工具有强烈现实需求。 | **背离**：学界在探索智能体的通用进化能力，而社区对直接转化为生产力的代码生成工具最为买单。产品化潜力直接驱动热度。 |
| **4** | **面向科学发现的自主研究智能体** <br>虽然论文数量不多(21)，但 `AI Can Learn Scientific Taste` (427↑) 等高分论文，展示了用AI加速科学研究的巨大潜力，学术新颖性极高。 | **多智能体安全与治理** <br>`The Devil Behind Moltbook...` (197↑) 等关于AI自我进化导致安全失效的论文引发了社区对AI风险的广泛讨论，安全问题始终是高热议题。 | **背离**：学术界在谨慎地构建AI科学家，而社区对AI失控的风险更为敏感，这种“能力”与“安全”的关注度分离是典型现象。 |
| **5** | **视频世界模型与可控生成** <br>规模可观(25)，`Lyra 2.0` 和 `Generative World Renderer` 等研究，从生成单一视频走向构建可交互、可探索的动态世界。 | **推理模型中的创造力与多样性** <br>`Rewarding the Rare` (150↑) 等论文，关注让模型跳出模式化思维，产生新颖解决方案，触及了人们对“真智能”的想象，引发广泛讨论。 | **背离**：学术热点在于构建复杂的视频世界，而社区热点在于解锁模型的创造性思维。前者是工程实现，后者是能力边界探索。 |

---

#### **3. 预判的上升/新兴趋势**

基于周动量 (W19→W22) 增长、高新颖性小簇以及长尾论文，我们预判以下方向将成为未来热点：

*   **趋势一：世界模型的“可交互化”与“具身化”**
    *   **信号**：`cluster-22` (视频世界模型) W22 出现多个新论文，`Lyra 2.0` (可探索3D世界)和 `Gamma-World` (多智能体世界建模，405↑高热) 预示着从“看”到“进入”的范式转变。
    *   **长尾候补证据**：`CADEvolve` (通过程序进化创建逼真CAD世界)、`Agentic World Modeling...` (世界模型综述，227↑) 正填补了世界模型与智能体间的空白。未来的关键在于构建物理规则一致、支持多智能体交互的“模拟器”。

*   **趋势二：“自我进化”智能体的安全对齐与治理**
    *   **信号**：`cluster-6` (自我进化智能体) 和 `cluster-13` (多智能体安全) 并列存在。`The Devil Behind Moltbook...` (197↑) 点名“自我进化AI社会中安全消失”，这不再是哲学讨论，而是现实技术问题。
    *   **长尾候补证据**：`AgentDoG 1.5` (127↑) 和 `Hyperagents` (51↑) 开始提出轻量级、可扩展的对齐框架。研究方向将从“对齐静态模型”转向“约束和治理动态进化的智能体社会”。

*   **趋势三：强化学习(RL)加速科学发现**
    *   **信号**：`cluster-11` (科学发现智能体) 论文质量高且新颖，`AI Can Learn Scientific Taste` (427↑) 引爆社区。表明 RL 不仅能解数学题，更能学习“科学品味”，自主提出和验证假说。
    *   **长尾候补证据**：`MOOSE-Star` (为科学发现突破复杂性障碍) 和 `ResearchMath-14K` (用智能体扩展研究级数学) 是此趋势的具体落地。未来是构建垂直领域的“AI科学家”，如材料、生物、数学。

*   **趋势四：挑战“推理黑盒” — 思维链的机制与自省**
    *   **信号**：`cluster-24` (思维链机制) 高新颖性(6.1)，`Can LLMs Predict Their Own Failures?` (86↑) 和 `Does Your Reasoning Model Implicitly Know When to Stop Thinking?` (266↑) 直接拷问模型的元认知能力。
    *   **长尾候补证据**：`The Flexibility Trap...` (扩散语言模型的推理局限，74↑) 和 `Imagination Helps Visual Reasoning, But Not Yet in Latent Space` (44↑) 表明，理解并突破当前推理模式的根本局限，是通往下一代的钥匙。

*   **趋势五：“统一多模态理解与生成"的新范式**
    *   **信号**：`cluster-31` (统一多模态模型) 在W21、W22保持热度，`LLaDA2.0-Uni` (242↑) 和 `ERNIE 5.0` (269↑) 等技术报告表明头部玩家正在统一架构上取得突破。
    *   **长尾候补证据**：`Omni-Diffusion` (50↑) 和 `Unified Latents (UL)` (60↑) 探索用扩散模型或统一潜在空间实现“任何到任何”的生成。这是超越Transformer，探索下一代多模态基础模型的路线之争。

---

#### **4. 学术 vs 社区错位案例**

**高社区热度，低学术评分 (产品/话题驱动)**

*   **案例一: `GrandCode: Achieving Grandmaster Level...` (cluster-7)**
    *   **社区热度: 630 ↑ (本期最高)** vs. **学术分: 未入簇顶**。
    *   **原因**: 极强的结果导向。“Grandmaster level”是对程序员生产力的直接承诺，极具传播力。社区追捧其“能用、好用”的潜力，而非论文提出的RL训练方法本身是否具备根本性创新。这是典型的**产品发布式论文**，价值在于工程实现和性能突破。

*   **案例二: `A Very Big Video Reasoning Suite` (cluster-2)**
    *   **社区热度: 524 ↑** vs. **学术分: 未入簇顶**。
    *   **原因**: 名字本身就极具话题性，“Very Big”和“Reasoning Suite”结合，击中了社区对“造个大基准测尽模型”这一模式的复杂情感（嘲讽与期待并存）。论文更多是工程贡献和资源发布，而非理论突破，但其引发的关于评测的讨论具有极高的社区价值。

*   **案例三: `Adam's Law: Textual Frequency Law...` (cluster-15)**
    *   **社区热度: 503 ↑** vs. **学术分: 中等(7.0)**。
    *   **原因**: 标题模仿物理学定律，声称发现了一种语言学或AI的根本规律，这种“宏大叙事”极易在社交媒体上走红。虽然其严谨性需要时间检验，但“发现定律”这个概念本身就足以吸引眼球，属于**话题驱动型传播**。

**高学术评分，低社区热度 (被低估的潜力)**

*   **案例一: `ACES: Who Tests the Tests? Leave-One-Out AUC...` (cluster-9)**
    *   **学术分: 8.5 (本期最高之一)** vs. **社区热度: 53 ↑**。
    *   **原因**: 研究代码生成评测基准本身可靠性的元研究。标题偏学术、问题抽象，远离“造个大模型”的热闹。但这却是奠定整个代码生成领域进步的基石。**它被严重低估了**，其提出的评估方法可能成为未来评测的标准，值得所有关注模型评估的研究者深读。

*   **案例二: `OSCAR: Offline Spectral Covariance-Aware Rotation...` (cluster-16)**
    *   **学术分: 8.0 (本期最高之一)** vs. **社区热度: 63 ↑**。
    *   **原因**: 极硬核的底层架构研究，关注2-bit KV缓存量化等工程细节，技术门槛高，难以被大众理解和传播。但这正是降低大模型推理成本、实现端侧部署的关键技术，**商业价值和基础设施意义巨大**，是被掩盖的明珠。

*   **案例三: `Recursive Language Models` (cluster-15)**
    *   **学术分: 7.5** vs. **社区热度: 96 ↑**。
    *   **原因**: 提出了与现有Transformer完全不同的递归架构，概念新颖。但由于缺乏像“Grandmaster”那样直观且震撼的结果展示，其长期影响力远未被社区充分认识。这是**高风险、高回报的种子型研究**，如果成功，将开启新范式。

---
## 附：聚类信号原始数据

### cluster-0 (n=35)
week momentum: W19:4 W20:2 W21:0 W22:1 | avg_score=6.18 (novelty 5.8, impact 6.1) | HF likes median=59 max=347
tags: vision-language-action, embodied AI, robotic manipulation, robot manipulation, flow matching, Vision-Language-Action
top papers (by score): [7.5|103↑] Qwen-VLA: Unifying Vision-Language-Action Modeling across Tasks, Environments, and Robot Embodiments; [7.5|26↑] TOPReward: Token Probabilities as Hidden Zero-Shot Rewards for Robotics; [7.0|347↑] MolmoAct2: Action Reasoning Models for Real-world Deployment
most upvoted: [347↑] MolmoAct2: Action Reasoning Models for Real-world Deployment; [343↑] CARLA-Air: Fly Drones Inside a CARLA World -- A Unified Infrastructure for Air-Ground Embodied Intelligence

### cluster-27 (n=30)
week momentum: W19:2 W20:0 W21:1 W22:1 | avg_score=6.35 (novelty 6.0, impact 6.2) | HF likes median=86 max=201
tags: reinforcement learning, benchmark, vision-language models, vision-language model, visual grounding, evaluation
top papers (by score): [7.75|101↑] OpenSearch-VL: An Open Recipe for Frontier Multimodal Search Agents; [7.5|169↑] Perception or Prejudice: Can MLLMs Go Beyond First Impressions of Personality?; [7.25|50↑] TerraScope: Pixel-Grounded Visual Reasoning for Earth Observation
most upvoted: [201↑] BabyVision: Visual Reasoning Beyond Language; [196↑] STEP3-VL-10B Technical Report

### cluster-3 (n=28)
week momentum: W19:1 W20:1 W21:3 W22:0 | avg_score=6.19 (novelty 5.7, impact 6.3) | HF likes median=57 max=248
tags: benchmark, text-to-speech, speech synthesis, automatic speech recognition, open-source, reinforcement learning
top papers (by score): [7.5|151↑] OmniLottie: Generating Vector Animations via Parameterized Lottie Tokens; [7.25|149↑] When Vision Speaks for Sound; [7.25|25↑] MAEB: Massive Audio Embedding Benchmark
most upvoted: [248↑] SocialOmni: Benchmarking Audio-Visual Social Interactivity in Omni Models; [246↑] SQuTR: A Robustness Benchmark for Spoken Query to Text Retrieval under Acoustic Noise

### cluster-16 (n=26)
week momentum: W19:1 W20:1 W21:2 W22:0 | avg_score=6.34 (novelty 6, impact 6.2) | HF likes median=56 max=328
tags: sparse attention, efficient inference, long-context, KV cache compression, depth scaling, attention mechanism
top papers (by score): [8.0|63↑] OSCAR: Offline Spectral Covariance-Aware Rotation for 2-bit KV Cache Quantization; [7.25|154↑] FASA: Frequency-aware Sparse Attention; [7.0|185↑] Attention Residuals
most upvoted: [328↑] mHC: Manifold-Constrained Hyper-Connections; [231↑] Mean Mode Screaming: Mean--Variance Split Residuals for 1000-Layer Diffusion Transformers

### cluster-22 (n=25)
week momentum: W19:1 W20:1 W21:0 W22:3 | avg_score=6.29 (novelty 6.1, impact 6.2) | HF likes median=70 max=405
tags: video generation, world models, diffusion models, camera control, dataset, video diffusion models
top papers (by score): [7.5|100↑] WBench: A Comprehensive Multi-turn Benchmark for Interactive Video World Model Evaluation; [7.25|41↑] Lyra 2.0: Explorable Generative 3D Worlds; [7.0|102↑] Generative World Renderer
most upvoted: [405↑] Gamma-World: Generative Multi-Agent World Modeling Beyond Two Players; [156↑] Out of Sight but Not Out of Mind: Hybrid Memory for Dynamic Video World Models

### cluster-6 (n=21)
week momentum: W19:2 W20:1 W21:2 W22:0 | avg_score=6.42 (novelty 6.4, impact 6.1) | HF likes median=85 max=291
tags: LLM agents, reinforcement learning, skill evolution, continual learning, transfer learning, skill library
top papers (by score): [7.5|208↑] SkillOpt: Executive Strategy for Self-Evolving Agent Skills; [7.25|46↑] SkillOS: Learning Skill Curation for Self-Evolving Agents; [7.25|53↑] Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills
most upvoted: [291↑] SkillClaw: Let Skills Evolve Collectively with Agentic Evolver; [208↑] SkillOpt: Executive Strategy for Self-Evolving Agent Skills

### cluster-11 (n=21)
week momentum: W19:1 W20:0 W21:3 W22:0 | avg_score=6.12 (novelty 6.0, impact 5.8) | HF likes median=71 max=427
tags: benchmark, autonomous research, scientific discovery, LLM agents, deep research, evaluation
top papers (by score): [7.5|21↑] ResearchGym: Evaluating Language Model Agents on Real-World AI Research; [7.25|29↑] AutoResearchBench: Benchmarking AI Agents on Complex Scientific Literature Discovery; [7.25|52↑] FS-Researcher: Test-Time Scaling for Long-Horizon Research Tasks with File-System-Based Agents
most upvoted: [427↑] AI Can Learn Scientific Taste; [228↑] PaperBanana: Automating Academic Illustration for AI Scientists

### cluster-4 (n=19)
week momentum: W19:2 W20:3 W21:0 W22:0 | avg_score=6.08 (novelty 5.8, impact 5.7) | HF likes median=59 max=147
tags: retrieval-augmented generation, benchmark, LLM agents, multimodal memory, memory-augmented agents, long-context understanding
top papers (by score): [7.75|75↑] MemLens: Benchmarking Multimodal Long-Term Memory in Large Vision-Language Models; [7.0|62↑] MemEye: A Visual-Centric Evaluation Framework for Multimodal Agent Memory; [6.75|59↑] KnowMe-Bench: Benchmarking Person Understanding for Lifelong Digital Companions
most upvoted: [147↑] MemPrivacy: Privacy-Preserving Personalized Memory Management for Edge-Cloud Agents; [124↑] δ-mem: Efficient Online Memory for Large Language Models

### cluster-31 (n=19)
week momentum: W19:0 W20:2 W21:1 W22:2 | avg_score=6.42 (novelty 6, impact 6.3) | HF likes median=71 max=269
tags: text-to-image generation, image editing, unified multimodal model, multimodal understanding, multimodal large language models, mixture-of-experts
top papers (by score): [7.25|140↑] Modality Gap-Driven Subspace Alignment Training Paradigm For Multimodal Large Language Models; [7.0|105↑] Beyond Language Modeling: An Exploration of Multimodal Pretraining; [7.0|269↑] ERNIE 5.0 Technical Report
most upvoted: [269↑] ERNIE 5.0 Technical Report; [242↑] LLaDA2.0-Uni: Unifying Multimodal Understanding and Generation with Diffusion Large Language Model

### cluster-2 (n=18)
week momentum: W19:1 W20:0 W21:0 W22:1 | avg_score=6.62 (novelty 6.3, impact 6.3) | HF likes median=66 max=524
tags: video understanding, multimodal large language models, benchmark, GRPO, reinforcement learning, video reasoning
top papers (by score): [7.5|236↑] Video-MME-v2: Towards the Next Stage in Benchmarks for Comprehensive Video Understanding; [7.25|41↑] YoCausal: How Far is Video Generation from World Model? A Causality Perspective; [7.0|73↑] A Simple Baseline for Streaming Video Understanding
most upvoted: [524↑] A Very Big Video Reasoning Suite; [372↑] Demystifing Video Reasoning

### cluster-9 (n=17)
week momentum: W19:0 W20:0 W21:0 W22:0 | avg_score=6.6 (novelty 6.5, impact 6.5) | HF likes median=67 max=126
tags: software engineering, LLM evaluation, code agents, code generation, reinforcement learning, benchmark
top papers (by score): [8.5|53↑] ACES: Who Tests the Tests? Leave-One-Out AUC Consistency for Code Generation; [7.5|26↑] PlayCoder: Making LLM-Generated GUI Code Playable; [7.25|57↑] BeyondSWE: Can Current Code Agent Survive Beyond Single-Repo Bug Fixing?
most upvoted: [126↑] daVinci-Dev: Agent-native Mid-training for Software Engineering; [125↑] QuanBench+: A Unified Multi-Framework Benchmark for LLM-Based Quantum Code Generation

### cluster-12 (n=16)
week momentum: W19:0 W20:1 W21:2 W22:1 | avg_score=6.23 (novelty 5.8, impact 6.4) | HF likes median=68 max=201
tags: reinforcement learning, GUI agents, benchmark, computer-use agents, mobile GUI agents, GRPO
top papers (by score): [7.25|58↑] MobileGym: A Verifiable and Highly Parallel Simulation Platform for Mobile GUI Agent Research; [7.0|201↑] Code2World: A GUI World Model via Renderable Code Generation; [6.75|81↑] OpenComputer: Verifiable Software Worlds for Computer-Use Agents
most upvoted: [201↑] Code2World: A GUI World Model via Renderable Code Generation; [158↑] UI-Venus-1.5 Technical Report

### cluster-26 (n=16)
week momentum: W19:2 W20:3 W21:0 W22:0 | avg_score=6.44 (novelty 6, impact 6.3) | HF likes median=61 max=195
tags: reinforcement learning, knowledge distillation, GRPO, on-policy distillation, self-distillation, large language models
top papers (by score): [7.5|35↑] How to Fine-Tune a Reasoning Model? A Teacher-Student Cooperation Framework to Synthesize Student-Consistent SFT Data; [7.25|109↑] Rethinking On-Policy Distillation of Large Language Models: Phenomenology, Mechanism, and Recipe; [7.25|36↑] Self-Distillation Enables Continual Learning
most upvoted: [195↑] Anti-Self-Distillation for Reasoning RL via Pointwise Mutual Information; [176↑] Self-Distilled RLVR

### cluster-29 (n=15)
week momentum: W19:2 W20:0 W21:1 W22:2 | avg_score=6.2 (novelty 5.7, impact 5.9) | HF likes median=81 max=352
tags: reinforcement learning, GRPO, mathematical reasoning, large language models, RLVR, language model alignment
top papers (by score): [7.25|81↑] ProRL: Effective Reinforcement Learning for Proactive Recommendation via Rectified Policy Gradient Estimation; [7.0|204↑] DelTA: Discriminative Token Credit Assignment for Reinforcement Learning from Verifiable Rewards; [7.0|158↑] Your Group-Relative Advantage Is Biased
most upvoted: [352↑] FIPO: Eliciting Deep Reasoning with Future-KL Influenced Policy Optimization; [232↑] GDPO: Group reward-Decoupled Normalization Policy Optimization for Multi-reward RL Optimization

### cluster-10 (n=14)
week momentum: W19:2 W20:0 W21:0 W22:2 | avg_score=6.25 (novelty 5.9, impact 6.2) | HF likes median=65 max=149
tags: reinforcement learning, agentic search, large language models, deep research agents, LLM Agents, information retrieval
top papers (by score): [7.25|71↑] Learning to Retrieve from Agent Trajectories; [6.75|54↑] Self-Improving Language Models with Bidirectional Evolutionary Search; [6.75|38↑] Web2BigTable: A Bi-Level Multi-Agent LLM System for Internet-Scale Information Search and Extraction
most upvoted: [149↑] OpenSeeker: Democratizing Frontier Search Agents by Fully Open-Sourcing Training Data; [117↑] Beyond Semantic Similarity: Rethinking Retrieval for Agentic Search via Direct Corpus Interaction

### cluster-13 (n=14)
week momentum: W19:0 W20:1 W21:1 W22:1 | avg_score=5.95 (novelty 5.8, impact 5.8) | HF likes median=53 max=197
tags: multi-agent systems, LLM agents, AI safety, large language models, synthetic data, governance
top papers (by score): [7.0|127↑] AgentDoG 1.5: A Lightweight and Scalable Alignment Framework for AI Agent Safety and Security; [7.0|54↑] Auditing Agent Harness Safety; [6.75|51↑] Hyperagents
most upvoted: [197↑] The Devil Behind Moltbook: Anthropic Safety is Always Vanishing in Self-Evolving AI Societies; [127↑] AgentDoG 1.5: A Lightweight and Scalable Alignment Framework for AI Agent Safety and Security

### cluster-8 (n=14)
week momentum: W19:2 W20:2 W21:2 W22:0 | avg_score=6.45 (novelty 6.1, impact 6.3) | HF likes median=96 max=187
tags: long video generation, video generation, diffusion models, distribution matching distillation, autoregressive video generation, diffusion distillation
top papers (by score): [7.25|53↑] PackForcing: Short Video Training Suffices for Long Video Sampling and Long Context Inference; [7.25|187↑] Helios: Real Real-Time Long Video Generation Model; [7.25|51↑] Stream-DiffVSR: Low-Latency Streamable Video Super-Resolution via Auto-Regressive Diffusion
most upvoted: [187↑] Helios: Real Real-Time Long Video Generation Model; [155↑] ShotStream: Streaming Multi-Shot Video Generation for Interactive Storytelling

### cluster-15 (n=13)
week momentum: W19:1 W20:0 W21:1 W22:0 | avg_score=6.35 (novelty 6.2, impact 6.2) | HF likes median=46 max=503
tags: large language models, reinforcement learning, test-time training, language modeling, code generation, continual learning
top papers (by score): [7.5|96↑] Recursive Language Models; [7.25|32↑] Test-Time Training with KV Binding Is Secretly Linear Attention; [7.0|25↑] Length Value Model: Scalable Value Pretraining for Token-Level Length Modeling
most upvoted: [503↑] Adam's Law: Textual Frequency Law on Large Language Models; [96↑] Recursive Language Models

### cluster-23 (n=12)
week momentum: W19:0 W20:0 W21:0 W22:1 | avg_score=6.02 (novelty 5.7, impact 5.7) | HF likes median=47 max=137
tags: image editing, diffusion models, reinforcement learning, chain-of-thought, Multi-Teacher Distillation, LoRA
top papers (by score): [6.5|47↑] SmartPhotoCrafter: Unified Reasoning, Generation and Optimization for Automatic Photographic Image Editing; [6.5|64↑] VIBE: Visual Instruction Based Editor; [6.5|48↑] RL-AWB: Deep Reinforcement Learning for Auto White Balance Correction in Low-Light Night-time Scenes
most upvoted: [137↑] From Scale to Speed: Adaptive Test-Time Scaling for Image Editing; [64↑] VIBE: Visual Instruction Based Editor

### cluster-18 (n=12)
week momentum: W19:0 W20:1 W21:2 W22:0 | avg_score=6.79 (novelty 6.3, impact 6.4) | HF likes median=76 max=174
tags: benchmark, LLM agents, tool use, large language models, enterprise automation, agent architectures
top papers (by score): [7.75|102↑] π-Bench: Evaluating Proactive Personal Assistant Agents in Long-Horizon Workflows; [7.25|66↑] OccuBench: Evaluating AI Agents on Real-World Professional Tasks via Language World Models; [7.25|37↑] Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces
most upvoted: [174↑] TransitLM: A Large-Scale Dataset and Benchmark for Map-Free Transit Route Generation; [149↑] EnterpriseOps-Gym: Environments and Evaluations for Stateful Agentic Planning and Tool Use in Enterprise Settings

### cluster-28 (n=11)
week momentum: W19:0 W20:0 W21:1 W22:1 | avg_score=6.59 (novelty 6.2, impact 6.4) | HF likes median=67 max=150
tags: reinforcement learning, GRPO, reasoning, large language models, diversity, mathematical reasoning
top papers (by score): [7.5|67↑] RAGEN-2: Reasoning Collapse in Agentic RL; [7.0|59↑] How Far Can Unsupervised RLVR Scale LLM Training?; [6.75|101↑] KnowRL: Boosting LLM Reasoning via Reinforcement Learning with Minimal-Sufficient Knowledge Guidance
most upvoted: [150↑] Rewarding the Rare: Uniqueness-Aware RL for Creative Problem Solving in LLMs; [144↑] The Past Is Not Past: Memory-Enhanced Dynamic Reward Shaping

### cluster-25 (n=11)
week momentum: W19:0 W20:0 W21:1 W22:1 | avg_score=5.91 (novelty 5.4, impact 5.6) | HF likes median=61 max=150
tags: reinforcement learning, GRPO, tool use, tool-augmented reasoning, agentic reasoning, multimodal
top papers (by score): [7.0|48↑] AdaReasoner: Dynamic Tool Orchestration for Iterative Visual Reasoning; [6.75|79↑] Agent Explorative Policy Optimization for Multimodal Agentic Reasoning; [6.75|61↑] Baichuan-M3: Modeling Clinical Inquiry for Reliable Medical Decision-Making
most upvoted: [150↑] From Blind Spots to Gains: Diagnostic-Driven Iterative Training for Large Multimodal Models; [83↑] IndusAgent: Reinforcing Open-Vocabulary Industrial Anomaly Detection with Agentic Tools

### cluster-5 (n=11)
week momentum: W19:0 W20:0 W21:0 W22:1 | avg_score=6.73 (novelty 6.4, impact 6.4) | HF likes median=68 max=247
tags: vision-language models, 3D scene understanding, spatial reasoning, 3D reconstruction, benchmark evaluation, 3D reasoning
top papers (by score): [7.5|68↑] SpatialBench: Is Your Spatial Foundation Model an All-Round Player?; [7.25|72↑] HERMES++: Toward a Unified Driving World Model for 3D Scene Understanding and Generation; [7.25|67↑] ReVSI: Rebuilding Visual Spatial Intelligence Evaluation for Accurate Assessment of VLM 3D Reasoning
most upvoted: [247↑] WildDet3D: Scaling Promptable 3D Detection in the Wild; [95↑] Generation Models Know Space: Unleashing Implicit 3D Priors for Scene Understanding

### cluster-24 (n=11)
week momentum: W19:1 W20:0 W21:0 W22:0 | avg_score=6.52 (novelty 6.1, impact 6) | HF likes median=74 max=266
tags: chain-of-thought, reinforcement learning, prompt engineering, efficient reasoning, overthinking, large reasoning models
top papers (by score): [7.25|86↑] Can LLMs Predict Their Own Failures? Self-Awareness via Internal Circuits; [7.0|38↑] Reasoning Models Struggle to Control their Chains of Thought; [6.75|60↑] The Molecular Structure of Thought: Mapping the Topology of Long Chain-of-Thought Reasoning
most upvoted: [266↑] Does Your Reasoning Model Implicitly Know When to Stop Thinking?; [150↑] Efficient Reasoning with Balanced Thinking

### cluster-7 (n=11)
week momentum: W19:0 W20:0 W21:0 W22:0 | avg_score=6.11 (novelty 6, impact 6.4) | HF likes median=103 max=630
tags: code generation, reinforcement learning, LLM fine-tuning, data engineering, synthetic data generation, large language models
top papers (by score): [7.25|99↑] CUDA Agent: Large-Scale Agentic RL for High-Performance CUDA Kernel Generation; [6.75|89↑] Programming with Data: Test-Driven Data Engineering for Self-Improving LLMs from Raw Corpora; [6.75|53↑] daVinci-Agency: Unlocking Long-Horizon Agency Data-Efficiently
most upvoted: [630↑] GrandCode: Achieving Grandmaster Level in Competitive Programming via Agentic Reinforcement Learning; [311↑] InCoder-32B: Code Foundation Model for Industrial Scenarios

### cluster-30 (n=10)
week momentum: W19:0 W20:2 W21:2 W22:0 | avg_score=6.1 (novelty 5.4, impact 6.2) | HF likes median=55 max=110
tags: image generation, diffusion models, text-to-image generation, variational autoencoder, representation learning, autoregressive models
top papers (by score): [7.5|55↑] Scaling Text-to-Image Diffusion Transformers with Representation Autoencoders; [7.25|55↑] BitDance: Scaling Autoregressive Generative Models with Binary Tokens; [7.0|32↑] Representation Fréchet Loss for Visual Generation
most upvoted: [110↑] Qwen-Image-2.0 Technical Report; [106↑] Lens: Rethinking Training Efficiency for Foundational Text-to-Image Models

### cluster-19 (n=10)
week momentum: W19:0 W20:0 W21:0 W22:0 | avg_score=6.05 (novelty 5.7, impact 6) | HF likes median=99 max=217
tags: LLM agents, large language models, reinforcement learning, tool use, multi-agent systems, survey
top papers (by score): [7.25|57↑] From Static Templates to Dynamic Runtime Graphs: A Survey of Workflow Optimization for LLM Agents; [6.75|61↑] OdysseyArena: Benchmarking Large Language Models For Long-Horizon, Active and Inductive Interactions; [6.5|85↑] Agent-World: Scaling Real-World Environment Synthesis for Evolving General Agent Intelligence
most upvoted: [217↑] Heterogeneous Scientific Foundation Model Collaboration; [204↑] Agentic Reasoning for Large Language Models

### cluster-20 (n=10)
week momentum: W19:0 W20:0 W21:0 W22:0 | avg_score=5.8 (novelty 5.7, impact 5.8) | HF likes median=56 max=99
tags: diffusion models, video generation, video diffusion models, video editing, humanoid robotics, motion estimation
top papers (by score): [7.0|54↑] CaricatureGS: Exaggerating 3D Gaussian Splatting Faces With Gaussian Curvature; [6.5|55↑] VOID: Video Object and Interaction Deletion; [6.25|58↑] 3DreamBooth: High-Fidelity 3D Subject-Driven Video Generation Model
most upvoted: [99↑] InsertAnywhere: Bridging 4D Scene Geometry and Diffusion Models for Realistic Video Object Insertion; [87↑] CoInteract: Physically-Consistent Human-Object Interaction Video Synthesis via Spatially-Structured Co-Generation

### cluster-21 (n=9)
week momentum: W19:0 W20:0 W21:0 W22:1 | avg_score=6.58 (novelty 6.3, impact 6.2) | HF likes median=48 max=145
tags: diffusion models, novel view synthesis, sparse-view 3D reconstruction, geometry-aware generation, feed-forward reconstruction, triangle splatting
top papers (by score): [7.5|50↑] TriSplat: Simulation-Ready Feed-Forward 3D Scene Reconstruction; [7.5|48↑] Repurposing Geometric Foundation Models for Multi-view Diffusion; [7.25|55↑] Strips as Tokens: Artist Mesh Generation with Native UV Segmentation
most upvoted: [145↑] Geometry-Guided Reinforcement Learning for Multi-view Consistent 3D Scene Editing; [104↑] InfiniDepth: Arbitrary-Resolution and Fine-Grained Depth Estimation with Neural Implicit Fields

### cluster-17 (n=9)
week momentum: W19:0 W20:1 W21:0 W22:0 | avg_score=6.36 (novelty 5.6, impact 6.6) | HF likes median=99 max=199
tags: mixture-of-experts, reinforcement learning, large language models, test-time scaling, mathematical reasoning, agentic reasoning
top papers (by score): [7.0|37↑] Nemotron 3 Super: Open, Efficient Mixture-of-Experts Hybrid Mamba-Transformer Model for Agentic Reasoning; [6.75|159↑] Achieving Gold-Medal-Level Olympiad Reasoning via Simple and Unified Scaling; [6.75|99↑] Coupling Experts and Routers in Mixture-of-Experts via an Auxiliary Loss
most upvoted: [199↑] Step 3.5 Flash: Open Frontier-Level Intelligence with 11B Active Parameters; [181↑] LongCat-Flash-Thinking-2601 Technical Report

### cluster-32 (n=9)
week momentum: W19:0 W20:0 W21:0 W22:0 | avg_score=6.36 (novelty 6, impact 6.2) | HF likes median=72 max=121
tags: text-to-image generation, chain-of-thought, unified multimodal models, multimodal reasoning, code generation, image editing
top papers (by score): [7.25|46↑] Unify-Agent: A Unified Multimodal Agent for World-Grounded Image Synthesis; [7.0|111↑] Everything in Its Place: Benchmarking Spatial Intelligence of Text-to-Image Models; [6.75|80↑] UniReason 1.0: A Unified Reasoning Framework for World Knowledge Aligned Image Generation and Editing
most upvoted: [121↑] T2S-Bench & Structure-of-Thought: Benchmarking and Prompting Comprehensive Text-to-Structure Reasoning; [111↑] Everything in Its Place: Benchmarking Spatial Intelligence of Text-to-Image Models

### cluster-1 (n=8)
week momentum: W19:1 W20:0 W21:0 W22:0 | avg_score=5.22 (novelty 4.9, impact 5.2) | HF likes median=106 max=227
tags: world models, video generation, survey, unified framework, multimodal generation, Model Context Protocol
top papers (by score): [6.5|77↑] Lingshu-Cell: A generative cellular world model for transcriptome modeling toward virtual cells; [6.0|227↑] Agentic World Modeling: Foundations, Capabilities, Laws, and Beyond; [5.25|57↑] MCP-Cosmos: World Model-Augmented Agents for Complex Task Execution in MCP Environments
most upvoted: [227↑] Agentic World Modeling: Foundations, Capabilities, Laws, and Beyond; [203↑] OpenWorldLib: A Unified Codebase and Definition of Advanced World Models

### cluster-14 (n=8)
week momentum: W19:0 W20:0 W21:0 W22:0 | avg_score=6.06 (novelty 5.8, impact 5.8) | HF likes median=46 max=263
tags: LLM agents, benchmark, agent evaluation, reinforcement learning, evaluation, multimodal agents
top papers (by score): [7.0|263↑] ClawBench: Can AI Agents Complete Everyday Online Tasks?; [7.0|121↑] Claw-Eval: Toward Trustworthy Evaluation of Autonomous Agents; [6.75|33↑] ClawMark: A Living-World Benchmark for Multi-Turn, Multi-Day, Multimodal Coworker Agents
most upvoted: [263↑] ClawBench: Can AI Agents Complete Everyday Online Tasks?; [155↑] OpenClaw-RL: Train Any Agent Simply by Talking

## 附：长尾候选（147 篇）
- [6.25|365↑|W13] DataFlex: A Unified Framework for Data-Centric Dynamic Training of Large Language Models (data-centric training, data selection, data mixture)
- [6.5|355↑|W06] OPUS: Towards Efficient and Principled Data Selection in Large Language Model Pre-training in Every Iteration (dynamic data selection, LLM pre-training, optimizer-aware selection)
- [7.0|326↑|W15] Rethinking Generalization in Reasoning SFT: A Conditional Analysis on Optimization, Data, and Model Capability (SFT, generalization, chain-of-thought)
- [5.5|290↑|W07] Weak-Driven Learning: How Weak Agents make Strong Agents Stronger (weak-driven learning, post-training, large language models)
- [6.25|273↑|W18] Recursive Multi-Agent Systems (multi-agent systems, latent space, recursive computation)
- [2.25|272↑|W06] Kimi K2.5: Visual Agentic Intelligence (multimodal, agent, reinforcement learning)
- [6.5|269↑|W20] CiteVQA: Benchmarking Evidence Attribution for Trustworthy Document Intelligence (document VQA, evidence attribution, multimodal LLMs)
- [6.0|250↑|W17] Tstars-Tryon 1.0: Robust and Realistic Virtual Try-On for Diverse Fashion Items (virtual try-on, diffusion models, image editing)
- [7.25|245↑|W07] Less is Enough: Synthesizing Diverse Data in Feature Space of LLMs (data-centric AI, sparse autoencoders, diversity measurement)
- [5.75|219↑|W20] MinT: Managed Infrastructure for Training and Serving Millions of LLMs (LoRA, reinforcement learning, post-training)
- [6.25|211↑|W10] Bootstrapping Exploration with Group-Level Natural Language Feedback in Reinforcement Learning (natural language feedback, reinforcement learning, exploration)
- [5.75|210↑|W21] Code as Agent Harness (survey, agent harness, code generation)
- [6.5|197↑|W10] Heterogeneous Agent Collaborative Reinforcement Learning (collaborative reinforcement learning, heterogeneous agents, RLVR)
- [5.0|190↑|W06] QuantaAlpha: An Evolutionary Framework for LLM-Driven Alpha Mining (quantitative finance, alpha mining, genetic programming)
- [7.0|155↑|W11] Qianfan-OCR: A Unified End-to-End Model for Document Intelligence (end-to-end OCR, document intelligence, layout analysis)
- [7.25|155↑|W01] Youtu-LLM: Unlocking the Native Agentic Potential for Lightweight Large Language Models (lightweight language models, agentic AI, pre-training curriculum)
- [6.25|153↑|W09] dLLM: Simple Diffusion Language Modeling (diffusion language models, open-source framework, training pipeline)
- [7.0|151↑|W14] The Latent Space: Foundation, Evolution, Mechanism, Ability, and Outlook (Latent Space, Language Models, Survey)
- [5.0|150↑|W08] GLM-5: from Vibe Coding to Agentic Engineering (large language model, mixture of experts, sparse attention)
- [5.75|144↑|W13] TAPS: Task Aware Proposal Distributions for Speculative Sampling (speculative decoding, task-aware drafting, inference-time routing)
- [6.5|136↑|W13] MinerU-Diffusion: Rethinking Document OCR as Inverse Rendering via Diffusion Decoding (document OCR, diffusion models, inverse rendering)
- [6.5|123↑|W15] MinerU2.5-Pro: Pushing the Limits of Data-Centric Document Parsing at Scale (document parsing, data-centric AI, vision-language model)
- [5.5|120↑|W10] Penguin-VL: Exploring the Efficiency Limits of VLM with LLM-based Vision Encoders (vision-language models, vision encoder initialization, efficient VLM)
- [6.75|118↑|W18] World-R1: Reinforcing 3D Constraints for Text-to-Video Generation (text-to-video generation, 3d consistency, reinforcement learning)
- [5.75|117↑|W13] PixelSmile: Toward Fine-Grained Facial Expression Editing (facial expression editing, diffusion models, contrastive learning)
- [6.5|115↑|W15] When Numbers Speak: Aligning Textual Numerals and Visual Instances in Text-to-Video Diffusion Models (text-to-video generation, diffusion models, counting accuracy)
- [6.25|115↑|W03] Controlled Self-Evolution for Algorithmic Code Optimization (code generation, self-evolution, genetic algorithms)
- [6.5|115↑|W02] Entropy-Adaptive Fine-Tuning: Resolving Confident Conflicts to Mitigate Forgetting (catastrophic forgetting, supervised fine-tuning, entropy)
- [6.5|109↑|W21] Rethinking Cross-Layer Information Routing in Diffusion Transformers (diffusion transformers, image generation, residual connections)
- [5.25|108↑|W18] GLM-5V-Turbo: Toward a Native Foundation Model for Multimodal Agents (multimodal agents, vision-language model, reinforcement learning)
- [7.25|102↑|W16] RationalRewards: Reasoning Rewards Scale Visual Generation Both Training and Test Time (visual generation, reward models, reasoning)
- [6.75|101↑|W15] MegaStyle: Constructing Diverse and Scalable Style Dataset via Consistent Text-to-Image Style Mapping (style transfer, dataset curation, text-to-image generation)
- [6.75|98↑|W20] Active Learners as Efficient PRP Rerankers (LLM reranking, pairwise ranking prompting, active learning)
- [6.5|97↑|W06] CodeOCR: On the Effectiveness of Vision Language Models in Code Understanding (code understanding, vision language models, multimodal LLMs)
- [6.5|96↑|W03] MAXS: Meta-Adaptive Exploration with LLM Agents (LLM agents, test-time scaling, lookahead)
- [6.25|95↑|W11] Thinking in Uncertainty: Mitigating Hallucinations in MLRMs with Latent Entropy-Aware Decoding (multimodal reasoning, hallucination mitigation, entropy-aware decoding)
- [5.25|92↑|W03] Collaborative Multi-Agent Test-Time Reinforcement Learning for Reasoning (multi-agent systems, test-time learning, reinforcement learning)
- [6.0|90↑|W18] Visual Generation in the New Era: An Evolution from Atomic Mapping to Agentic World Modeling (visual generation, image editing, taxonomy)
- [6.5|89↑|W10] MOOSE-Star: Unlocking Tractable Training for Scientific Discovery by Breaking the Complexity Barrier (scientific discovery, large language models, training methodologies)
- [6.75|86↑|W20] Training Long-Context Vision-Language Models Effectively with Generalization Beyond 128K Context (vision-language models, long-context training, document understanding)
- [6.25|86↑|W19] MACE-Dance: Motion-Appearance Cascaded Experts for Music-Driven Dance Video Generation (music-driven dance generation, video generation, motion synthesis)
- [7.0|84↑|W18] UniVidX: A Unified Multimodal Framework for Versatile Video Generation via Diffusion Priors (video diffusion models, multimodal video generation, intrinsic decomposition)
- [5.75|82↑|W11] Flash-KMeans: Fast and Memory-Efficient Exact K-Means (k-means, GPU optimization, memory-aware computing)
- [7.0|82↑|W06] DFlash: Block Diffusion for Flash Speculative Decoding (speculative decoding, diffusion language models, block diffusion)
- [5.75|80↑|W19] Soohak: A Mathematician-Curated Benchmark for Evaluating Research-level Math Capabilities of LLMs (mathematical reasoning, benchmark, LLM evaluation)
- [6.0|80↑|W19] Continuous Latent Diffusion Language Model (continuous latent diffusion, language models, hierarchical generative models)
- [7.0|80↑|W15] LPM 1.0: Video-based Character Performance Model (video generation, diffusion transformer, conversational AI)
- [6.25|80↑|W06] Training Data Efficiency in Multimodal Process Reward Models (Multimodal Process Reward Models, Data Efficiency, Process Reward Modeling)
- [6.5|77↑|W21] EvalVerse: Pipeline-Aware and Expert-Calibrated Benchmarking for Professional Cinematic Video Generation (video generation, benchmark, cinematic quality)
- [5.5|77↑|W18] MiniCPM-o 4.5: Towards Real-Time Full-Duplex Omni-Modal Interaction (multimodal LLM, full-duplex interaction, speech generation)
- [6.0|76↑|W20] RubricEM: Meta-RL with Rubric-guided Policy Decomposition beyond Verifiable Rewards (Deep Research Agents, Reinforcement Learning from AI Feedback, GRPO)
- [5.5|75↑|W07] Experiential Reinforcement Learning (reinforcement learning, language models, self-reflection)
- [6.5|74↑|W18] Large Language Models Explore by Latent Distilling (LLM decoding, semantic diversity, online learning)
- [7.25|74↑|W04] The Flexibility Trap: Why Arbitrary Order Limits Reasoning Potential in Diffusion Language Models (diffusion language models, reasoning, reinforcement learning)
- [6.0|73↑|W16] Elucidating the SNR-t Bias of Diffusion Probabilistic Models (diffusion models, SNR bias, training-free correction)
- [6.5|73↑|W07] LLaDA2.1: Speeding Up Text Diffusion via Token Editing (discrete diffusion, language models, token editing)
- [6.75|72↑|W16] OmniShow: Unifying Multimodal Conditions for Human-Object Interaction Video Generation (video generation, multimodal conditioning, human-object interaction)
- [6.75|72↑|W03] Motion Attribution for Video Generation (video generation, data attribution, motion analysis)
- [5.5|70↑|W05] DeepSeek-OCR 2: Visual Causal Flow (visual causal flow, vision encoder, optical character recognition)
- [6.25|69↑|W14] All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models (Vision-Language Models, Reinforcement Learning, Group Relative Policy Optimization)
- [5.75|68↑|W13] Calibri: Enhancing Diffusion Transformers via Parameter-Efficient Calibration (diffusion transformers, parameter-efficient tuning, evolutionary algorithm)
- [6.75|68↑|W12] SAMA: Factorized Semantic Anchoring and Motion Alignment for Instruction-Guided Video Editing (video editing, instruction-guided editing, diffusion models)
- [4.75|67↑|W02] Solar Open Technical Report (Large Language Model, Mixture-of-Experts, Korean NLP)
- [6.0|66↑|W13] VGGRPO: Towards World-Consistent Video Generation with 4D Latent Reward (video generation, diffusion models, reinforcement learning from rewards)
- [5.0|66↑|W01] LiveTalk: Real-Time Multimodal Interactive Video Diffusion via Improved On-Policy Distillation (real-time video generation, diffusion distillation, on-policy distillation)
- [6.5|64↑|W20] FashionChameleon: Towards Real-Time and Interactive Human-Garment Video Customization (human-centric video generation, garment customization, interactive video)
- [6.0|63↑|W17] Video Analysis and Generation via a Semantic Progress Function (video generation, semantic analysis, temporal control)
- [6.25|63↑|W13] SpecEyes: Accelerating Agentic Multimodal LLMs via Speculative Perception and Planning (speculative reasoning, agentic multimodal LLMs, efficient inference)
- [7.25|63↑|W10] LoGeR: Long-Context Geometric Reconstruction with Hybrid Memory (3D reconstruction, long-context, feedforward)
- [6.75|63↑|W10] RubricBench: Aligning Model-Generated Rubrics with Human Standards (reward models, rubric-guided evaluation, LLM-as-a-judge)
- [6.25|62↑|W03] RubricHub: A Comprehensive and Highly Discriminative Rubric Dataset via Automated Coarse-to-Fine Generation (rubric generation, reinforcement learning with rubrics, open-ended generation)
- [5.0|62↑|W03] Ministral 3 (model distillation, pruning, small language models)
- [5.75|61↑|W05] ASTRA: Automated Synthesis of agentic Trajectories and Reinforcement Arenas (tool-augmented agents, reinforcement learning, supervised fine-tuning)
- [6.5|60↑|W20] Darwin Family: MRI-Trust-Weighted Evolutionary Merging for Training-Free Scaling of Language-Model Reasoning (model merging, evolutionary algorithms, large language models)
- [5.25|60↑|W12] Online Experiential Learning for Language Models (online learning, experiential learning, language models)
- [6.5|60↑|W08] Unified Latents (UL): How to train your latents (diffusion models, latent representations, variational autoencoders)
- [5.5|59↑|W21] ACC: Compiling Agent Trajectories for Long-Context Training (agent trajectories, long-context training, supervision blind spot)
- [5.75|59↑|W06] On the Entropy Dynamics in Reinforcement Fine-Tuning of Large Language Models (entropy dynamics, reinforcement fine-tuning, GRPO)
- [6.25|59↑|W02] Qwen3-VL-Embedding and Qwen3-VL-Reranker: A Unified Framework for State-of-the-Art Multimodal Retrieval and Ranking (multimodal retrieval, embedding model, reranker)
- [7.25|58↑|W12] TRUST-SQL: Tool-Integrated Multi-Turn Reinforcement Learning for Text-to-SQL over Unknown Schemas (text-to-sql, reinforcement learning, multi-turn agents)
- [6.0|57↑|W01] Avatar Forcing: Real-Time Interactive Head Avatar Generation for Natural Conversation (interactive avatar, diffusion forcing, real‑time generation)
- [7.0|56↑|W14] Steerable Visual Representations (Vision Transformer, Vision-Language Fusion, Steerable Representations)
- [5.5|56↑|W09] CHIMERA: Compact Synthetic Data for Generalizable LLM Reasoning (synthetic data, reasoning, chain-of-thought)
- [6.5|56↑|W08] MolHIT: Advancing Molecular-Graph Generation with Hierarchical Discrete Diffusion Models (molecular generation, graph diffusion models, discrete diffusion)
- [6.0|56↑|W04] The Script is All You Need: An Agentic Framework for Long-Horizon Dialogue-to-Cinematic Video Generation (video generation, cinematic script generation, multi-agent systems)
- [6.75|55↑|W14] CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery (autonomous agents, multi-agent systems, evolutionary search)
- [6.75|55↑|W07] PhyCritic: Multimodal Critic Models for Physical AI (multimodal critics, physical AI, reinforcement fine-tuning)
- [7.25|55↑|W07] GENIUS: Generative Fluid Intelligence Evaluation Suite (generative fluid intelligence, multimodal benchmark, unified multimodal models)
- [5.75|54↑|W04] Stable-DiffCoder: Pushing the Frontier of Code Diffusion Large Language Model (code generation, diffusion language models, masked diffusion)
- [5.75|54↑|W02] ArenaRL: Scaling RL for Open-Ended Agents via Tournament-based Relative Ranking (reinforcement learning, LLM agents, open-ended tasks)
- [7.0|53↑|W15] DMax: Aggressive Parallel Decoding for dLLMs (diffusion language models, parallel decoding, on-policy training)
- [5.0|53↑|W10] DARE: Aligning LLM Agents with the R Statistical Ecosystem via Distribution-Aware Retrieval (retrieval-augmented generation, R language, statistical computing)
- [5.5|53↑|W03] User-Oriented Multi-Turn Dialogue Generation with Tool Use at scale (multi-turn dialogue, tool use, data generation)
- [6.25|53↑|W01] DreamID-V:Bridging the Image-to-Video Gap for High-Fidelity Face Swapping via Diffusion Transformer (Video Face Swapping, Diffusion Transformer, Identity Preservation)
- [6.5|52↑|W19] Geometry Conflict: Explaining and Controlling Forgetting in LLM Continual Post-Training (continual learning, model merging, geometry conflict)
- [6.25|52↑|W07] OneVision-Encoder: Codec-Aligned Sparsity as a Foundational Principle for Multimodal Intelligence (vision transformer, video understanding, codec-guided sparsity)
- [4.5|52↑|W05] OCRVerse: Towards Holistic OCR in End-to-End Vision-Language Models (OCR, Vision-Language Models, Reinforcement Learning)
- [5.5|52↑|W03] MMDeepResearch-Bench: A Benchmark for Multimodal Deep Research Agents (multimodal deep research, benchmark, evaluation)
- [5.25|51↑|W13] DA-Flow: Degradation-Aware Optical Flow Estimation with Diffusion Models (optical flow, degradation-aware, diffusion models)
- [6.75|50↑|W15] OpenVLThinkerV2: A Generalist Multimodal Reasoning Model for Multi-domain Visual Tasks (multimodal reasoning, reinforcement learning, group relative policy optimization)
- [6.0|50↑|W14] CutClaw: Agentic Hours-Long Video Editing via Music Synchronization (video editing, multimodal agents, audio-visual synchronization)
- [6.75|50↑|W10] MSA: Memory Sparse Attention for Efficient End-to-End Memory Model Scaling to 100M Tokens (sparse-attention, memory-augmented-LLMs, long-context)
- [5.0|50↑|W10] Omni-Diffusion: Unified Multimodal Understanding and Generation with Masked Discrete Diffusion (multimodal learning, discrete diffusion, any-to-any generation)
- [5.25|50↑|W10] OpenAutoNLU: Open Source AutoML Library for NLU (AutoML, natural language understanding, text classification)
- [6.25|49↑|W18] Beyond SFT-to-RL: Pre-alignment via Black-Box On-Policy Distillation for Multimodal RL (multimodal reasoning, reinforcement learning with verifiable rewards, on-policy distillation)
- [6.0|48↑|W04] OmniTransfer: All-in-one Framework for Spatio-temporal Video Transfer (video generation, diffusion models, video transfer)
- [5.75|48↑|W04] Locate, Steer, and Improve: A Practical Survey of Actionable Mechanistic Interpretability in Large Language Models (mechanistic interpretability, large language models, model steering)
- [5.5|48↑|W03] Beyond Static Tools: Test-Time Tool Evolution for Scientific Reasoning (test-time tool evolution, scientific reasoning, LLM agents)
- [7.25|47↑|W15] KnowU-Bench: Towards Interactive, Proactive, and Personalized Mobile Agent Evaluation (mobile agents, personalization, proactive assistance)
- [5.75|47↑|W15] MegaTrain: Full Precision Training of 100B+ Parameter Large Language Models on a Single GPU (large language models, memory-efficient training, GPU offloading)
- [7.25|47↑|W05] Reinforcement Learning via Self-Distillation (reinforcement learning, self-distillation, credit assignment)
- [6.5|46↑|W22] ResearchMath-14K: Scaling Research-Level Mathematics via Agents (research-level math dataset, open problems, language model reasoning)
- [8.25|46↑|W12] Alignment Makes Language Models Normative, Not Descriptive (LLM alignment, behavioral prediction, game theory)
- [6.75|45↑|W09] AgentVista: Evaluating Multimodal Agents in Ultra-Challenging Realistic Visual Scenarios (multimodal agents, benchmark, long-horizon reasoning)
- [6.75|45↑|W02] Atlas: Orchestrating Heterogeneous Models and Tools for Multi-Domain Complex Reasoning (tool-augmented LLMs, model routing, reinforcement learning)
- [5.75|44↑|W11] Multimodal OCR: Parse Anything from Documents (document parsing, optical character recognition, image-to-SVG)
- [7.25|44↑|W11] LLM2Vec-Gen: Generative Embeddings from Large Language Models (text embeddings, output-centric representations, self-supervised learning)
- [6.75|44↑|W09] Imagination Helps Visual Reasoning, But Not Yet in Latent Space (latent visual reasoning, multimodal LLMs, causal mediation analysis)
- [7.0|44↑|W05] Youtu-VL: Unleashing Visual Potential via Unified Vision-Language Supervision (vision-language models, unified multimodal pretraining, autoregressive supervision)
- [5.0|43↑|W15] Uni-ViGU: Towards Unified Video Generation and Understanding via A Diffusion-Based Video Generator (unified multimodal models, video generation, video understanding)
- [5.5|43↑|W11] In-Context Reinforcement Learning for Tool Use in Large Language Models (reinforcement learning, tool use, large language models)
- [6.0|42↑|W05] ConceptMoE: Adaptive Token-to-Concept Compression for Implicit Compute Allocation (token compression, mixture of experts, efficient transformers)
- [6.75|41↑|W18] DV-World: Benchmarking Data Visualization Agents in Real-World Scenarios (data visualization, benchmark, LLM agents)
- [6.75|41↑|W12] ProactiveBench: Benchmarking Proactiveness in Multimodal Large Language Models (multimodal, benchmark, proactiveness)
- [6.0|40↑|W19] MARBLE: Multi-Aspect Reward Balance for Diffusion RL (multi-reward RL, diffusion models, gradient harmonization)
- [7.5|40↑|W18] Efficient Training on Multiple Consumer GPUs with RoundPipe (LLM fine-tuning, pipeline parallelism, CPU offloading)
- [6.0|40↑|W10] Believe Your Model: Distribution-Guided Confidence Calibration (Test-Time Scaling, Confidence Calibration, Gaussian Mixture Models)
- [5.75|39↑|W13] mSFT: Addressing Dataset Mixtures Overfiting Heterogeneously in Multi-task SFT (multi-task learning, supervised fine-tuning, overfitting)
- [6.5|39↑|W03] Unlocking Implicit Experience: Synthesizing Tool-Use Trajectories from Text (tool-use data synthesis, multi-turn dialogue, large language models)
- [7.0|38↑|W16] CodeTracer: Towards Traceable Agent States (code agents, trajectory analysis, fault localization)
- [7.0|38↑|W04] GutenOCR: A Grounded Vision-Language Front-End for Documents (OCR, document understanding, vision-language models)
- [6.25|37↑|W10] Proact-VL: A Proactive VideoLLM for Real-Time AI Companions (video understanding, streaming AI, proactive interaction)
- [6.5|37↑|W09] Exploratory Memory-Augmented LLM Agent via Hybrid On- and Off-Policy Optimization (LLM agents, reinforcement learning, memory-augmented RL)
- [4.75|36↑|W52] SciEvalKit: An Open-source Evaluation Toolkit for Scientific General Intelligence (scientific AI evaluation, benchmark toolkit, LLMs)
- [6.5|34↑|W11] ShotVerse: Advancing Cinematic Camera Control for Text-Driven Multi-Shot Video Creation (text-driven video generation, camera control, multi-shot video)
- [6.25|33↑|W10] Beyond Length Scaling: Synergizing Breadth and Depth for Generative Reward Models (generative reward models, chain-of-thought, breadth reasoning)
- [6.5|32↑|W16] Reward Hacking in the Era of Large Models: Mechanisms, Emergent Misalignment, Challenges (reward hacking, proxy compression, RLHF)
- [5.75|30↑|W17] ShadowPEFT: Shadow Network for Parameter-Efficient Fine-Tuning (PEFT, LoRA, shadow network)
- [5.75|30↑|W08] Generated Reality: Human-centric World Simulation using Interactive Video Generation with Hand and Camera Control (video generation, diffusion models, world models)
- [7.0|30↑|W08] CADEvolve: Creating Realistic CAD via Program Evolution (CAD, program synthesis, evolutionary algorithms)
- [6.25|28↑|W09] AgentDropoutV2: Optimizing Information Flow in Multi-Agent Systems via Test-Time Rectify-or-Reject Pruning (multi-agent systems, test-time rectification, error propagation)
- [6.0|27↑|W19] StraTA: Incentivizing Agentic Reinforcement Learning with Strategic Trajectory Abstraction (agentic reinforcement learning, long-horizon decision making, strategy abstraction)
- [5.75|27↑|W08] jina-embeddings-v5-text: Task-Targeted Embedding Distillation (text embeddings, knowledge distillation, multilingual models)
- [5.5|26↑|W19] Continuous-Time Distribution Matching for Few-Step Diffusion Distillation (diffusion distillation, distribution matching, continuous-time training)
- [5.5|26↑|W09] ARLArena: A Unified Framework for Stable Agentic Reinforcement Learning (Agentic Reinforcement Learning, Policy Gradient, Training Stability)
- [6.75|25↑|W17] StyleID: A Perception-Aware Dataset and Metric for Stylization-Agnostic Facial Identity Recognition (facial identity, stylization, perception)
- [5.75|24↑|W08] Multi-agent cooperation through in-context co-player inference (multi-agent reinforcement learning, cooperation, in-context learning)