# Frontend

supervisor_AGENT 的 Next.js 前端,提供论文生成交互界面。

## 快速开始

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 后端地址配置

默认连接 `http://localhost:8000`。如果后端运行在其他地址,创建 `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://your-backend:8000
```

## 交互流程

1. 输入研究主题、字数上限、可选关键词 → 点击「生成大纲」
2. 预览大纲,可选择:
   - 输入修改意见 → 「提交修改意见」→ 修订大纲 (可反复)
   - 「确认并撰写」→ RAG 检索 → 逐节撰写 → 审查 → 局部重写 → 全文输出
3. 历史论文可在左侧列表查看和下载

## 技术栈

- Next.js 16 (App Router)
- React 19 + TypeScript (strict)
- Tailwind CSS v4
- shadcn/ui (base-nova)
- react-markdown
- framer-motion

## 项目结构

```
frontend/
├── app/
│   ├── layout.tsx      # 根布局
│   ├── page.tsx         # 主页面: SSE 消费 + 历史面板 + Markdown 渲染
│   └── globals.css      # Tailwind + shadcn 变量
├── components/
│   └── ui/              # shadcn/ui 原子组件
├── lib/
│   └── utils.ts         # cn() 工具
└── package.json
```
