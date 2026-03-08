"""Test WebSocket ingestion progress streaming."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_test_app():
    from routes.ingestion_ws import router, set_ingestion_pipeline
    app = FastAPI()
    app.include_router(router)
    return app, set_ingestion_pipeline


def test_start_ingestion_returns_job_id():
    app, set_pipeline = _make_test_app()
    mock_pipeline = MagicMock()
    mock_pipeline.seed_from_url = AsyncMock(return_value={"products_created": 1})
    set_pipeline(mock_pipeline)

    client = TestClient(app)
    resp = client.post("/api/v1/ingestion/start", json={"url": "https://chempoint.com/products/test"})
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "running"


def test_start_batch_ingestion():
    app, set_pipeline = _make_test_app()
    mock_pipeline = MagicMock()
    mock_pipeline.seed_from_industries = AsyncMock(return_value={"products_created": 5})
    set_pipeline(mock_pipeline)

    client = TestClient(app)
    resp = client.post("/api/v1/ingestion/start-batch", json={
        "industry_urls": [
            "https://chempoint.com/industries/adhesives/all",
            "https://chempoint.com/industries/coatings/all",
        ],
        "max_products": 50,
    })
    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_get_job_status():
    app, set_pipeline = _make_test_app()
    set_pipeline(MagicMock())

    client = TestClient(app)
    with patch("routes.ingestion_ws.asyncio") as mock_asyncio:
        mock_asyncio.create_task = MagicMock()
        resp = client.post("/api/v1/ingestion/start", json={"url": "https://example.com"})
        job_id = resp.json()["job_id"]

    resp2 = client.get(f"/api/v1/ingestion/jobs/{job_id}")
    assert resp2.status_code == 200
    assert resp2.json()["job_id"] == job_id


def test_get_job_status_not_found():
    app, set_pipeline = _make_test_app()
    set_pipeline(MagicMock())

    client = TestClient(app)
    resp = client.get("/api/v1/ingestion/jobs/nonexistent")
    assert resp.status_code == 404
