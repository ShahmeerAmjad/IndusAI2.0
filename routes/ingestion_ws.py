"""WebSocket-enabled ingestion endpoints with real-time progress."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])

_pipeline = None
_jobs: dict[str, dict] = {}
_job_events: dict[str, list[dict]] = {}
_job_subscribers: dict[str, list[WebSocket]] = {}


def set_ingestion_pipeline(pipeline):
    global _pipeline
    _pipeline = pipeline


class StartIngestionRequest(BaseModel):
    url: str


class StartBatchRequest(BaseModel):
    industry_urls: list[str]
    max_products: int = 50


@router.post("/start", status_code=202)
async def start_ingestion(req: StartIngestionRequest):
    """Start single-URL ingestion. Returns job_id for WebSocket progress."""
    if not _pipeline:
        raise HTTPException(503, "Ingestion pipeline not configured")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"job_id": job_id, "status": "running", "events": [], "result": None}
    _job_events[job_id] = []
    _job_subscribers[job_id] = []

    async def _run():
        try:
            result = await _pipeline.seed_from_url(
                req.url, on_progress=lambda e: _broadcast(job_id, e),
            )
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = result
            _broadcast(job_id, {"stage": "done", "result": result})
        except Exception as exc:
            logger.error("Ingestion job %s failed: %s", job_id, exc)
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)
            _broadcast(job_id, {"stage": "error", "detail": str(exc)})

    asyncio.create_task(_run())
    return {"job_id": job_id, "status": "running"}


@router.post("/start-batch", status_code=202)
async def start_batch_ingestion(req: StartBatchRequest):
    """Start batch industry ingestion. Returns job_id."""
    if not _pipeline:
        raise HTTPException(503, "Ingestion pipeline not configured")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"job_id": job_id, "status": "running", "events": [], "result": None}
    _job_events[job_id] = []
    _job_subscribers[job_id] = []

    async def _run():
        try:
            result = await _pipeline.seed_from_industries(
                req.industry_urls,
                on_progress=lambda e: _broadcast(job_id, e),
            )
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = result
            _broadcast(job_id, {"stage": "done", "result": result})
        except Exception as exc:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(exc)

    asyncio.create_task(_run())
    return {"job_id": job_id, "status": "running"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Poll job status (fallback if WebSocket not available)."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {**job, "events": _job_events.get(job_id, [])[-20:]}


@router.websocket("/ws/{job_id}")
async def ws_progress(websocket: WebSocket, job_id: str):
    """WebSocket for real-time ingestion progress."""
    await websocket.accept()

    if job_id not in _job_subscribers:
        _job_subscribers[job_id] = []
    _job_subscribers[job_id].append(websocket)

    # Send any missed events
    for event in _job_events.get(job_id, []):
        await websocket.send_text(json.dumps(event))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _job_subscribers.get(job_id, []):
            _job_subscribers[job_id].remove(websocket)


def _broadcast(job_id: str, event: dict):
    """Store event and broadcast to all WebSocket subscribers."""
    if job_id in _job_events:
        _job_events[job_id].append(event)

    for ws in _job_subscribers.get(job_id, []):
        try:
            asyncio.create_task(ws.send_text(json.dumps(event)))
        except Exception:
            pass
