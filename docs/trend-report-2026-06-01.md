# AI 研究趋势报告 — HF Weekly W19-W22 (2026)

> 语料：120 篇全文分析论文 | 14 个主题簇（45 篇离群） | 聚类 HDBSCAN(min_cluster_size=3) | 模型 deepseek-v4-pro

# AI 研究趋势周报（W19-W22, 2026）

## 一、主题簇命名

- **视频生成与扩散蒸馏**（原 cluster-12，13 篇）  
  涵盖视频扩散模型、在线策略蒸馏、相机控制、交互式视频生成与世界模型评估。
- **多模态代理推理与强化学习**（原 cluster-8，10 篇）  
  基于 GRPO 的 LLM 代理、工具使用、多模态搜索代理的强化学习。
- **多代理系统与自主研究**（原 cluster-4，6 篇）  
  多智能体安全对齐、代理框架、自动化科研。
- **VLA 与具身智能**（原 cluster-11，6 篇）  
  视觉‑语言‑动作模型、机器人操纵、世界动作模型。
- **自进化代理技能学习**（原 cluster-5，6 篇）  
  代理技能的自我进化、上下文到技能的转换、经验复用。
- **多模态记忆与长上下文评估**（原 cluster-7，5 篇）  
  VLMs 的长期记忆基准、视觉中心记忆评测、在线记忆机制。
- **统一多模态建模**（原 cluster-9，5 篇）  
  无编码器的原生视觉‑语言模型、统一理解与生成、流匹配。
- **视听语言模型与语音对话**（原 cluster-1，5 篇）  
  音频‑语言大模型、语音识别与合成、实时对话、多 token 预测。
- **RL 驱动的数学推理**（原 cluster-10，4 篇）  
  GRPO、策略梯度、可验证奖励下的 Token 信用分配。
- **生成式 UI 与个人代理**（原 cluster-6，3 篇）  
  移动 GUI 仿真、规模化交互轨迹合成、个人代理的生成式界面。
- **研究级数学推理基准**（原 cluster-3，3 篇）  
  奥林匹克数学、研究级数学数据集、智能体流水线。
- **高效注意力与 KV 缓存量化**（原 cluster-2，3 篇）  
  稀疏/混合精度注意力、2‑bit KV 量化、Blackwell GPU 适配。
- **推理 RL 中的策略蒸馏**（原 cluster-13，3 篇）  
  在线策略自蒸馏、互信息、多模态 RL 预对齐。
- **自动驾驶世界模型**（原 cluster-0，3 篇）  
  统一驾驶世界模型、3D 场景理解、未来点云预测。

---

## 二、当前热点 Topic 排名

学术热度以“簇规模 × avg_score”衡量，反映该方向整体的研究体量与质量；社区热度以簇内最高点赞（HF likes max）表征开源社区的实际关注度。两者并列，不进行加权混合。

| 学术热度排名（Tier 1‑3） | 簇规模×分数 | 社区热度排名（Tier 1‑3） | 最高点赞 |
|--------------------------|--------------|----------------------------|----------|
| 1. 视频生成与扩散蒸馏 | 13×6.1 = 79.3 | 1. VLA 与具身智能 | 347↑ (MolmoAct2) |
| 2. 多模态代理推理与强化学习 | 10×6.42 = 64.2 | 2. 多代理系统与自主研究 | 210↑ (Code as Agent Harness) |
| 3. 自进化代理技能学习 | 6×6.67 = 40.0 | 3. 自进化代理技能学习 | 208↑ (SkillOpt) |
| 4. VLA 与具身智能 | 6×6.33 ≈ 38.0 | 4. RL 驱动的数学推理 | 204↑ (DelTA) |
| 5. 多代理系统与自主研究 | 6×6.17 ≈ 37.0 | 5. 统一多模态建模 | 191↑ (SenseNova‑U1) |
| 6. 多模态记忆与长上下文评估 | 5×6.55 ≈ 32.8 | 6. 研究级数学推理基准 | 159↑ (Gold‑Medal‑Level) |
| 7. 视听语言模型与语音对话 | 5×6.55 ≈ 32.8 | 7. 多模态记忆与长上下文评估 | 124↑ (δ‑mem) |
| 8. 统一多模态建模 | 5×6.4 = 32.0 | 8. 视频生成与扩散蒸馏 | 125↑ (Stream‑R1) |

