"""Shared state definition for the LangGraph paper-generation pipeline."""

from __future__ import annotations

from typing import TypedDict


class RagChunk(TypedDict):
    """A single RAG retrieval result with metadata."""
    text: str
    metadata: dict  # {"source": "file.tex", "section": "Introduction", ...}


class PaperState(TypedDict, total=False):
    """State that flows through every node in the graph.

    Fields marked total=False are optional — nodes populate them progressively.
    """
    # ── Input (set once at graph entry) ──
    topic: str
    word_count: int
    max_revisions: int
    keywords: list[str]
    language: str

    # ── Planner output ──
    outline: str                    # Markdown outline from Planner
    sections: list[str]             # Section titles parsed from outline

    # ── Human-in-the-loop ──
    outline_approved: bool          # Set to True after user confirms
    feedback: str                   # User feedback for outline revision

    # ── Researcher output ──
    rag_chunks: list[RagChunk]      # Retrieved chunks with metadata

    # ── Writer output ──
    current_section_idx: int        # Which section is being written
    draft_sections: list[str]       # Per-section drafts
    full_draft: str                 # Concatenated final draft

    # ── Reviewer output ──
    review_pass: bool               # Whether the review passed
    review_result: dict             # Structured ReviewResult as dict
    revision_count: int             # Times the draft has been sent back (max 2)
    section_feedbacks: dict[int, str]  # 被打回章节的索引 → 修改意见

    # ── SSE message queue ──
    messages: list[dict]            # Accumulated SSE events for streaming
