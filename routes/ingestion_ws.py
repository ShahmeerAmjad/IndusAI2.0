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
_cancelled: set[str] = set()


def set_ingestion_pipeline(pipeline):
    global _pipeline
    _pipeline = pipeline


def is_cancelled(job_id: str) -> bool:
    return job_id in _cancelled


class StartIngestionRequest(BaseModel):
    url: str
    max_products: int = 0  # 0 = unlimited


class StartBatchRequest(BaseModel):
    industry_urls: list[str]
    max_products: int = 50


async def _broadcast(job_id: str, event: dict):
    """Store event and broadcast to all WebSocket subscribers."""
    if job_id in _job_events:
        _job_events[job_id].append(event)

    for ws in _job_subscribers.get(job_id, []):
        try:
            await ws.send_text(json.dumps(event))
        except Exception:
            pass


async def _run_single(job_id: str, url: str, max_products: int = 0):
    """Run single-URL ingestion with proper error broadcasting."""
    try:
        cancel_fn = lambda: is_cancelled(job_id)
        broadcast_fn = lambda event: asyncio.ensure_future(_broadcast(job_id, event))
        result = await _pipeline.seed_from_url(
            url, on_progress=broadcast_fn, cancel_check=cancel_fn,
            max_products=max_products,
        )
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = result
        await _broadcast(job_id, {"stage": "done", "result": result})
    except Exception as exc:
        logger.error("Ingestion job %s failed: %s", job_id, exc)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["result"] = {"error": str(exc)}
        await _broadcast(job_id, {"stage": "error", "detail": str(exc)})


async def _run_batch(job_id: str, industry_urls: list[str], max_products: int):
    """Run batch ingestion with proper error broadcasting."""
    try:
        cancel_fn = lambda: is_cancelled(job_id)
        broadcast_fn = lambda event: asyncio.ensure_future(_broadcast(job_id, event))
        stats = await _pipeline.seed_from_industries(
            industry_urls, on_progress=broadcast_fn,
            max_products=max_products, cancel_check=cancel_fn,
        )
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = stats
        await _broadcast(job_id, {"stage": "done", "detail": str(stats)})
    except Exception as exc:
        logger.error("Batch ingestion %s failed: %s", job_id, exc)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["result"] = {"error": str(exc)}
        await _broadcast(job_id, {"stage": "error", "detail": str(exc)})


@router.post("/start", status_code=202)
async def start_ingestion(req: StartIngestionRequest):
    """Start single-URL ingestion. Returns job_id for WebSocket progress."""
    if not _pipeline:
        raise HTTPException(503, "Ingestion pipeline not configured")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"job_id": job_id, "status": "running", "events": [], "result": None}
    _job_events[job_id] = []
    _job_subscribers[job_id] = []

    asyncio.create_task(_run_single(job_id, req.url, req.max_products))
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

    asyncio.create_task(_run_batch(job_id, req.industry_urls, req.max_products))
    return {"job_id": job_id, "status": "running"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    _cancelled.add(job_id)
    _jobs[job_id]["status"] = "cancelled"
    await _broadcast(job_id, {"stage": "cancelled", "detail": "Job cancelled by user"})
    return {"job_id": job_id, "status": "cancelled"}


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