**一致之处**：自进化代理技能学习在两个榜单均位列前 3，说明其新颖性和社区需求高度重合。  
**明显背离**：视频生成与扩散蒸馏学术热度第一，但社区最高仅 125 点赞，远低于具身智能、多代理等方向的 200‑350 点赞，表明该方向研究密集但开源社区尚未出现现象级应用。相反，VLA 与具身智能学术体量中等，却以 MolmoAct2 的 347 点赞遥遥领先，社区热度由实用性和机器人落地预期驱动。

---

## 三、预判的上升 / 新兴趋势

对周动量上升、高新颖性小簇、以及长尾列表中高潜力单点进行交叉分析，提炼五个未来可能爆发的方向。

1. **生成式 UI 与可验证个人代理**  
   Cluster‑6 动量从 W19 的 0 平稳攀升至 W22 的 1，平均 novelty=6.0，impact=7.0。长尾中同时出现高 novelty 的 π‑Bench（7.75, 102↑）和 Video2GUI（6.5, 145↑）。可验证的 GUI 仿真平台（MobileGym）和生成式界面模型（Macaron‑A2UI）正在为“主动式个人助理”构建基础设施。该方向有望接替当前 Tool‑augmented Agent 成为下一风口。

2. **因果视频世界模型与多智能体世界生成**  
   长尾论文 YoCausal（7.25, 41↑）从因果视角审视视频生成与世界模型的鸿沟；Gamma‑World（5.75, 405↑）以超高点赞揭示了社区对多智能体世界模型的狂热点击。WBench（7.5, 100↑，属 cluster‑12）则系统评估交互式视频世界模型。三者共同指向“视频生成 × 世界模型 × 多智能体交互”的交叉地带，具备高新颖性与话题性。

3. **主动式代理：推荐、感知与长期记忆**  
   长尾中的 ProRL（7.25, 81↑）和 π‑Bench 定义了主动推荐与长期工作流中的代理行为，感知人格的 Perception or Prejudice（7.5, 169↑）带来社会智能维度。多模态记忆评估 MemLens（7.75, 75↑，cluster‑7）为此类主动代理的记忆基础提供标准。主动性与社会感知正在成为 Agent 研究的新一层抽象。

4. **高效注意力与极限 KV 缓存压缩**  
   cluster‑2 虽然仅有 3 篇，但平均 novelty=7.0，所有簇中最高，代表论文 OSCAR（8.0, 63↑）提出了 2‑bit KV 量化方案。随着 128K 以上长上下文模型落地，推理效率成为瓶颈，该方向学术价值极高，待社区感知跟上后将快速膨胀。

5. **原生多模态模型：从编码器自由到统一架构**  
   cluster‑9 动量持续上升（W20→W22: 1→2），SenseNova‑U1（191↑）和 Towards Native One‑Vision Models（6.5, 68↑）等论文倡导去除独立编码器的原生多模态范式，可能在下半年引发骨干网络重构的热潮，并在长尾中出现技术报告（Qwen‑Image‑VAE‑2.0）作为基础设施信号。

---

## 四、学术 vs 社区错位案例

### 高点赞、低学术分（产品或话题驱动）
- **Gamma‑World（5.75, 405↑）**：“生成式多智能体世界建模”，但 novelty 仅 5.75。娱乐化的多智能体游戏概念引发极高传播，学术贡献有限。  
- **MinT（5.75, 219↑）**：百万级 LLM 的训练/服务基础设施，实用性极强但学术新颖度不足，点赞来自工程师群体。  
- **Qwen‑Image‑2.0 Technical Report（5.5, 110↑）**：品牌效应与扩散 transformer 的工程报告，社区期待多过学术突破。  
- **Foundation Protocol（4.5, 77↑）**：代理社会的协调协议，蓝图式论文，概念引人遐想，但缺乏实质方法与实验验证。

