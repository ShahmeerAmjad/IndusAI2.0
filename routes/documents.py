"""Document API — TDS/SDS upload, download, search, listing."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# Module-level DI
_document_service = None


def set_document_services(document_service=None):
    global _document_service
    _document_service = document_service


def _require_service():
    if not _document_service:
        raise HTTPException(status_code=503, detail="Document service unavailable")
    return _document_service


# ── Endpoints ──


@router.get("/count")
async def get_document_count():
    """Return total document count and breakdown by type (TDS/SDS)."""
    svc = _require_service()
    return await svc.count_documents()


@router.get("/product/{product_id}")
async def list_documents_for_product(product_id: str):
    """List current TDS/SDS documents for a product."""
    svc = _require_service()
    docs = await svc.get_documents_for_product(product_id)
    return docs


@router.post("/upload", status_code=201)
async def upload_document(
    product_id: str = Form(...),
    doc_type: str = Form(..., description="TDS or SDS"),
    file: UploadFile = File(...),
):
    """Upload a TDS/SDS PDF document for a product."""
    svc = _require_service()

    if doc_type not in ("TDS", "SDS"):
        raise HTTPException(status_code=400, detail="doc_type must be TDS or SDS")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    result = await svc.store_document(
        product_id=product_id,
        doc_type=doc_type,
        file_bytes=file_bytes,
        file_name=file.filename or "upload.pdf",
    )
    return result


@router.get("/{doc_id}/download")
async def download_document(doc_id: str):
    """Download a document file by its ID."""
    svc = _require_service()

    doc = await svc.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    content_format = doc.get("content_format", "pdf")
    if content_format == "markdown":
        media_type = "text/markdown"
        filename = doc.get("file_name", file_path.name).rsplit(".", 1)[0] + ".md"
    else:
        media_type = "application/pdf"
        filename = doc.get("file_name", file_path.name)

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )


@router.get("/{doc_id}/info")
async def get_document_info(doc_id: str):
    """Get document metadata including content format (pdf vs markdown)."""
    svc = _require_service()
    doc = await svc.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/search")
async def search_documents(
    q: str = Query(..., min_length=1, description="Search keyword"),
    doc_type: Optional[str] = Query(None, description="TDS or SDS"),
    limit: int = Query(20, ge=1, le=100),
):
    """Search documents by keyword, product name, or CAS number."""
    svc = _require_service()
    results = await svc.search_documents(q, doc_type=doc_type, limit=limit)
    return results
