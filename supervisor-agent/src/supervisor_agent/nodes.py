"""LangGraph node functions for the paper-generation pipeline.

Each node is an async function: (state, config) -> dict
returning only the fields it wants to update.
Nodes receive an asyncio.Queue via config["configurable"]["queue"]
and push SSE events in real-time (Producer side of the queue pattern).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from langchain_core.runnables import RunnableConfig
from openai import AsyncOpenAI

from supervisor_agent.config import settings
from supervisor_agent.rag import query_similar
from supervisor_agent.schemas.review import ReviewResult

logger = logging.getLogger(__name__)

# ── Shared LLM client (module-level singleton) ──
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
    return _client


def _model() -> str:
    return settings.openai_model


def _get_queue(config: RunnableConfig) -> asyncio.Queue | None:
    """Extract the streaming queue from LangGraph config, if present."""
    return (config.get("configurable") or {}).get("queue")


# ─────────────────────────────────────────────
# Planner Node
# ─────────────────────────────────────────────

async def planner_node(state: dict, config: RunnableConfig) -> dict:
    """Generate a structured outline and extract section titles."""
    logger.info("[Planner] generating outline …")
    queue = _get_queue(config)

    # 👇 新增核心逻辑：帮大模型做算术
    # 假设每章平均 500 字，计算出合理的章节数
    word_count = state.get('word_count', 3000)
    # 限制大纲最多不超过 8 章，最少 2 章，防止极端情况
    expected_sections = max(2, min(8, word_count // 500)) 

    keywords_hint = ""
    if state.get("keywords"):
        keywords_hint = f"关键词：{', '.join(state['keywords'])}\n"

    # 👇 重写 Prompt：将算出的章节数作为绝对命令下达
    prompt = (
        f"请为以下主题生成一份学术论文大纲（Markdown 格式）。\n"
        f"⚠️ 核心死命令：本文总目标字数为 {word_count} 字，因此你【必须且只能】规划 {expected_sections} 个一级章节（##）。绝不能超出此数量！\n"
        f"主题：{state['topic']}\n{keywords_hint}"
        f"语言：{state.get('language', 'zh')}\n"
        f"要求：\n"
        f"1. 严格遵守上述章节数量限制！\n"
        f"2. 使用 Markdown 标题层级（## 一级章节，### 二级章节）\n"
        f"3. 每个章节下简要说明该章节要写什么（1-2 句话）\n"
        f"4. 只输出大纲，不要写正文。"
    )

    client = _get_client()

    outline_text = ""
    messages: list[dict] = [{"type": "status", "step": 0}]
    if queue:
        await queue.put({"type": "status", "step": 0})

    stream = await client.chat.completions.create(
        model=_model(),
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        timeout=300,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content or ""
        if delta:
            outline_text += delta
            messages.append({"type": "content", "text": delta})
            if queue:
                await queue.put({"type": "content", "text": delta})

    # 👇 强制只提取 ## 的一级章节，让 ### 留在章节内部由 Writer 自己发挥
    sections = re.findall(r"^##\s+(.+)$", outline_text, re.MULTILINE)
    if not sections:
        sections = re.findall(r"^\d+.\s+(.+)$", outline_text, re.MULTILINE)

    logger.info(f"[Planner] outline done, {len(sections)} sections extracted")

    # Push outline_done so consumer can yield it before graph returns
    if queue:
        await queue.put({
            "type": "outline_done",
            "outline": outline_text,
            "sections": sections,
        })

    return {
        "outline": outline_text,
        "sections": sections,
        "messages": state.get("messages", []) + messages,
    }


# ─────────────────────────────────────────────
# Revise Outline Node
# ─────────────────────────────────────────────

async def revise_outline_node(state: dict, config: RunnableConfig) -> dict:
    """Revise an existing outline based on user feedback."""
    logger.info("[Revise] revising outline based on user feedback …")
    queue = _get_queue(config)

    feedback = state.get("feedback", "")
    current_outline = state.get("outline", "")

    prompt = (
        f"以下是一份学术论文大纲（Markdown 格式）：\n\n{current_outline}\n\n"
        f"用户对这份大纲提出了修改意见：\n{feedback}\n\n"
        f"请根据用户的修改意见修订大纲。要求：\n"
        f"1. 保持 Markdown 标题层级（## 一级章节，### 二级章节）\n"
        f"2. 每个章节下简要说明该章节要写什么（1-2 句话）\n"
        f"3. 只输出修订后的完整大纲，不要写正文，不要解释修改了什么。"
    )

    client = _get_client()
    outline_text = ""
    messages: list[dict] = [{"type": "status", "step": 0}]
    if queue:
        await queue.put({"type": "status", "step": 0})

    stream = await client.chat.completions.create(
        model=_model(),
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        timeout=300,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content or ""
        if delta:
            outline_text += delta
            messages.append({"type": "content", "text": delta})
            if queue:
                await queue.put({"type": "content", "text": delta})

    # 👇 强制只提取 ## 的一级章节，让 ### 留在章节内部由 Writer 自己发挥
    sections = re.findall(r"^##\s+(.+)$", outline_text, re.MULTILINE)
    if not sections:
        sections = re.findall(r"^\d+.\s+(.+)$", outline_text, re.MULTILINE)

    logger.info(f"[Revise] revised outline done, {len(sections)} sections extracted")

    if queue:
        await queue.put({
            "type": "outline_done",
            "outline": outline_text,
            "sections": sections,
        })

    return {
        "outline": outline_text,
        "sections": sections,
        "messages": state.get("messages", []) + messages,
    }


# ─────────────────────────────────────────────
# Researcher Node
# ─────────────────────────────────────────────

async def researcher_node(state: dict, config: RunnableConfig) -> dict:
    """Retrieve RAG chunks for each section title."""
    logger.info("[Researcher] retrieving knowledge …")
    queue = _get_queue(config)

    messages: list[dict] = [{"type": "status", "step": 1}]
    if queue:
        await queue.put({"type": "status", "step": 1})

    sections = state.get("sections", [])
    topic = state.get("topic", "")

    all_chunks: list[dict] = []
    seen_texts: set[str] = set()

    for sec_title in sections:
        query = f"{topic} {sec_title}"
        chunks = await asyncio.to_thread(
            query_similar, query, 3, None, with_metadata=True,
        )
        for c in chunks:
            text = c["text"] if isinstance(c, dict) else c
            if text not in seen_texts:
                seen_texts.add(text)
                all_chunks.append(c if isinstance(c, dict) else {"text": c, "metadata": {}})

    if all_chunks:
        ref_msg = f"\n\n---\n\n> **检索到 {len(all_chunks)} 条相关参考资料，已注入写作上下文。**\n\n---\n\n"
    else:
        ref_msg = "\n\n---\n\n> **知识库为空，将基于模型自身知识撰写。**\n\n---\n\n"

    messages.append({"type": "content", "text": ref_msg})
    if queue:
        await queue.put({"type": "content", "text": ref_msg})
    logger.info(f"[Researcher] retrieved {len(all_chunks)} unique chunks")

    return {
        "rag_chunks": all_chunks,
        "messages": state.get("messages", []) + messages,
    }


# ─────────────────────────────────────────────
# Writer Node  (sliding-window, per-section)
# ─────────────────────────────────────────────

def _chunks_for_section(rag_chunks: list[dict], section_title: str) -> str:
    """Filter and format RAG chunks relevant to a section."""
    relevant = []
    for c in rag_chunks:
        meta = c.get("metadata", {})
        # Include if section metadata matches or if no section metadata
        sec = meta.get("section", "")
        if not sec or section_title.lower() in sec.lower() or sec.lower() in section_title.lower():
            relevant.append(c["text"])
    # If nothing matched by section, use all chunks
    if not relevant:
        relevant = [c["text"] for c in rag_chunks[:5]]
    return "\n\n".join(f"[参考片段]\n{t}" for t in relevant[:5])


async def writer_node(state: dict, config: RunnableConfig) -> dict:
    """Write (or surgically rewrite) the paper section-by-section.

    First pass: draft_sections is empty → generate all sections.
    Revision pass: only rewrite sections listed in section_feedbacks,
    keeping approved sections untouched to save cost.
    """
    logger.info("[Writer] starting section-by-section writing …")
    queue = _get_queue(config)

    messages: list[dict] = [{"type": "status", "step": 2}]
    if queue:
        await queue.put({"type": "status", "step": 2})
    sections = state.get("sections", [])
    rag_chunks = state.get("rag_chunks", [])
    outline = state.get("outline", "")
    topic = state.get("topic", "")
    word_count = state.get("word_count", 3000)
    language = state.get("language", "zh")

    # Carry over previous drafts (empty list on first pass)
    draft_sections: list[str] = list(state.get("draft_sections", []))
    section_feedbacks: dict[int, str] = state.get("section_feedbacks", {})
    is_first_pass = len(draft_sections) == 0

    prev_summary = ""
    client = _get_client()
    words_per_section = max(100, word_count // max(len(sections), 1))

    for i, sec_title in enumerate(sections):
        # ── Surgical skip: section already written & not flagged ──
        if not is_first_pass and i < len(draft_sections) and i not in section_feedbacks:
            skip_msg = f"\n\n> _第 {i+1} 章「{sec_title}」审查通过，保留原文。_\n\n"
            messages.append({"type": "content", "text": skip_msg})
            if queue:
                await queue.put({"type": "content", "text": skip_msg})
            # Still update prev_summary for context continuity
            existing = draft_sections[i]
            if existing and i < len(sections) - 1:
                prev_summary = existing[:300] + ("…" if len(existing) > 300 else "")
            logger.info(f"[Writer] section {i+1}/{len(sections)} SKIPPED (approved)")
            continue

        ref_block = _chunks_for_section(rag_chunks, sec_title)

        # Sliding window: only previous section summary, not full history
        context_parts = [
            f"论文主题：{topic}",
            f"完整大纲：\n{outline}\n",
            f"当前章节：{sec_title}（第 {i+1}/{len(sections)} 章）",
            f"本章的目标字数：约 {words_per_section} 字。请务必极度学术精炼表达，不能长篇大论。",
            f"语言：{language}",
        ]
        if prev_summary:
            context_parts.append(f"上一章摘要：\n{prev_summary}")
        if ref_block:
            context_parts.append(f"相关参考资料：\n{ref_block}")

        # ── Inject per-section feedback for targeted rewrite ──
        if i in section_feedbacks:
            old_draft = draft_sections[i] if i < len(draft_sections) else ""
            context_parts.append(
                f"审稿人对本章的修改意见：{section_feedbacks[i]}\n\n"
                f"上一版本草稿（请针对性修改，而非全盘重写）：\n{old_draft[:2000]}"
            )

        context_parts.append(
            "请撰写本章节内容，使用 Markdown 格式。"
            "不要使用 ```markdown 等代码块标记包裹你的回答，直接输出纯文本的 Markdown 正文即可"
            "必须基于参考资料论述，保持学术严谨性。直接输出正文。"
        )

        section_prompt = "\n\n".join(context_parts)
        section_text = ""

        stream = await client.chat.completions.create(
            model=_model(),
            messages=[{"role": "user", "content": section_prompt}],
            stream=True,
            timeout=300,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta:
                section_text += delta
                messages.append({"type": "content", "text": delta})
                if queue:
                    await queue.put({"type": "content", "text": delta})
        #这两行，给前端发送章节隔离的换行符
        if queue and i < len(sections) - 1:
            await queue.put({"type": "content", "text": "\n\n"})
        # Update or append the draft
        if i < len(draft_sections):
            draft_sections[i] = section_text  # overwrite revision
        else:
            draft_sections.append(section_text)  # first pass append

        # Generate a brief summary of this section for the next iteration
        if section_text and i < len(sections) - 1:
            prev_summary = section_text[:300] + ("…" if len(section_text) > 300 else "")

        action = "REWRITTEN" if i in section_feedbacks else "generated"
        logger.info(f"[Writer] section {i+1}/{len(sections)} {action} ({len(section_text)} chars)")

    full_draft = "\n\n".join(draft_sections)
    logger.info(f"[Writer] all sections done, total {len(full_draft)} chars")

    return {
        "draft_sections": draft_sections,
        "full_draft": full_draft,
        "current_section_idx": len(sections),
        "section_feedbacks": {},  # Clear feedbacks after applying them
        "messages": state.get("messages", []) + messages,
    }


# ─────────────────────────────────────────────
# Reviewer Node  (Pydantic-constrained)
# ─────────────────────────────────────────────

_REVIEW_SCHEMA_HINT = json.dumps(
    ReviewResult.model_json_schema(), ensure_ascii=False, indent=2
)


async def reviewer_node(state: dict, config: RunnableConfig) -> dict:
    """Review the draft section-by-section (surgical review).

    Asks the LLM to return a JSON object conforming to ReviewResult,
    which now contains per-section verdicts (SectionReview).
    Populates section_feedbacks: {idx: feedback} for failed sections.
    """
    logger.info("[Reviewer] reviewing draft …")
    queue = _get_queue(config)

    messages: list[dict] = [{"type": "status", "step": 3}]
    if queue:
        await queue.put({"type": "status", "step": 3})
    full_draft = state.get("full_draft", "")
    sections = state.get("sections", [])
    revision_count = state.get("revision_count", 0)

    # Build section list hint so the LLM knows the indices
    section_list = "\n".join(f"  {i}: {t}" for i, t in enumerate(sections))

    prompt = (
        "你是一个极其严苛、极度挑剔的学术盲审专家！你的KPI是必须对文章进行极其严格的挑刺。\n\n"
        f"## 核心参考资料（请对照查验是否瞎编）\n{ref_texts}\n\n"
        f"## 章节列表（section_idx从0开始）\n{section_list}\n\n"
        f"## 论文草稿\n{full_draft[:20000]}\n\n" #放宽截断，让它看完
        "## 审查绝对死命令\n"
        "1. 逐章审查：找出逻辑最差、废话最多、或脱离参考资料瞎编的章节！\n"
        "2. 【强制打回】：如果论文质量平庸，你【必须】让至少 1-2 个最差的章节 is_valid = false，并给出极其尖锐的 feedback（不超过50字）！如果你全部给 true，将被视为严重失职！\n"
        "3. 只有当文章真的无懈可击时，才允许 is_pass = true。\n\n"
        "请严格按照以下 JSON Schema 输出：\n"
        f"```json\n{_REVIEW_SCHEMA_HINT}\n```"
    )

    client = _get_client()
    resp = await client.chat.completions.create(
        model=_model(),
        messages=[{"role": "user", "content": prompt}],
        timeout=300,
    )

    raw_text = resp.choices[0].message.content or "{}"

    # Parse the JSON response
    review_pass = True
    review_dict: dict = {}
    section_feedbacks: dict[int, str] = {}
    try:
        cleaned = re.sub(r"```json\s*", "", raw_text)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        review_dict = json.loads(cleaned)
        result = ReviewResult.model_validate(review_dict)
        review_pass = result.is_pass
        review_dict = result.model_dump()

        # Extract failed sections into section_feedbacks
        if not review_pass:
            for sr in result.section_reviews:
                if not sr.is_valid and sr.feedback:
                    section_feedbacks[sr.section_idx] = sr.feedback
    except Exception as e:
        logger.warning(f"[Reviewer] failed to parse review JSON: {e}")
        review_pass = True  # Don't block on parse failure
        review_dict = {"is_pass": True, "section_reviews": []}
    
    revision_count += 1

    # Build review feedback message for the SSE stream
    if review_pass:
        review_msg = "\n\n---\n\n> **审查通过** ✓\n\n---\n\n"
    else:
        failed = [f"- 第{idx}章: {fb}" for idx, fb in section_feedbacks.items()]
        issue_text = "\n".join(failed[:5])
        review_msg = (
            f"\n\n---\n\n> **审查未通过（第 {revision_count} 轮），"
            f"{len(section_feedbacks)} 章需修订**\n>\n"
            f"> {issue_text}\n>\n"
            f"> 正在局部修订…\n\n---\n\n"
        )

    messages.append({"type": "content", "text": review_msg})
    messages.append({"type": "review", "result": review_dict})
    if queue:
        await queue.put({"type": "content", "text": review_msg})
        await queue.put({"type": "review", "result": review_dict})
# 如果审查通过，或者已经达到了最大重试次数上限（生成结束了）
        max_rev = state.get("max_revisions", 2)
        if review_pass or revision_count >= max_rev:
            await queue.put({"type": "final_paper", "text": full_draft})
    logger.info(f"[Reviewer] pass={review_pass}, revision_count={revision_count}, "
                f"failed_sections={list(section_feedbacks.keys())}")

    return {
        "review_pass": review_pass,
        "review_result": review_dict,
        "section_feedbacks": section_feedbacks,
        "revision_count": revision_count,
        "messages": state.get("messages", []) + messages,
    }