### 高学术分、低点赞（被低估的技术硬货）
- **OSCAR（8.0, 63↑）**：2‑bit KV 缓存量化的离线谱协方差旋转方法，所有论文中 novelty 最高，点赞仅 63。其强数学推导使得传播门槛升高，但一旦纳入推理框架（如 vLLM），影响将指数级放大。  
- **YoCausal（7.25, 41↑）**：从因果推断的角度检验视频生成作为世界模型的有效性，视角独到。硬核方法论使得点击量严重低于其 insight 价值，是学术界可能忽视的宝藏。  
- **SpatialBench（7.5, 68↑）**：首个全方位 3D 空间基础模型测评，填补行业空白，但 3D 重建社区体量小于 LLM，传播不足。  
- **π‑Bench（7.75, 102↑）**：定义长周期主动个人助理的评估基准，其点赞数尚可但远未匹配 7.75 的创新分。作为新任务设定的开山之作，应被更多 multi‑agent 和 GUI agent 研究者关注。  
- **ProRL（7.25, 81↑）**：主动推荐中的强化学习策略梯度估计，跨学科（RL + 推荐）导致受众分裂，实际价值高于现有关注度。

---

**结论速览**：当前，**具身 VLA 与自进化代理技能**在学术与社区双热，前者更强于落地期待，后者则实现了研究质量与点赞的“双赢”。**视频生成**虽然学术体量庞大，但缺乏社区爆款，未来可能通过“世界模型”与“交互式生成”分支出新热点。投资新兴方向应重点关注：**生成式个人助理 GUI**、**因果视频世界模型**、**原生多模态架构**，以及在长尾中孤独闪耀的 **极限 KV 压缩技术**。长尾中的 π‑Bench、YoCausal、OSCAR 等论文，代表着下一次聚类的种子。

---
## 附：聚类信号原始数据

### cluster-12 (n=13)
week momentum: W19:5 W20:4 W21:2 W22:2 | avg_score=6.1 (novelty 5.5, impact 6) | HF likes median=92 max=125
tags: video generation, diffusion distillation, on-policy distillation, camera control, interactive video generation, world models
top papers (by score): [7.5|100↑] WBench: A Comprehensive Multi-turn Benchmark for Interactive Video World Model Evaluation; [6.75|27↑] D-OPSD: On-Policy Self-Distillation for Continuously Tuning Step-Distilled Diffusion Models; [6.5|101↑] AnyFlow: Any-Step Video Diffusion Model with On-Policy Flow Map Distillation
most upvoted: [125↑] Stream-R1: Reliability-Perplexity Aware Reward Distillation for Streaming Video Generation; [111↑] LongLive-2.0: An NVFP4 Parallel Infrastructure for Long Video Generation

### cluster-8 (n=10)
week momentum: W19:5 W20:0 W21:1 W22:2 | avg_score=6.42 (novelty 6.3, impact 6.2) | HF likes median=60 max=117
tags: reinforcement learning, GRPO, LLM Agents, agentic reasoning, tool use, vision-language models
top papers (by score): [7.75|101↑] OpenSearch-VL: An Open Recipe for Frontier Multimodal Search Agents; [7.0|62↑] HyperEyes: Dual-Grained Efficiency-Aware Reinforcement Learning for Parallel Multimodal Search Agents; [6.75|79↑] Agent Explorative Policy Optimization for Multimodal Agentic Reasoning
most upvoted: [117↑] Beyond Semantic Similarity: Rethinking Retrieval for Agentic Search via Direct Corpus Interaction; [101↑] OpenSearch-VL: An Open Recipe for Frontier Multimodal Search Agents

### cluster-4 (n=6)
week momentum: W19:1 W20:1 W21:3 W22:1 | avg_score=6.17 (novelty 5.8, impact 6) | HF likes median=125 max=210
tags: LLM agents, multi-agent systems, autonomous research, survey, agent harness, code generation
top papers (by score): [7.0|127↑] AgentDoG 1.5: A Lightweight and Scalable Alignment Framework for AI Agent Safety and Security; [7.0|54↑] Auditing Agent Harness Safety; [6.5|67↑] AI for Auto-Research: Roadmap & User Guide
most upvoted: [210↑] Code as Agent Harness; [185↑] AutoResearchClaw: Self-Reinforcing Autonomous Research with Human-AI Collaboration

