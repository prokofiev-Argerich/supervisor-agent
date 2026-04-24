"""Main FastAPI application."""

import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from supervisor_agent.agent import SupervisorAgent
from supervisor_agent.config import settings
from supervisor_agent.models import AgentRequest, AgentResponse
from supervisor_agent.schemas.paper import PaperRequest

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="An async supervisor agent framework",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent
agent = SupervisorAgent(name="supervisor")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to the Supervisor Agent API",
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/agent/process", response_model=AgentResponse)
async def process_request(request: AgentRequest) -> AgentResponse:
    """Process a request through the agent.
    
    Args:
        request: The agent request
        
    Returns:
        Agent response
    """
    logger.info(f"Received request: {request.query}")
    response = await agent.process(request)
    return response


@app.post("/api/stream_generate")
async def stream_generate(request: PaperRequest):
    """Stream paper generation via SSE.

    Accepts PaperRequest, returns text/event-stream with JSON lines:
      {"type":"status","step":0-3}  — agent stage indicator
      {"type":"content","text":"…"} — markdown chunk
      {"type":"done"}               — generation finished
    """
    logger.info(f"stream_generate: topic={request.topic}, words={request.word_count}")
    return StreamingResponse(
        agent.stream_paper(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
