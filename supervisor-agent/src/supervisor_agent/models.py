"""Pydantic models for the supervisor agent."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A message in the agent conversation."""

    role: str = Field(..., description="Role of the message sender (user/assistant)")
    content: str = Field(..., description="Message content")


class AgentRequest(BaseModel):
    """Request to the agent."""

    query: str = Field(..., description="User query or task")
    conversation_history: Optional[list[Message]] = Field(
        default_factory=list, description="Conversation history"
    )
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class AgentResponse(BaseModel):
    """Response from the agent."""

    response: str = Field(..., description="Agent response")
    status: str = Field(default="success", description="Status of the response")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict, description="Response metadata")
