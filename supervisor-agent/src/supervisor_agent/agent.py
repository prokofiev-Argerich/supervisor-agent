"""Core supervisor agent implementation."""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from openai import AsyncOpenAI

from supervisor_agent.config import settings
from supervisor_agent.models import AgentRequest, AgentResponse, Message
from supervisor_agent.rag import query_similar
from supervisor_agent.schemas.paper import PaperRequest

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """Base supervisor agent for managing LLM-based tasks."""

    def __init__(self, name: str = "supervisor"):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        self.model = settings.openai_model

    async def process(self, request: AgentRequest) -> AgentResponse:
        """Process a request asynchronously."""
        self.logger.info(f"Processing request: {request.query}")
        try:
            response_text = f"Echo: {request.query}"
            return AgentResponse(
                response=response_text,
                status="success",
                metadata={"agent": self.name},
            )
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            return AgentResponse(
                response=f"Error: {str(e)}",
                status="error",
                metadata={"agent": self.name, "error": str(e)},
            )

    async def stream_paper(self, request: PaperRequest) -> AsyncGenerator[str, None]:
        """Stream paper generation via OpenAI, yielding SSE-formatted JSON lines.

        Stages: outline(0) → search(1) → writing(2) → review(3) → done
        """
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        keywords_hint = ""
        if request.keywords:
            keywords_hint = f"关键词：{', '.join(request.keywords)}\n"

        try:
            # ── Stage 0: Outline ──
            yield sse({"type": "status", "step": 0})
            outline_prompt = (
                f"请为以下主题生成一份学术论文大纲（Markdown 格式），"
                f"目标字数约 {request.word_count} 字。\n"
                f"主题：{request.topic}\n{keywords_hint}"
                f"语言：{request.language}\n"
                f"只输出大纲，不要写正文。"
            )
            outline_text = ""
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": outline_prompt}],
                stream=True,
                timeout=300,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    outline_text += delta
                    yield sse({"type": "content", "text": delta})

            # ── Stage 1: RAG Retrieval ──
            yield sse({"type": "status", "step": 1})
            query_text = f"{request.topic} {outline_text[:200]}"
            rag_chunks = await asyncio.to_thread(query_similar, query_text, 5)
            if rag_chunks:
                self.logger.info(f"RAG retrieved {len(rag_chunks)} chunks")
                ref_block = "\n\n---\n\n> **检索到 {} 条相关参考资料，已注入写作上下文。**\n\n---\n\n".format(len(rag_chunks))
            else:
                self.logger.warning("RAG returned no results — writing without references.")
                ref_block = "\n\n---\n\n> **知识库为空，将基于模型自身知识撰写。**\n\n---\n\n"
            yield sse({"type": "content", "text": ref_block})

            # ── Stage 2: Writing (with RAG context) ──
            yield sse({"type": "status", "step": 2})
            self.logger.info("Writing stage: sending request to OpenAI...")

            reference_section = ""
            if rag_chunks:
                formatted = "\n\n".join(f"[参考片段 {i+1}]\n{c}" for i, c in enumerate(rag_chunks))
                reference_section = f"\n\n参考资料（从知识库检索）：\n{formatted}\n\n"

            writing_prompt = (
                f"基于以下大纲和参考资料，撰写一篇完整的学术论文（Markdown 格式），"
                f"目标字数约 {request.word_count} 字。\n\n"
                f"大纲：\n{outline_text}\n\n"
                f"{reference_section}"
                f"主题：{request.topic}\n{keywords_hint}"
                f"语言：{request.language}\n"
                f"要求：必须严格基于给定的参考资料进行论述，保留学术严谨性。"
                f"请直接输出正文，使用 Markdown 标题、段落、列表等排版。"
            )
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": writing_prompt}],
                stream=True,
            )
            self.logger.info("Writing stage: stream connected, receiving chunks...")
            chunk_count = 0
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    chunk_count += 1
                    yield sse({"type": "content", "text": delta})
            self.logger.info(f"Writing stage: done, received {chunk_count} chunks")

            # ── Stage 3: Review ──
            yield sse({"type": "status", "step": 3})
            await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"stream_paper error: {e}")
            yield sse({"type": "error", "message": str(e)})

        # ── Done ──
        yield sse({"type": "done"})
