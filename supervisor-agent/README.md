# Supervisor Agent

基于 FastAPI + LangGraph 的智能论文生成系统，支持大纲生成、人工修订、RAG 检索增强和流式全文撰写。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                     │
│  app/page.tsx — SSE 流式交互界面                         │
│                                                         │
│  用户流程:                                               │
│  输入主题 → 生成大纲 → [修改意见 ↔ 修订大纲] → 确认撰写  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP + SSE
┌────────────────────────▼────────────────────────────────┐
│  Backend (FastAPI)                                      │
│                                                         │
│  API 端点:                                               │
│    POST /api/generate_outline  — 生成大纲                │
│    POST /api/revise_outline    — 根据反馈修订大纲         │
│    POST /api/confirm_and_write — 确认大纲并撰写全文       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Agent 层 (agent.py)                                    │
│    stream_outline()         → build_outline_graph()     │
│    stream_revise_outline()  → build_revise_graph()      │
│    stream_paper()           → build_paper_graph()       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  LangGraph 工作流 (graph.py)                             │
│                                                         │
│  outline_graph:  outline_node                           │
│  revise_graph:   revise_outline_node                    │
│  paper_graph:    search_node → write_node → review_node │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  节点实现 (nodes.py) + RAG 检索 (rag.py)                 │
│  状态定义 (state.py) + 数据模型 (schemas/)               │
└─────────────────────────────────────────────────────────┘
```

## 项目结构

```
supervisor-agent/
├── src/supervisor_agent/
│   ├── main.py              # FastAPI 入口，路由定义
│   ├── agent.py             # SupervisorAgent，流式调度 LangGraph
│   ├── graph.py             # LangGraph 工作流构建
│   ├── nodes.py             # 各节点实现（大纲/修订/检索/撰写/校对）
│   ├── state.py             # PaperState 状态定义（含 feedback 字段）
│   ├── rag.py               # RAG 向量检索
│   ├── config.py            # 配置管理
│   ├── models.py            # 通用 Pydantic 模型
│   └── schemas/
│       ├── paper.py         # PaperRequest / ConfirmRequest / ReviseRequest
│       └── review.py        # 校对相关模型
├── tests/
├── pyproject.toml
└── README.md

frontend/
├── app/
│   └── page.tsx             # 主页面（主题输入/大纲预览/修改意见/全文展示）
├── components/ui/           # shadcn/ui 组件
└── package.json
```

## 快速开始

### 后端

```bash
cd supervisor-agent
python -m venv venv
venv\Scripts\activate        # Linux/Mac: source venv/bin/activate
pip install -e ".[dev]"

# 配置环境变量
cp .env.example .env         # 填入 OPENAI_API_KEY 等

# 启动
uvicorn supervisor_agent.main:app --reload
```

API 地址: http://localhost:8000 ，文档: http://localhost:8000/docs

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 交互流程

1. 用户输入研究主题和字数上限
2. `POST /api/generate_outline` → 流式返回大纲
3. 用户审阅大纲，可选择：
   - 输入修改意见 → `POST /api/revise_outline` → 流式返回修订大纲（可反复）
   - 重新生成 → 回到步骤 2
   - 确认并撰写 → 进入步骤 4
4. `POST /api/confirm_and_write` → RAG 检索 → 分段撰写 → 排版校对 → 流式返回全文

## 配置

```env
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=''
OPENAI_MODEL=''
LOG_LEVEL=INFO
```

## License

MIT
