"""Tests for routes/ingestion_ws — ingestion endpoints and broadcast logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from routes.ingestion_ws import (
    router, set_ingestion_pipeline,
    _jobs, _job_events, _job_subscribers, _broadcast, _cancelled,
)


def _make_test_app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up module-level state between tests."""
    yield
    _jobs.clear()
    _job_events.clear()
    _job_subscribers.clear()
    _cancelled.clear()
    set_ingestion_pipeline(None)


class TestBroadcast:
    """Test the _broadcast helper."""

    def test_broadcast_stores_event(self):
        job_id = "test-job"
        _job_events[job_id] = []
        _job_subscribers[job_id] = []

        _broadcast(job_id, {"stage": "processing", "product": "EP-200"})

        assert len(_job_events[job_id]) == 1
        assert _job_events[job_id][0]["stage"] == "processing"

    def test_broadcast_multiple_events(self):
        job_id = "test-job"
        _job_events[job_id] = []
        _job_subscribers[job_id] = []

        _broadcast(job_id, {"stage": "processing", "current": 1})
        _broadcast(job_id, {"stage": "processing", "current": 2})
        _broadcast(job_id, {"stage": "done", "result": {}})

        assert len(_job_events[job_id]) == 3
        assert _job_events[job_id][-1]["stage"] == "done"

    def test_broadcast_unknown_job_no_crash(self):
        """Broadcasting to an unknown job should not crash."""
        _broadcast("nonexistent", {"stage": "test"})
        assert "nonexistent" not in _job_events


class TestStartIngestion:
    """Test the start ingestion endpoint."""

    @pytest.mark.asyncio
    async def test_start_ingestion_returns_job_id(self):
        mock_pipeline = MagicMock()
        mock_pipeline.seed_from_url = AsyncMock(return_value={"products": 5})
        set_ingestion_pipeline(mock_pipeline)

        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/ingestion/start",
                                 json={"url": "https://example.com/products"})
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_start_ingestion_no_pipeline_503(self):
        set_ingestion_pipeline(None)
        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/ingestion/start",
                                 json={"url": "https://example.com"})
        assert resp.status_code == 503


class TestStartBatchIngestion:
    """Test the batch ingestion endpoint."""

    @pytest.mark.asyncio
    async def test_start_batch_returns_job_id(self):
        mock_pipeline = MagicMock()
        mock_pipeline.seed_from_industries = AsyncMock(return_value={"products": 10})
        set_ingestion_pipeline(mock_pipeline)

        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/ingestion/start-batch",
                                 json={"industry_urls": ["https://example.com/ind1"],
                                        "max_products": 25})
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_start_batch_no_pipeline_503(self):
        set_ingestion_pipeline(None)
        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/ingestion/start-batch",
                                 json={"industry_urls": ["https://example.com"]})
        assert resp.status_code == 503


class TestGetJobStatus:
    """Test job status polling endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_status_found(self):
        _jobs["j1"] = {"job_id": "j1", "status": "completed", "result": {"products": 3}}
        _job_events["j1"] = [
            {"stage": "processing", "current": 1},
            {"stage": "done", "result": {"products": 3}},
        ]

        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/ingestion/jobs/j1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert len(data["events"]) == 2

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self):
        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/ingestion/jobs/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_job_status_truncates_events(self):
        """Only last 20 events returned via polling."""
        _jobs["j2"] = {"job_id": "j2", "status": "running", "result": None}
        _job_events["j2"] = [{"stage": "processing", "i": i} for i in range(30)]

        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/ingestion/jobs/j2")
        data = resp.json()
        assert len(data["events"]) == 20


class TestCancelJob:
    """Test the cancel endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_job(self):
        set_ingestion_pipeline(MagicMock())
        _jobs["test-job-1"] = {"job_id": "test-job-1", "status": "running", "result": None}
        _job_events["test-job-1"] = []

        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/ingestion/jobs/test-job-1/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self):
        set_ingestion_pipeline(MagicMock())
        app = _make_test_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/ingestion/jobs/nonexistent/cancel")
        assert resp.status_code == 404


class TestBatchErrorBroadcast:
    """Test error broadcasting on batch failure."""

    @pytest.mark.asyncio
    async def test_batch_job_broadcasts_error_on_failure(self):
        """Batch job should broadcast an error event when pipeline raises."""
        import routes.ingestion_ws as mod

        mock_pipeline = MagicMock()
        mock_pipeline.seed_from_industries = AsyncMock(side_effect=Exception("Firecrawl down"))
        mod._pipeline = mock_pipeline

        job_id = "fail-job"
        _jobs[job_id] = {"job_id": job_id, "status": "running", "result": None}
        _job_events[job_id] = []

        await mod._run_batch(job_id, ["https://ex.com/ind1"], 50)

        assert _jobs[job_id]["status"] == "failed"
        error_events = [e for e in _job_events[job_id] if e.get("stage") == "error"]
        assert len(error_events) >= 1
