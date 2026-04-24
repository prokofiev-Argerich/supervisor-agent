"""Tests for the supervisor agent."""

import pytest

from supervisor_agent.agent import SupervisorAgent
from supervisor_agent.models import AgentRequest


@pytest.fixture
def agent():
    """Create a test agent."""
    return SupervisorAgent(name="test_agent")


@pytest.mark.asyncio
async def test_agent_process(agent):
    """Test basic agent processing."""
    request = AgentRequest(query="What is 2+2?")
    response = await agent.process(request)
    
    assert response.status == "success"
    assert response.response is not None
    assert "Echo" in response.response


@pytest.mark.asyncio
async def test_agent_stream(agent):
    """Test agent streaming."""
    request = AgentRequest(query="Hello agent")
    chunks = []
    
    async for chunk in agent.stream(request):
        chunks.append(chunk)
    
    assert len(chunks) > 0
    assert chunks[-1]["type"] == "done"
