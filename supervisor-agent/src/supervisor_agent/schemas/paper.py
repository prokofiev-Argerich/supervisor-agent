from pydantic import BaseModel, Field
from typing import List, Optional


class PaperRequest(BaseModel):
    """用户论文写作请求模型"""
    topic: str = Field(..., description="论文主题", min_length=1, max_length=500)
    word_count: int = Field(..., description="目标字数", gt=0, le=100000)
    keywords: Optional[List[str]] = Field(default=None, description="关键词列表")
    language: str = Field(default="zh", description="目标语言，默认中文")

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
