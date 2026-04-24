# Supervisor Agent

面向严肃学术长文调研与生成场景的端到端闭环 AI 系统。

AI 负责文献检索、长文起草与格式排版；用户（Human-in-the-loop）负责全局大纲确认与核心研究方向定调。

## 项目结构

```
supervisor-agent/   # 后端 — FastAPI + LangGraph + ChromaDB
frontend/           # 前端 — Next.js + React + shadcn/ui
```

## 核心设计

### 多节点状态流转编排

弃用黑盒框架，采用 LangGraph 状态机编排执行流程，拆分为四大核心节点：

```
Planner（规划） → Researcher（检索） → Writer（撰写） → Reviewer（审稿）
    ↑                                                       │
    └───────────── 打回修订 ←────────────────────────────────┘
```

- Planner：根据用户主题生成结构化大纲，等待用户确认后推进
- Researcher：基于大纲调用 RAG 检索知识库，召回相关文献片段
- Writer：携带检索上下文逐章撰写，动态滑动窗口截断历史，解决长文本 Token 爆炸与注意力涣散
- Reviewer：Pydantic 结构化约束审查节点，拦截虚假引用，锚定文献真实性

### 代码级语义切块

创新性抛弃常规 PDF 解析，基于 LaTeX 原生标签（`\section`、`\subsection`）实现语义切块，元数据（章节层级、标题）强绑定至 ChromaDB 向量条目，检索精度远超朴素文本分割。

### 流式架构

FastAPI 异步路由 + SSE 单向流式通信，打通后端多节点状态与前端实时 Markdown 渲染：

```
Backend (SSE)                    Frontend
  ├─ {type:"status", step:0}  →  规划大纲中
  ├─ {type:"status", step:1}  →  检索知识库中
  ├─ {type:"content", text:…} →  实时渲染 Markdown
  ├─ {type:"status", step:3}  →  排版校对中
  └─ {type:"done"}            →  生成完成
```

## 快速开始

### 后端

```bash
cd supervisor-agent
cp .env.example .env        # 填入 API Key
pip install -r requirements.txt
python -m supervisor_agent.main
```

### 知识库导入

```bash
cd supervisor-agent
python ingest_latex.py /path/to/your/latex/files
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:3000`。

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | API 密钥 |
| `OPENAI_BASE_URL` | 自定义 API 地址（可选，兼容 DeepSeek / Ollama） |
| `OPENAI_MODEL` | 模型名称，默认 `gpt-4-turbo-preview` |

## 技术栈

- Python 3.11+ / FastAPI / LangGraph / LangChain / ChromaDB
- Next.js / React / Tailwind CSS / shadcn/ui
