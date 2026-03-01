# =======================
# Report Routes — CSV, Excel, PDF downloads
# =======================

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from services.report_service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

_report_service: ReportService = None


def set_report_service(svc: ReportService):
    global _report_service
    _report_service = svc


def _get_svc() -> ReportService:
    if not _report_service:
        raise HTTPException(status_code=503, detail="Report service unavailable")
    return _report_service


_CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _streaming_response(data: bytes, filename: str, fmt: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type=_CONTENT_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/orders")
async def report_orders(format: str = Query("csv", pattern="^(csv|xlsx|pdf)$")):
    svc = _get_svc()
    rows = await svc._fetch_orders()
    if format == "csv":
        data = svc.generate_csv(rows)
    elif format == "xlsx":
        data = svc.generate_xlsx(rows, sheet_name="Orders")
    else:
        data = svc.generate_pdf(rows, title="Orders Report")
    return _streaming_response(data, f"orders.{format}", format)


@router.get("/inventory")
async def report_inventory(format: str = Query("csv", pattern="^(csv|xlsx|pdf)$")):
    svc = _get_svc()
    rows = await svc._fetch_inventory()
    if format == "csv":
        data = svc.generate_csv(rows)
    elif format == "xlsx":
        data = svc.generate_xlsx(rows, sheet_name="Inventory")
    else:
        data = svc.generate_pdf(rows, title="Inventory Report")
    return _streaming_response(data, f"inventory.{format}", format)


@router.get("/invoices")
async def report_invoices(format: str = Query("csv", pattern="^(csv|xlsx|pdf)$")):
    svc = _get_svc()
    rows = await svc._fetch_invoices()
    if format == "csv":
        data = svc.generate_csv(rows)
    elif format == "xlsx":
        data = svc.generate_xlsx(rows, sheet_name="Invoices")
    else:
        data = svc.generate_pdf(rows, title="Invoices Report")
    return _streaming_response(data, f"invoices.{format}", format)


@router.get("/sales")
async def report_sales(
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    period: str = Query("month", pattern="^(day|week|month)$"),
):
    svc = _get_svc()
    rows = await svc._fetch_sales(period)
    if format == "csv":
        data = svc.generate_csv(rows)
    elif format == "xlsx":
        data = svc.generate_xlsx(rows, sheet_name="Sales")
    else:
        data = svc.generate_pdf(rows, title=f"Sales Report ({period})")
    return _streaming_response(data, f"sales_{period}.{format}", format)
