# Paper Trending

LLM 研究论文的自动追踪、深度分析与趋势发现系统。从 arXiv / HuggingFace 采集论文，下载解析 PDF，通过 LLM 生成中文深度分析笔记，同步至 Obsidian，并生成周度趋势报告。

## 架构概览

```
arXiv / HuggingFace
        |
    collect          采集论文元数据
        |
    pdf_fetch        下载 PDF
        |
    pdf_parse        解析提取全文
        |
    processor        分块 + 向量化 (ChromaDB)
        |
    analyzer         LLM 深度分析 (中文)
        |
    sync             写入 Obsidian 笔记
        |
    reporter         HDBSCAN 聚类 + LLM 周报
```

每个阶段通过 `stage_runs` 表驱动，支持重试和幂等。

## 技术栈

- **后端:** Python 3.11+ / FastAPI / aiosqlite / ChromaDB
- **前端:** React 19 / TypeScript / Vite / TailwindCSS / TanStack Query
- **LLM:** OpenAI API 协议 (兼容任意 OpenAI-compatible 服务)
- **向量存储:** ChromaDB (本地持久化)

## 快速开始

### 环境要求

- Python >= 3.11
- Node.js >= 20
- npm >= 10

### 后端

```bash
# 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 准备配置文件
cp settings.example.yaml settings.yaml
# 编辑 settings.yaml，填入 api_key 或设置 OPENAI_API_KEY 环境变量

# 运行测试
pytest tests/ -v

# 启动开发服务器
uvicorn backend.main:app --reload --port 8000
```

启动后可访问：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173，`/api` 请求会自动代理到后端 8000 端口。

## 配置

配置文件为项目根目录的 `settings.yaml`（从 `settings.example.yaml` 复制），优先级：

1. 配置文件中的直接值 (`api_key: "sk-xxx"`)
2. 配置文件中的环境变量引用 (`api_key: "${OPENAI_API_KEY}"`)
3. 留空时自动读取 `OPENAI_API_KEY` 环境变量

主要配置项：

| 配置项 | 说明 |
|--------|------|
| `llm.base_url` | LLM 服务地址，兼容 OpenAI 协议 |
| `llm.model` | 分析用模型，默认 `gpt-4o` |
| `embedding.model` | 向量化模型，默认 `text-embedding-3-small` |
| `arxiv.categories` | 监控的 arXiv 分类 |
| `obsidian.vault_path` | Obsidian vault 路径 |
| `storage.data_root` | 数据存储根目录 |

## 项目结构

```
paper-trending/
├── backend/
│   ├── main.py              # FastAPI 入口，lifespan 初始化
│   ├── api/                 # REST API (papers, reports, search, jobs)
│   ├── collectors/          # arXiv / HuggingFace 采集器
│   ├── pdf/                 # PDF 下载与解析
│   ├── processor/           # 文本分块 + 向量化
│   ├── analyzer/            # LLM 深度分析
│   ├── sync/                # Obsidian 笔记同步
│   ├── reporter/            # 聚类 + 周报生成
│   ├── scheduler/           # 流水线调度 + 回填任务
│   ├── config/              # 配置加载
│   └── core/                # DB / StageRunner / LLM Client / 向量存储
├── frontend/                # React + TypeScript Web UI
├── tests/                   # pytest 测试套件
├── settings.example.yaml    # 配置模板
└── pyproject.toml
```

## 开发

```bash
# 运行测试
pytest tests/ -v

# 代码检查
ruff check .

# 前端类型检查 + 构建
cd frontend && npm run build
```

## License

MIT