### cluster-11 (n=6)
week momentum: W19:3 W20:2 W21:0 W22:1 | avg_score=6.33 (novelty 6.2, impact 6.2) | HF likes median=114 max=347
tags: vision-language-action, robot manipulation, World Action Models, Vision-Language-Action, foundation model, visual navigation
top papers (by score): [7.5|103↑] Qwen-VLA: Unifying Vision-Language-Action Modeling across Tasks, Environments, and Robot Embodiments; [7.0|347↑] MolmoAct2: Action Reasoning Models for Real-world Deployment; [6.75|67↑] World Action Models: The Next Frontier in Embodied AI
most upvoted: [347↑] MolmoAct2: Action Reasoning Models for Real-world Deployment; [143↑] PhysBrain 1.0 Technical Report

### cluster-5 (n=6)
week momentum: W19:2 W20:1 W21:2 W22:0 | avg_score=6.67 (novelty 6.5, impact 6.2) | HF likes median=122 max=208
tags: LLM agents, agent skills, prompt engineering, skill evolution, experience reuse, reinforcement learning
top papers (by score): [7.5|208↑] SkillOpt: Executive Strategy for Self-Evolving Agent Skills; [7.25|46↑] SkillOS: Learning Skill Curation for Self-Evolving Agents; [6.5|166↑] From Context to Skills: Can Language Models Learn from Context Skillfully?
most upvoted: [208↑] SkillOpt: Executive Strategy for Self-Evolving Agent Skills; [166↑] From Context to Skills: Can Language Models Learn from Context Skillfully?

### cluster-7 (n=5)
week momentum: W19:0 W20:4 W21:1 W22:0 | avg_score=6.55 (novelty 6.2, impact 6) | HF likes median=75 max=124
tags: multimodal memory, benchmark, vision-language agents, long-term memory, visual reasoning, agent memory systems
top papers (by score): [7.75|75↑] MemLens: Benchmarking Multimodal Long-Term Memory in Large Vision-Language Models; [7.0|62↑] MemEye: A Visual-Centric Evaluation Framework for Multimodal Agent Memory; [6.75|86↑] Training Long-Context Vision-Language Models Effectively with Generalization Beyond 128K Context
most upvoted: [124↑] δ-mem: Efficient Online Memory for Large Language Models; [86↑] Training Long-Context Vision-Language Models Effectively with Generalization Beyond 128K Context

### cluster-9 (n=5)
week momentum: W19:0 W20:1 W21:1 W22:2 | avg_score=6.4 (novelty 5.6, impact 6.4) | HF likes median=76 max=191
tags: encoder-free VLM, unified multimodal model, image editing, flow matching, native vision-language model, multi-image understanding
top papers (by score): [7.0|84↑] UniVidX: A Unified Multimodal Framework for Versatile Video Generation via Diffusion Priors; [6.5|68↑] From Pixels to Words -- Towards Native One-Vision Models at Scale; [6.25|42↑] Toward Native Multimodal Modeling: A Roadmap
most upvoted: [191↑] SenseNova-U1: Unifying Multimodal Understanding and Generation with NEO-unify Architecture; [84↑] UniVidX: A Unified Multimodal Framework for Versatile Video Generation via Diffusion Priors

### cluster-1 (n=5)
week momentum: W19:1 W20:1 W21:3 W22:0 | avg_score=6.55 (novelty 6, impact 6.4) | HF likes median=56 max=149
tags: audio-language model, automatic speech recognition, text-to-speech, realtime spoken dialogue, reinforcement learning from human feedback, multi-token prediction
top papers (by score): [7.25|149↑] When Vision Speaks for Sound; [7.0|35↑] Audio-Visual Intelligence in Large Foundation Models; [6.75|56↑] A Survey of Large Audio Language Models: Generalization, Trustworthiness, and Outlook
most upvoted: [149↑] When Vision Speaks for Sound; [131↑] Mega-ASR: Towards In-the-wild^2 Speech Recognition via Scaling up Real-world Acoustic Simulation

