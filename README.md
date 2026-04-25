# Supervisor Agent

面向严肃学术长文调研与生成场景的端到端闭环 AI 系统。

AI 负责文献检索、长文起草与格式排版；用户（Human-in-the-loop）负责全局大纲确认、修改意见反馈与核心研究方向定调。基于 FastAPI + LangGraph 构建，支持大纲生成、人工动态修订、RAG 检索增强和流式（SSE）全文撰写。

---

## 💡 核心设计与特性

### 1. 多节点状态流转编排 (LangGraph)
弃用黑盒框架，采用 LangGraph 状态机编排执行流程，拆分为四大核心节点：
* **Planner（规划）：** 根据用户主题生成结构化大纲，支持接收反馈并动态重构大纲。
* **Researcher（检索）：** 基于确认后的大纲调用 RAG 检索知识库，精确召回相关文献片段。
* **Writer（撰写）：** 携带检索上下文逐章撰写，动态滑动窗口截断历史，解决长文本 Token 爆炸与注意力涣散。
* **Reviewer（审稿）：** 采用 Pydantic 结构化约束的审查节点，拦截虚假引用，锚定文献真实性。

### 2. 人机协同工作流 (Human-in-the-loop)
引入大纲修订循环机制。用户在生成长文前，可对 AI 生成的初始大纲提出具体的修改意见（如“第三章拆成两节”、“增加文献综述章节”），系统将结合历史大纲与反馈重新规划，直到用户满意后才触发高成本的全文撰写与检索。

### 3. 代码级语义切块 (LaTeX RAG)
创新性抛弃常规 PDF 解析，基于 LaTeX 原生标签（`\section`、`\subsection`）实现语义切块。元数据（章节层级、标题）强绑定至 ChromaDB 向量条目，检索精度远超朴素文本分割。

### 4. 流式交互架构 (SSE)
基于 FastAPI 异步路由与 SSE 单向流式通信，打造丝滑的前端打字机体验。

---

## 🏗️ 架构概览

    ┌─────────────────────────────────────────────────────────┐
    │  Frontend (Next.js)                                     │
    │  app/page.tsx — SSE 流式交互界面                         │
    │                                                         │
    │  用户流程:                                               │
    │  输入主题 → 生成大纲 → [输入修改意见 ↔ 重新生成大纲] → 确认撰写 │
    └────────────────────────┬────────────────────────────────┘
                             │ HTTP + SSE
    ┌────────────────────────▼────────────────────────────────┐
    │  Backend (FastAPI)                                      │
    │                                                         │
    │  API 端点:                                               │
    │    POST /api/generate_outline  — 初次生成大纲            │
    │    POST /api/revise_outline    — 根据反馈修订大纲         │
    │    POST /api/confirm_and_write — 确认大纲并执行 RAG 撰写  │
    └────────────────────────┬────────────────────────────────┘
                             │
    ┌────────────────────────▼────────────────────────────────┐
    │  Agent & LangGraph 编排层 (agent.py / graph.py)           │
    │                                                         │
    │  outline_graph:  Planner 规划初始大纲                     │
    │  revise_graph:   Planner 接收 feedback 重构大纲           │
    │  paper_graph:    Researcher → Writer → Reviewer         │
    └─────────────────────────────────────────────────────────┘

---

## 📂 项目结构

    supervisor-agent/
    ├── src/supervisor_agent/
    │   ├── main.py              # FastAPI 入口，路由定义与 SSE 流生成
    │   ├── agent.py             # SupervisorAgent，调度各个 Graph
    │   ├── graph.py             # LangGraph 工作流图构建
    │   ├── nodes.py             # 各节点业务逻辑（规划/修订/检索/撰写/校对）
    │   ├── state.py             # 全局状态定义（PaperState，包含 feedback 字段）
    │   ├── rag.py               # RAG 向量检索与 ChromaDB 交互
    │   ├── config.py            # 环境变量与配置管理
    │   ├── ingest_latex.py      # 知识库构建脚本（LaTeX 语义解析入库）
    │   └── schemas/             # Pydantic 数据验证模型
    │       ├── paper.py         # 包含 ReviseRequest 等请求模型
    │       └── review.py        # 审稿与排版相关模型
    ├── frontend/                # Next.js 交互前端
    │   ├── app/page.tsx         # 主页面（主题输入/大纲预览/反馈弹窗/全文展示）
    │   └── components/ui/       # shadcn/ui 组件库
    └── .env.example             # 环境变量配置模板

---

## 🚀 快速开始

### 1. 环境准备与配置

在项目根目录复制环境变量模板并填入您的配置：

    cp .env.example .env

**关键环境变量说明：**

| 变量 | 说明 |
| :--- | :--- |
| `OPENAI_API_KEY` | 您的 API 密钥（必填） |
| `OPENAI_BASE_URL` | 自定义 API 代理地址（可选，兼容 DeepSeek / Ollama 等兼容协议服务） |
| `OPENAI_MODEL` | 使用的模型名称，默认推荐 `gpt-4-turbo-preview` |
| `LOG_LEVEL` | 日志级别，默认 `INFO` |

### 2. 启动后端 (FastAPI)

建议使用 Python 3.11+ 虚拟环境：

    cd supervisor-agent
    python -m venv venv
    source venv/bin/activate     # Windows 用户请使用: venv\Scripts\activate
    pip install -e ".[dev]"      # 或 pip install -r requirements.txt
    
    # 启动后端服务
    uvicorn supervisor_agent.main:app --reload

后端服务将运行在 `http://localhost:8000`。
您可以访问 `http://localhost:8000/docs` 查看交互式 API 接口文档。

### 3. 构建本地知识库 (可选)

如果需要 RAG 检索功能，请提前导入您的 LaTeX 语料库：

    python ingest_latex.py /path/to/your/latex/files

### 4. 启动前端 (Next.js)

新开一个终端窗口，进入前端目录：

    cd frontend
    npm install
    npm run dev
    # 或 yarn dev / pnpm dev

前端服务将运行在 `http://localhost:3000`。在浏览器中打开即可开始体验流式论文生成。

---
