from pydantic import BaseModel, Field
from typing import List, Optional


class PaperRequest(BaseModel):
    """用户论文写作请求模型"""
    topic: str = Field(..., description="论文主题", min_length=1, max_length=1000)
    word_count: int = Field(..., description="目标字数", gt=0, le=100000)
    keywords: Optional[List[str]] = Field(default=None, description="关键词列表")
    language: str = Field(default="zh", description="目标语言，默认中文")
    max_revisions: int = Field(default=2, description="最大允许的审稿打回重写次数")
    class Config:
        json_schema_extra = {
            "example": {
                "topic": "深度学习在自然语言处理中的应用",
                "word_count": 5000,
                "keywords": ["深度学习", "NLP", "神经网络"],
                "language": "zh"
            }
        }


class OutlineItem(BaseModel):
    """大纲项目"""
    title: str = Field(..., description="章节标题")
    content: str = Field(..., description="章节内容描述")
    subsections: Optional[List["OutlineItem"]] = Field(default=None, description="子章节")


class OutlineSchema(BaseModel):
    """论文大纲结构模型"""
    title: str = Field(..., description="论文标题")
    abstract: str = Field(..., description="论文摘要")
    outline: List[OutlineItem] = Field(..., description="论文大纲")
    estimated_word_count: int = Field(..., description="预估字数")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "深度学习在NLP中的应用",
                "abstract": "本文综述了深度学习技术在自然语言处理领域的应用...",
                "outline": [
                    {
                        "title": "1. 引言",
                        "content": "介绍深度学习和NLP的基本概念",
                        "subsections": None
                    }
                ],
                "estimated_word_count": 5000
            }
        }


OutlineItem.model_rebuild()


class ConfirmRequest(BaseModel):
    """用户确认大纲后，携带原始请求 + 大纲信息发起全文生成"""
    topic: str = Field(..., description="论文主题")
    word_count: int = Field(..., description="目标字数", gt=0, le=100000)
    keywords: Optional[List[str]] = Field(default=None, description="关键词列表")
    language: str = Field(default="zh", description="目标语言")
    outline: str = Field(..., description="已确认的大纲文本")
    sections: List[str] = Field(..., description="章节标题列表")
    max_revisions: int = Field(default=2, description="最大允许的审稿打回重写次数")

class ReviseRequest(BaseModel):
    """用户对大纲提出修改意见"""
    topic: str = Field(..., description="论文主题")
    word_count: int = Field(..., description="目标字数", gt=0, le=100000)
    keywords: Optional[List[str]] = Field(default=None, description="关键词列表")
    language: str = Field(default="zh", description="目标语言")
    outline: str = Field(..., description="当前大纲文本")
    sections: List[str] = Field(..., description="当前章节标题列表")
    feedback: str = Field(..., description="用户修改意见", min_length=1, max_length=2000)
    max_revisions: int = Field(default=2, description="最大允许的审稿打回重写次数")
