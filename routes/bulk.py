# =======================
# Bulk Import Routes — CSV upload & templates
# =======================

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
import io

from services.bulk_import_service import BulkImportService, MAX_FILE_SIZE

router = APIRouter(prefix="/api/v1/bulk", tags=["Bulk Import"])

_bulk_service: BulkImportService = None


def set_bulk_service(svc: BulkImportService):
    global _bulk_service
    _bulk_service = svc


def _get_svc() -> BulkImportService:
    if not _bulk_service:
        raise HTTPException(status_code=503, detail="Bulk import service unavailable")
    return _bulk_service


@router.post("/products")
async def bulk_import_products(
    file: UploadFile = File(...),
    dry_run: bool = Query(False),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")

    svc = _get_svc()
    result = await svc.import_products(contents, dry_run=dry_run)
    return result


@router.post("/inventory")
async def bulk_import_inventory(
    file: UploadFile = File(...),
    dry_run: bool = Query(False),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")

    svc = _get_svc()
    result = await svc.import_inventory(contents, dry_run=dry_run)
    return result


@router.get("/templates/products")
async def download_product_template():
    data = BulkImportService.product_template()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="products_template.csv"'},
    )


@router.get("/templates/inventory")
async def download_inventory_template():
    data = BulkImportService.inventory_template()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="inventory_template.csv"'},
    )