### cluster-10 (n=4)
week momentum: W19:2 W20:0 W21:1 W22:1 | avg_score=6.38 (novelty 6, impact 5.8) | HF likes median=56 max=204
tags: reinforcement learning, math reasoning, GRPO, policy gradient, reasoning, self-correction
top papers (by score): [7.0|204↑] DelTA: Discriminative Token Credit Assignment for Reinforcement Learning from Verifiable Rewards; [6.5|44↑] DenoiseRL: Bootstrapping Reasoning Models to Recover from Noisy Prefixes; [6.5|37↑] Nonsense Helps: Prompt Space Perturbation Broadens Reasoning Exploration
most upvoted: [204↑] DelTA: Discriminative Token Credit Assignment for Reinforcement Learning from Verifiable Rewards; [69↑] Listwise Policy Optimization: Group-based RLVR as Target-Projection on the LLM Response Simplex

### cluster-6 (n=3)
week momentum: W19:0 W20:1 W21:1 W22:1 | avg_score=6.58 (novelty 6, impact 7) | HF likes median=79 max=145
tags: benchmark, generative ui, personal agents, dialogue systems, reinforcement learning, structured output
top papers (by score): [7.25|58↑] MobileGym: A Verifiable and Highly Parallel Simulation Platform for Mobile GUI Agent Research; [6.5|145↑] Video2GUI: Synthesizing Large-Scale Interaction Trajectories for Generalized GUI Agent Pretraining; [6.0|79↑] Macaron-A2UI: A Model for Generative UI in Personal Agents
most upvoted: [145↑] Video2GUI: Synthesizing Large-Scale Interaction Trajectories for Generalized GUI Agent Pretraining; [79↑] Macaron-A2UI: A Model for Generative UI in Personal Agents

### cluster-3 (n=3)
week momentum: W19:1 W20:1 W21:0 W22:1 | avg_score=6.33 (novelty 6, impact 6) | HF likes median=80 max=159
tags: mathematical reasoning, research-level math dataset, open problems, language model reasoning, agentic pipeline, fake references
top papers (by score): [6.75|159↑] Achieving Gold-Medal-Level Olympiad Reasoning via Simple and Unified Scaling; [6.5|46↑] ResearchMath-14K: Scaling Research-Level Mathematics via Agents; [5.75|80↑] Soohak: A Mathematician-Curated Benchmark for Evaluating Research-level Math Capabilities of LLMs
most upvoted: [159↑] Achieving Gold-Medal-Level Olympiad Reasoning via Simple and Unified Scaling; [80↑] Soohak: A Mathematician-Curated Benchmark for Evaluating Research-level Math Capabilities of LLMs

### cluster-2 (n=3)
week momentum: W19:0 W20:1 W21:2 W22:0 | avg_score=6.75 (novelty 7, impact 6.3) | HF likes median=63 max=93
tags: sparse attention, efficient attention, mixed precision, long-context, FP4 quantization, Blackwell GPU
top papers (by score): [8.0|63↑] OSCAR: Offline Spectral Covariance-Aware Rotation for 2-bit KV Cache Quantization; [6.5|41↑] ThriftAttention: Selective Mixed Precision for Long-Context FP4 Attention; [5.75|93↑] Full Attention Strikes Back: Transferring Full Attention into Sparse within Hundred Training Steps
most upvoted: [93↑] Full Attention Strikes Back: Transferring Full Attention into Sparse within Hundred Training Steps; [63↑] OSCAR: Offline Spectral Covariance-Aware Rotation for 2-bit KV Cache Quantization

### cluster-13 (n=3)
week momentum: W19:0 W20:2 W21:0 W22:0 | avg_score=6.58 (novelty 6.7, impact 6.3) | HF likes median=111 max=195
tags: on-policy self-distillation, reinforcement learning, GRPO, reasoning, pointwise mutual information, Jensen-Shannon divergence
top papers (by score): [7.0|195↑] Anti-Self-Distillation for Reasoning RL via Pointwise Mutual Information; [6.5|111↑] Self-Distilled Agentic Reinforcement Learning; [6.25|49↑] Beyond SFT-to-RL: Pre-alignment via Black-Box On-Policy Distillation for Multimodal RL
most upvoted: [195↑] Anti-Self-Distillation for Reasoning RL via Pointwise Mutual Information; [111↑] Self-Distilled Agentic Reinforcement Learning

