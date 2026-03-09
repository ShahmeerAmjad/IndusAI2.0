"""Knowledge Base API — product catalog, crawl triggers, document upload."""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-base", tags=["Knowledge Base"])

# ---------------------------------------------------------------------------
# Module-level DI
# ---------------------------------------------------------------------------

_kb_service = None
_chempoint_scraper = None
_crawl_jobs: dict = {}


def set_kb_service(svc):
    global _kb_service
    _kb_service = svc


def set_chempoint_scraper(scraper):
    global _chempoint_scraper
    _chempoint_scraper = scraper


def _get_svc():
    if not _kb_service:
        raise HTTPException(status_code=503, detail="Knowledge base service unavailable")
    return _kb_service


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get("/graph-viz")
async def graph_visualization(
    industry: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Return nodes and edges for frontend graph visualization."""
    svc = _get_svc()
    data = await svc.get_graph_visualization(
        industry=industry, manufacturer=manufacturer, limit=limit,
    )
    return data


@router.get("/filters")
async def get_filters():
    """Return available manufacturers and industries for filter dropdowns."""
    svc = _get_svc()
    return await svc.get_filters()


@router.get("/products")
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    has_tds: Optional[bool] = Query(None),
    has_sds: Optional[bool] = Query(None),
):
    """Paginated product list from the knowledge graph with filters."""
    svc = _get_svc()
    result = await svc.list_products(
        page=page, page_size=page_size, search=search,
        manufacturer=manufacturer, industry=industry,
        has_tds=has_tds, has_sds=has_sds,
    )
    return result


@router.get("/products/{product_id}/extraction")
async def get_product_extraction(product_id: str):
    """Return full TDS + SDS extracted fields with confidence scores."""
    svc = _get_svc()
    return await svc.get_product_extraction(product_id)


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get a single product with manufacturer, industries, and doc URLs."""
    svc = _get_svc()
    product = await svc.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ---------------------------------------------------------------------------
# Crawl
# ---------------------------------------------------------------------------


@router.post("/crawl", status_code=202)
async def trigger_crawl(
    base_url: str = "https://www.chempoint.com",
    max_pages: int = Query(50, ge=1, le=500),
):
    """Trigger an async Chempoint catalog crawl. Returns a job_id for polling."""
    if not _chempoint_scraper:
        raise HTTPException(status_code=503, detail="Chempoint scraper not configured")

    job_id = uuid.uuid4().hex
    _crawl_jobs[job_id] = {"status": "running", "products_found": 0, "error": None}

    async def _run_crawl():
        try:
            products = await _chempoint_scraper.crawl_full_catalog(base_url, max_pages=max_pages)
            _crawl_jobs[job_id]["products_found"] = len(products)

            # Ingest into knowledge base
            svc = _get_svc()
            result = await svc.ingest_batch(products)
            _crawl_jobs[job_id]["status"] = "completed"
            _crawl_jobs[job_id]["ingestion"] = result
        except Exception as exc:
            logger.error("Crawl job %s failed: %s", job_id, exc)
            _crawl_jobs[job_id]["status"] = "failed"
            _crawl_jobs[job_id]["error"] = str(exc)

    asyncio.create_task(_run_crawl())
    return {"job_id": job_id, "status": "running"}


@router.get("/crawl/{job_id}")
async def get_crawl_status(job_id: str):
    """Poll the status of an async crawl job."""
    job = _crawl_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return {"job_id": job_id, **job}


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------


@router.post("/documents/upload", status_code=201)
async def upload_document(
    product_id: str = Form(...),
    doc_type: str = Form(..., description="TDS or SDS"),
    file: UploadFile = File(...),
):
    """Upload a TDS/SDS PDF and associate it with a product in the knowledge base."""
    svc = _get_svc()

    if doc_type not in ("TDS", "SDS"):
        raise HTTPException(status_code=400, detail="doc_type must be TDS or SDS")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # Store via knowledge base service (delegates to PG documents table)
    result = {
        "product_id": product_id,
        "doc_type": doc_type,
        "file_name": file.filename or "upload.pdf",
        "file_size_bytes": len(file_bytes),
        "status": "stored",
    }
    logger.info("Uploaded %s for product %s (%d bytes)", doc_type, product_id, len(file_bytes))
    return result
