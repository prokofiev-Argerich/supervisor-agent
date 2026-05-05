# supervisor_AGENT

## Overview

`supervisor_AGENT` is an **Agentic RAG paper generation MVP**. It turns a topic + word budget + optional keywords into a long-form Markdown paper through a multi-node LangGraph pipeline backed by a local LaTeX knowledge base.

It is **not** a production system, a citation manager, or a proofreading tool. It is a research-oriented MVP that demonstrates an end-to-end loop from outline to reviewed final paper, with streaming progress, source-tagged drafting, and durable per-task artifacts.

The project is a monorepo: a Next.js frontend talks to a FastAPI + LangGraph backend, which orchestrates Planner → Researcher → Writer → Reviewer nodes around a ChromaDB-backed RAG layer.

---

## Features

- **Outline generation** — produces a structured outline from `topic`, `word_count`, and optional `keywords`.
- **Outline revision** — accepts free-text feedback and regenerates the outline before full writing.
- **RAG retrieval** — Researcher node pulls top-k LaTeX chunks from ChromaDB, scoped per section title.
- **LangGraph supervisor pipeline** — Planner → Researcher → Writer → Reviewer with conditional re-write routing.
- **Section-by-section writing** — Writer drafts each section independently with a sliding-window summary of prior content.
- **Reviewer-driven surgical rewrite** — Reviewer reads RAG evidence and emits per-section feedback; only flagged sections are rewritten, untouched sections are skipped at zero cost.
- **Source tag traceability** — Writer is prompted to include `[source: filename]` markers when it leans on retrieved evidence; Reviewer also checks these markers.
- **SSE streaming** — `status / content / final_paper / done` events stream live to the browser.
- **Markdown artifacts** — every completed paper is persisted under `artifacts/{task_id}/`.
- **Per-task download** — `task_id` based Markdown download endpoint.
- **History list & restore** — past generations are listed in the UI; reopening a past task restores its final paper into the preview pane.

---

## Architecture

```mermaid
flowchart LR
    subgraph FE[Frontend - Next.js]
        UI[app/page.tsx]
    end

    subgraph BE[Backend - FastAPI]
        API[/api/* SSE endpoints/]
        AGT[SupervisorAgent]
    end

    subgraph GR[LangGraph Pipeline]
        P[Planner]
        R[Researcher]
        W[Writer]
        RV[Reviewer]
    end

    subgraph DATA[Local Storage]
        CH[(ChromaDB)]
        ART[(artifacts/{task_id})]
    end

    LLM{{OpenAI-compatible LLM}}

    UI -- POST + SSE --> API
    API --> AGT
    AGT --> P --> R --> W --> RV
    RV -- needs revision --> W
    RV -- approved --> AGT

    R <--> CH
    P <--> LLM
    W <--> LLM
    RV <--> LLM

    AGT -- final_paper --> ART
    UI -- list / open / download --> ART
```

The pipeline is driven by a typed `PaperState` that carries `topic`, `outline`, `sections`, `section_drafts`, `section_feedbacks`, RAG evidence, and revision counters. Reviewer feedback is structured (Pydantic) and indexed by `section_idx`, which is what enables the localized rewrite loop.

---

## Tech Stack

**Frontend**

- Next.js 16 (App Router)
- React 19
- TypeScript (strict)
- Tailwind CSS v4
- shadcn/ui
- react-markdown
- framer-motion, lucide-react

**Backend**

- FastAPI
- Python 3.11+
- LangGraph
- LangChain (OpenAI + Chroma adapters)
- AsyncOpenAI (OpenAI-compatible client — works with OpenAI, DeepSeek, SiliconFlow, Kimi, etc.)
- ChromaDB (local PersistentClient)
- pydantic / pydantic-settings
- SSE via FastAPI `StreamingResponse`

There is currently **no** SQLite, Postgres, Redis, Celery, or user system.

---

## Project Structure

