"""Supervisor agent — thin wrapper that drives LangGraph and yields SSE.

Two public methods:
    stream_outline()  — run Planner only, return outline for user preview
    stream_paper()    — run full pipeline (Researcher→Writer→Reviewer loop)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from supervisor_agent.graph import build_outline_graph, build_full_graph, build_revise_graph
from supervisor_agent.models import AgentRequest, AgentResponse
from supervisor_agent.schemas.paper import PaperRequest

logger = logging.getLogger(__name__)

_SENTINEL = object()  # marks end-of-queue


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class SupervisorAgent:
    """Drives the LangGraph pipeline and streams SSE events."""

    def __init__(self, name: str = "supervisor"):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    async def process(self, request: AgentRequest) -> AgentResponse:
        """Generic echo (backward compat)."""
        return AgentResponse(
            response=f"Echo: {request.query}",
            status="success",
            metadata={"agent": self.name},
        )

    # ── Phase 1 ──

    async def stream_outline(
        self, request: PaperRequest,
    ) -> AsyncGenerator[str, None]:
        """Run Planner graph, stream outline via SSE in real-time."""
        graph = build_outline_graph()
        queue: asyncio.Queue = asyncio.Queue()
        state = {
            "topic": request.topic,
            "word_count": request.word_count,
            "keywords": request.keywords or [],
            "language": request.language or "zh",
            "messages": [],
        }

        async def _run() -> None:
            try:
                await graph.ainvoke(
                    state, config={"configurable": {"queue": queue}},
                )
            except Exception as e:
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(_SENTINEL)

        task = asyncio.create_task(_run())
        try:
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                yield _sse(item)
        finally:
            if not task.done():
                task.cancel()
        yield "data: [DONE]\n\n"

    # ── Phase 1.5: Revise outline ──

    async def stream_revise_outline(
        self,
        request: PaperRequest,
        outline: str,
        sections: list[str],
        feedback: str,
    ) -> AsyncGenerator[str, None]:
        """Revise outline based on user feedback, stream SSE in real-time."""
        graph = build_revise_graph()
        queue: asyncio.Queue = asyncio.Queue()
        state = {
            "topic": request.topic,
            "word_count": request.word_count,
            "keywords": request.keywords or [],
            "language": request.language or "zh",
            "outline": outline,
            "sections": sections,
            "feedback": feedback,
            "messages": [],
            "max_revisions": request.max_revisions,
        }

        async def _run() -> None:
            try:
                await graph.ainvoke(
                    state, config={"configurable": {"queue": queue}},
                )
            except Exception as e:
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(_SENTINEL)

        task = asyncio.create_task(_run())
        try:
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                yield _sse(item)
        finally:
            if not task.done():
                task.cancel()
        yield "data: [DONE]\n\n"

    # ── Phase 2 ──

    async def stream_paper(
        self,
        request: PaperRequest,
        outline: str,
        sections: list[str],
    ) -> AsyncGenerator[str, None]:
        """Run Researcher → Writer → Reviewer loop, stream SSE in real-time."""
        graph = build_full_graph()
        queue: asyncio.Queue = asyncio.Queue()
        state = {
            "topic": request.topic,
            "word_count": request.word_count,
            "keywords": request.keywords or [],
            "language": request.language or "zh",
            "outline": outline,
            "sections": sections,
            "outline_approved": True,
            "messages": [],
            "revision_count": 0,
            "max_revisions": request.max_revisions,  # 把前端传来的重写上限透传给Graph
            "draft_sections": [],           # 为局部重写提前备好空的草稿列表
            "section_feedbacks": {},         # 为局部重写提前备好空的意见字典
        }

        async def _run() -> None:
            try:
                await graph.ainvoke(
                    state, config={"configurable": {"queue": queue}},
                )
            except Exception as e:
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(_SENTINEL)

        task = asyncio.create_task(_run())
        try:
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                yield _sse(item)
        finally:
            if not task.done():
                task.cancel()
        yield "data: [DONE]\n\n"
