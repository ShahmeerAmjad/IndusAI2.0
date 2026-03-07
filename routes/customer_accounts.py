"""Customer account API — CRUD and email lookup."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/customer-accounts", tags=["customer-accounts"])

# Module-level DI
_account_service = None


def set_customer_account_services(account_service=None):
    global _account_service
    _account_service = account_service


def _require_service():
    if not _account_service:
        raise HTTPException(status_code=503, detail="Customer account service unavailable")
    return _account_service


# ── Request Models ──


class CreateAccountRequest(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    fax_number: Optional[str] = None
    company: Optional[str] = None
    account_number: Optional[str] = None
    erp_customer_id: Optional[str] = None
    pricing_tier: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


class UpdateAccountRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    fax_number: Optional[str] = None
    company: Optional[str] = None
    account_number: Optional[str] = None
    erp_customer_id: Optional[str] = None
    pricing_tier: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


# ── Endpoints ──


@router.get("")
async def list_accounts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List customer accounts with pagination."""
    svc = _require_service()
    accounts = await svc.list_accounts(limit=limit, offset=offset)
    return {"accounts": accounts, "limit": limit, "offset": offset}


@router.post("", status_code=201)
async def create_account(body: CreateAccountRequest):
    """Create a new customer account."""
    svc = _require_service()
    account = await svc.create_account(body.model_dump(exclude_none=True))
    return account


@router.get("/lookup")
async def lookup_by_email(email: str = Query(..., description="Email to look up")):
    """Look up a customer account by email address."""
    svc = _require_service()
    account = await svc.lookup_by_email(email)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found for this email")
    return account


@router.get("/{account_id}")
async def get_account(account_id: str):
    """Get customer account detail."""
    svc = _require_service()
    account = await svc.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("/{account_id}")
async def update_account(account_id: str, body: UpdateAccountRequest):
    """Update a customer account."""
    svc = _require_service()
    updated = await svc.update_account(
        account_id, body.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found")
    return updated