```txt
supervisor_AGENT/
├── frontend/
│   ├── app/page.tsx              # main UI + SSE consumer + history panel
│   ├── components/ui/            # shadcn/ui primitives
│   └── package.json
│
├── supervisor-agent/
│   ├── src/supervisor_agent/
│   │   ├── main.py               # FastAPI app + SSE endpoints + artifact routes
│   │   ├── agent.py              # SupervisorAgent: state assembly + stream wiring
│   │   ├── graph.py              # LangGraph workflow + conditional edges
│   │   ├── nodes.py              # Planner / Researcher / Writer / Reviewer
│   │   ├── state.py              # PaperState TypedDict
│   │   ├── rag.py                # ChromaDB retrieval helpers
│   │   ├── artifacts.py          # task_id, save/list/load artifact, path safety
│   │   ├── config.py             # pydantic-settings env loader
│   │   └── schemas/              # paper / review Pydantic models
│   ├── ingest_latex.py           # offline LaTeX → ChromaDB ingestion script
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── .env.example
│
├── .gitignore
├── CLAUDE.md                     # project-specific AI coding rules
└── README.md
```

`supervisor-agent/artifacts/` is created at runtime and is gitignored.

---

## Environment Variables

### Backend (`supervisor-agent/.env`)

| Var | Required | Notes |
| --- | --- | --- |
| `OPENAI_API_KEY` | yes | Any OpenAI-compatible key. |
| `OPENAI_BASE_URL` | optional | Override for DeepSeek / SiliconFlow / Kimi / local proxies. Empty = default OpenAI endpoint. |
| `OPENAI_MODEL` | optional | Defaults to `gpt-4-turbo-preview`. Set to `deepseek-chat`, `gpt-4o-mini`, etc. |
| `HOST` | optional | Defaults to `0.0.0.0`. |
| `PORT` | optional | Defaults to `8000`. |
| `LOG_LEVEL` | optional | Defaults to `INFO`. |

A template lives at `supervisor-agent/.env.example`. Never commit the real `.env`.

### Frontend (`frontend/.env.local`)

| Var | Required | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | optional | Backend base URL. Defaults to `http://localhost:8000`. |

---

## Installation

### Backend

```bash
cd supervisor-agent

python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in OPENAI_API_KEY (and optional BASE_URL / MODEL)

uvicorn src.supervisor_agent.main:app --reload
```

The API will be served on `http://localhost:8000` (`/docs` for OpenAPI).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI runs on `http://localhost:3000`. If your backend is on a non-default host, create `frontend/.env.local` with `NEXT_PUBLIC_API_BASE_URL=...`.

---

## RAG / Knowledge Base

- The knowledge base is a local **ChromaDB** PersistentClient stored in `chroma_db/` (gitignored).
- `supervisor-agent/ingest_latex.py` is an offline script that ingests LaTeX files:
  - strips `\begin{document}` preamble and comments,
  - chunks on LaTeX-aware separators (`\section`, `\subsection`, `\subsubsection`, paragraph, line),
  - tags each chunk with metadata `{ source, section, level }` so retrieval can be scoped per section title.
- The Researcher node retrieves top-k chunks per outline section heading, optionally biased by user-provided keywords.
- The Writer node receives the retrieved snippets as evidence and is prompted to emit `[source: filename]` markers when leaning on them.
- The Reviewer node sees the same evidence and checks for missing or fabricated source tags as part of its critique.

The `[source: filename]` tag is a **MVP-grade traceability hint**, not a formal citation system. There is no BibTeX/APA/GB-T formatting, deduplication, or reference list generation.

---

## Usage Flow

1. Open the UI, enter `topic`, `word_count`, optional `keywords` (comma-separated), and `max_revisions`.
2. Click **生成大纲** — outline streams in.
3. Either type free-text feedback and **提交修改意见** to revise the outline, or click **确认并撰写** to lock it in.
4. Full paper streams section-by-section. Reviewer may trigger surgical rewrites of individual sections; the rest is skipped.
5. When `final_paper` arrives, the streamed draft is replaced with the clean final version, and the artifact is persisted to `supervisor-agent/artifacts/{task_id}/`.
6. Click **下载 Markdown** to save the file, or open any past paper from the **历史生成** list in the left sidebar.
7. Refreshing the page restores the history list from the backend.

