"""Main FastAPI application."""
from dotenv import load_dotenv
import os

# 强制从项目根目录读取 .env 文件
load_dotenv()

import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from supervisor_agent.agent import SupervisorAgent
from supervisor_agent.artifacts import (
    generate_task_id,
    get_artifact_path,
    list_artifacts,
    load_artifact_text,
    save_artifact,
)
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
      {"type":"final_paper","text":"…","task_id":"…","download_url":"…"}
      {"type":"done"}
    """
    task_id = generate_task_id()
    logger.info(f"confirm_and_write: topic={request.topic}, task_id={task_id}")

    paper_req = PaperRequest(
        topic=request.topic,
        word_count=request.word_count,
        keywords=request.keywords,
        language=request.language,
    )

    metadata = {
        "topic": request.topic,
        "word_count": request.word_count,
        "keywords": request.keywords or [],
        "language": request.language,
        "max_revisions": request.max_revisions,
    }

    async def _wrapped_stream():
        """Wrap agent stream to intercept final_paper and persist artifact."""
        async for raw_line in agent.stream_paper(
            paper_req, request.outline, request.sections
        ):
            if raw_line.startswith("data: "):
                payload = raw_line[6:].strip()
                if payload == "[DONE]":
                    yield raw_line
                    continue
                try:
                    data = json.loads(payload)
                    if data.get("type") == "final_paper":
                        # Persist artifact off the event loop
                        await asyncio.to_thread(
                            save_artifact,
                            task_id,
                            data["text"],
                            metadata,
                        )
                        # Enrich event with task_id and download URL
                        data["task_id"] = task_id
                        data["download_url"] = f"/api/artifacts/{task_id}/download"
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                        continue
                except (json.JSONDecodeError, KeyError):
                    pass
            yield raw_line

    return StreamingResponse(
        _wrapped_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/artifacts/{task_id}/download")
async def download_artifact(task_id: str):
    """Download the final paper Markdown for a given task."""
    try:
        path = get_artifact_path(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(
        path,
        media_type="text/markdown; charset=utf-8",
        filename="final_paper.md",
    )


@app.get("/api/artifacts/{task_id}")
async def get_artifact_metadata(task_id: str):
    """Return metadata.json for a given task."""
    from supervisor_agent.artifacts import load_metadata

    try:
        meta = load_metadata(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return meta


@app.get("/api/artifacts")
async def list_saved_artifacts():
    """List all saved artifacts, sorted by created_at desc."""
    return list_artifacts()


@app.get("/api/artifacts/{task_id}/content")
async def get_artifact_content(task_id: str):
    """Return final paper text for a given task."""
    try:
        text = load_artifact_text(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"task_id": task_id, "text": text}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
