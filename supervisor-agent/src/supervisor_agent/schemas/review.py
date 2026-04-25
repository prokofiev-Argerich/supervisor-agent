"""Pydantic models for the Reviewer node's structured output."""

from pydantic import BaseModel, Field


class SectionReview(BaseModel):
    """Per-section review result from the Reviewer."""
    section_idx: int = Field(..., description="章节索引（从 0 开始）")
    is_valid: bool = Field(..., description="该章节是否通过审查")
    feedback: str = Field(default="", description="不超过 50 字的修改意见")


class ReviewResult(BaseModel):
    """Structured output from the Reviewer node."""
    is_pass: bool = Field(..., description="审查是否整体通过")
    section_reviews: list[SectionReview] = Field(
        default_factory=list, description="逐章审查结果"
    )