---

## API Summary

All endpoints are under the FastAPI app exposed by `supervisor-agent/src/supervisor_agent/main.py`.

### Generation (SSE)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/generate_outline` | Stream initial outline. |
| POST | `/api/revise_outline` | Stream revised outline given user feedback. |
| POST | `/api/confirm_and_write` | Run the full pipeline; emits `status`, `content`, `final_paper` (with `task_id` + `download_url`), and `done` events. |

### Artifacts

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/artifacts` | List saved artifacts, sorted by `created_at` desc. |
| GET | `/api/artifacts/{task_id}` | Return `metadata.json` for a single task. |
| GET | `/api/artifacts/{task_id}/content` | Return `{ task_id, text }` (final paper Markdown body). |
| GET | `/api/artifacts/{task_id}/download` | Download `final_paper.md` as a file. |

### Misc

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness probe. |
| GET | `/` | Root info JSON. |
| POST | `/agent/process` | Legacy non-streaming agent entry. |

`task_id` must be a strict UUIDv4. Bad format returns `400`; missing artifact returns `404`.

---

## Artifact Storage

```txt
supervisor-agent/artifacts/
└── {task_id}/
    ├── final_paper.md
    └── metadata.json
```

`metadata.json` carries `task_id`, `created_at`, `status`, `topic`, `word_count`, `keywords`, `language`, `max_revisions`. The list endpoint always overrides `task_id`, `download_url`, and `content_url` based on the directory name, so tampered metadata cannot redirect URLs.

`artifacts/` is **local single-machine storage** and is gitignored. Treat it as ephemeral / per-developer.

---

## Known Limitations

- No user system, auth, or multi-tenant isolation.
- No background task queue (Celery / Redis); generation runs in-request through the SSE response lifetime.
- No database — artifacts live on the local filesystem.
- No formal citation manager — `[source: filename]` tags are MVP traceability hints, not BibTeX/APA/GB-T citations.
- No PDF or LaTeX export — output is plain Markdown only.
- Reviewer is LLM-judged; there is no deterministic fact-checker, no structured fact set, and no scoring rubric beyond the prompt and Pydantic schema validation.
- `final_paper` SSE payload includes the entire paper string. There is no incremental patching for very large papers.
- Word-count enforcement is best-effort via prompting and per-section budgets; the model may still drift.
- Artifacts list is unpaginated.
- LaTeX ingestion expects well-formed `\section{}` style sources; arbitrary PDFs are out of scope.

---

## Roadmap

- Citation manager with deduplication, anchor IDs, and a generated reference list.
- BibTeX import + LaTeX/PDF export pipeline.
- User-uploaded reference materials per task.
- Persistent task index in SQLite/Postgres so artifact listing does not depend on filesystem scan.
- Background queue (Celery + Redis) so long-running generations survive disconnects.
- Stronger Reviewer with deterministic validation passes (structure check, section-budget check, source-tag presence check).
- Configurable retrieval — multi-query expansion, reranker, per-section keyword overrides.
- Multi-language paper output and prompt packs.

---

## Development Notes

- All UI strings are currently zh-CN; the underlying schema accepts a `language` field (defaults to `"zh"`).
- The frontend assumes a single-tenant local backend at `NEXT_PUBLIC_API_BASE_URL`. CORS in `main.py` is wide open (`allow_origins=["*"]`) for dev convenience.
- `CLAUDE.md` at the repo root documents project-specific AI coding rules (think first, simplicity first, surgical changes, goal-driven execution).

---

## License

No license file is present yet. Until one is added, treat the code as **all rights reserved** by the repository owner.
