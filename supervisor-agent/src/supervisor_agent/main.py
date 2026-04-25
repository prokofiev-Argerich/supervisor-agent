"""Main FastAPI application."""
from dotenv import load_dotenv
import os

# 强制从项目根目录读取 .env 文件
load_dotenv() 

# 打印出来验证一下（确认后可以删掉）
print("加载的 API URL 是:", os.getenv("OPENAI_BASE_URL"))

import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from supervisor_agent.agent import SupervisorAgent
from supervisor_agent.config import settings
from supervisor_agent.models import AgentRequest, AgentResponse
from supervisor_agent.schemas.paper import PaperRequest, ConfirmRequest, ReviseRequest

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


@app.post("/api/generate_outline")
async def generate_outline(request: PaperRequest):
    """Phase 1: generate outline only, stream SSE.

    Returns events:
      {"type":"status","message":"…"}   — progress
      {"type":"content","text":"…"}     — outline markdown chunk
      {"type":"outline_done","outline":"…","sections":[…]} — final
      {"type":"done"}
    """
    logger.info(f"generate_outline: topic={request.topic}")
    return StreamingResponse(
        agent.stream_outline(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/revise_outline")
async def revise_outline(request: ReviseRequest):
    """Phase 1.5: revise outline based on user feedback, stream SSE.

    Returns events:
      {"type":"content","text":"…"}     — revised outline markdown chunk
      {"type":"outline_done","outline":"…","sections":[…]} — final
      {"type":"done"}
    """
    logger.info(f"revise_outline: topic={request.topic}, feedback={request.feedback[:50]}")
    paper_req = PaperRequest(
        topic=request.topic,
        word_count=request.word_count,
        keywords=request.keywords,
        language=request.language,
    )
    return StreamingResponse(
        agent.stream_revise_outline(
            paper_req, request.outline, request.sections, request.feedback,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/confirm_and_write")
async def confirm_and_write(request: ConfirmRequest):
    """Phase 2: user confirmed outline, run full pipeline, stream SSE.

    Returns events:
      {"type":"status","message":"…"}   — progress
      {"type":"content","text":"…"}     — paper markdown chunk
      {"type":"done"}
    """
    logger.info(f"confirm_and_write: topic={request.topic}")
    paper_req = PaperRequest(
        topic=request.topic,
        word_count=request.word_count,
        keywords=request.keywords,
        language=request.language,
    )
    return StreamingResponse(
        agent.stream_paper(paper_req, request.outline, request.sections),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