### cluster-0 (n=3)
week momentum: W19:1 W20:0 W21:0 W22:0 | avg_score=6.75 (novelty 6.7, impact 6.7) | HF likes median=37 max=72
tags: diffusion models, driving world model, 3D scene understanding, future point cloud prediction, bird's-eye view (BEV), large language model (LLM)
top papers (by score): [7.25|72↑] HERMES++: Toward a Unified Driving World Model for 3D Scene Understanding and Generation; [6.75|37↑] PhysForge: Generating Physics-Grounded 3D Assets for Interactive Virtual World; [6.25|25↑] Map2World: Segment Map Conditioned Text to 3D World Generation
most upvoted: [72↑] HERMES++: Toward a Unified Driving World Model for 3D Scene Understanding and Generation; [37↑] PhysForge: Generating Physics-Grounded 3D Assets for Interactive Virtual World

## 附：长尾候选（45 篇）
- [5.75|405↑|W22] Gamma-World: Generative Multi-Agent World Modeling Beyond Two Players (multi-agent world model, video generation, diffusion transformers)
- [6.5|269↑|W20] CiteVQA: Benchmarking Evidence Attribution for Trustworthy Document Intelligence (document VQA, evidence attribution, multimodal LLMs)
- [6.5|231↑|W19] Mean Mode Screaming: Mean--Variance Split Residuals for 1000-Layer Diffusion Transformers (diffusion transformers, deep learning stability, residual networks)
- [5.75|219↑|W20] MinT: Managed Infrastructure for Training and Serving Millions of LLMs (LoRA, reinforcement learning, post-training)
- [6.5|174↑|W21] TransitLM: A Large-Scale Dataset and Benchmark for Map-Free Transit Route Generation (transit route planning, large language models, dataset)
- [7.5|169↑|W21] Perception or Prejudice: Can MLLMs Go Beyond First Impressions of Personality? (personality perception, multimodal large language models, benchmark)
- [6.0|147↑|W19] MemPrivacy: Privacy-Preserving Personalized Memory Management for Edge-Cloud Agents (privacy-preserving ML, LLM agents, personalized memory)
- [6.5|140↑|W20] MulTaBench: Benchmarking Multimodal Tabular Learning with Text and Image (multimodal tabular learning, benchmark, representation learning)
- [6.0|132↑|W22] DVAO: Dynamic Variance-adaptive Advantage Optimization for Multi-reward Reinforcement Learning (multi-reward, GRPO, advantage optimization)
- [6.75|128↑|W22] LocateAnything: Fast and High-Quality Vision-Language Grounding with Parallel Box Decoding (visual grounding, parallel decoding, vision-language model)
- [5.5|110↑|W20] Qwen-Image-2.0 Technical Report (image generation, diffusion transformer, multimodal encoder)
- [6.5|109↑|W21] Rethinking Cross-Layer Information Routing in Diffusion Transformers (diffusion transformers, image generation, residual connections)
- [5.25|106↑|W21] Lens: Rethinking Training Efficiency for Foundational Text-to-Image Models (text-to-image generation, diffusion models, training efficiency)
- [7.75|102↑|W21] π-Bench: Evaluating Proactive Personal Assistant Agents in Long-Horizon Workflows (proactive agents, personal assistant, benchmark)
- [6.75|98↑|W20] Active Learners as Efficient PRP Rerankers (LLM reranking, pairwise ranking prompting, active learning)
- [6.25|90↑|W21] HRM-Text: Efficient Pretraining Beyond Scaling (efficient pretraining, recurrent neural networks, language modeling)
- [6.25|86↑|W19] MACE-Dance: Motion-Appearance Cascaded Experts for Music-Driven Dance Video Generation (music-driven dance generation, video generation, motion synthesis)
- [6.25|83↑|W21] IndusAgent: Reinforcing Open-Vocabulary Industrial Anomaly Detection with Agentic Tools (industrial anomaly detection, multimodal LLM, tool-augmented agent)
- [7.25|81↑|W22] ProRL: Effective Reinforcement Learning for Proactive Recommendation via Rectified Policy Gradient Estimation (proactive recommendation, reinforcement learning, policy gradient)
- [6.75|81↑|W21] OpenComputer: Verifiable Software Worlds for Computer-Use Agents (verifiable environments, computer-use agents, programmatic verification)
- [6.0|80↑|W19] Continuous Latent Diffusion Language Model (continuous latent diffusion, language models, hierarchical generative models)
- [6.5|77↑|W21] EvalVerse: Pipeline-Aware and Expert-Calibrated Benchmarking for Professional Cinematic Video Generation (video generation, benchmark, cinematic quality)
- [4.5|77↑|W21] Foundation Protocol: A Coordination Layer for Agentic Society (agent protocols, multi-agent systems, coordination layer)
- [5.5|77↑|W18] MiniCPM-o 4.5: Towards Real-Time Full-Duplex Omni-Modal Interaction (multimodal LLM, full-duplex interaction, speech generation)
- [6.0|76↑|W20] RubricEM: Meta-RL with Rubric-guided Policy Decomposition beyond Verifiable Rewards (Deep Research Agents, Reinforcement Learning from AI Feedback, GRPO)
- [6.75|70↑|W19] CollabVR: Collaborative Video Reasoning with Vision-Language and Video Generation Models (video reasoning, test-time scaling, vision-language models)
- [6.75|69↑|W19] LLMs Improving LLMs: Agentic Discovery for Test-Time Scaling (test-time scaling, automated algorithm discovery, LLM agents)
- [7.5|68↑|W22] SpatialBench: Is Your Spatial Foundation Model an All-Round Player? (3D reconstruction, benchmark, spatial foundation models)
- [5.75|65↑|W22] OmniRetrieval: Unified Retrieval across Heterogeneous Knowledge Sources (unified retrieval, heterogeneous knowledge sources, large language models)
- [6.5|64↑|W20] FashionChameleon: Towards Real-Time and Interactive Human-Garment Video Customization (human-centric video generation, garment customization, interactive video)
- [6.0|61↑|W20] Do Enterprise Systems Need Learned World Models? The Importance of Context to Infer Dynamics (world models, enterprise AI, configuration shift)
- [6.0|60↑|W20] Qwen-Image-VAE-2.0 Technical Report (variational autoencoder, high-compression VAE, latent diffusion models)
- [6.5|60↑|W20] Darwin Family: MRI-Trust-Weighted Evolutionary Merging for Training-Free Scaling of Language-Model Reasoning (model merging, evolutionary algorithms, large language models)
- [4.5|58↑|W21] SciAtlas: A Large-Scale Knowledge Graph for Automated Scientific Research (knowledge graph, scientific literature retrieval, neuro-symbolic AI)
- [5.25|57↑|W19] MCP-Cosmos: World Model-Augmented Agents for Complex Task Execution in MCP Environments (Model Context Protocol, world models, tool-augmented agents)
- [5.75|55↑|W19] MiA-Signature: Approximating Global Activation for Long-Context Understanding (retrieval-augmented generation, long-context understanding, memory-augmented LLMs)
- [5.75|53↑|W22] CollectionLoRA: Collecting 50 Effects in 1 LoRA via Multi-Teacher On-Policy Distillation (Multi-Teacher Distillation, LoRA, Diffusion Models)
- [6.5|52↑|W19] Geometry Conflict: Explaining and Controlling Forgetting in LLM Continual Post-Training (continual learning, model merging, geometry conflict)
- [5.0|52↑|W19] HumanNet: Scaling Human-centric Video Learning to One Million Hours (human-centric video, embodied AI, dataset)
- [7.5|50↑|W22] TriSplat: Simulation-Ready Feed-Forward 3D Scene Reconstruction (feed-forward reconstruction, triangle splatting, 3D mesh)
- [6.25|47↑|W19] RaguTeam at SemEval-2026 Task 8: Meno and Friends in a Judge-Orchestrated LLM Ensemble for Faithful Multi-Turn Response Generation (LLM ensemble, multi-turn RAG, faithfulness evaluation)
- [6.0|44↑|W21] PiD: Fast and High-Resolution Latent Decoding with Pixel Diffusion (latent diffusion, image super-resolution, pixel diffusion)
- [7.25|41↑|W22] YoCausal: How Far is Video Generation from World Model? A Causality Perspective (causal reasoning, video diffusion models, world models)
- [6.0|40↑|W19] MARBLE: Multi-Aspect Reward Balance for Diffusion RL (multi-reward RL, diffusion models, gradient harmonization)
- [6.75|33↑|W18] Let ViT Speak: Generative Language-Image Pre-training (vision-language pretraining, generative pretraining, vision transformers)