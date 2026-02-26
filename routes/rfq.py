"""RFQ API routes — create, list, detail, respond."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.auth import get_current_user

router = APIRouter(prefix="/api/rfq", tags=["rfq"])

# Set by main.py
_db = None


def set_rfq_db(db_manager):
    global _db
    _db = db_manager


class RFQCreateRequest(BaseModel):
    part_description: str = Field(min_length=1)
    part_sku: str | None = None
    qty: int = Field(default=1, ge=1)
    urgency: str = Field(default="standard", pattern="^(urgent|standard|flexible)$")
    target_price: float | None = None


class RFQResponseRequest(BaseModel):
    seller_id: str
    price: float = Field(gt=0)
    lead_time_days: int | None = None
    notes: str = ""
    expires_in_days: int = Field(default=7, ge=1, le=90)


@router.post("")
async def create_rfq(req: RFQCreateRequest, user=Depends(get_current_user)):
    """Create a new RFQ request."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO rfq_requests
               (buyer_org_id, user_id, part_description, part_sku, qty, urgency, target_price)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING id, part_description, part_sku, qty, urgency, target_price, status, created_at""",
            user.get("org_id"), user.get("user_id"),
            req.part_description, req.part_sku, req.qty,
            req.urgency, req.target_price,
        )
    return dict(row)


@router.get("")
async def list_rfqs(user=Depends(get_current_user)):
    """List RFQs for the current buyer's organization."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT r.id, r.part_description, r.part_sku, r.qty, r.urgency,
                      r.target_price, r.status, r.created_at, r.updated_at,
                      (SELECT COUNT(*) FROM rfq_responses rr WHERE rr.rfq_id = r.id) AS response_count
               FROM rfq_requests r
               WHERE r.buyer_org_id = $1
               ORDER BY r.created_at DESC""",
            user.get("org_id"),
        )
    return [dict(r) for r in rows]


@router.get("/{rfq_id}")
async def get_rfq(rfq_id: str, user=Depends(get_current_user)):
    """Get RFQ detail with seller responses."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        rfq = await conn.fetchrow(
            """SELECT * FROM rfq_requests
               WHERE id = $1 AND buyer_org_id = $2""",
            rfq_id, user.get("org_id"),
        )
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")

        responses = await conn.fetch(
            """SELECT rr.*, sp.name AS seller_name
               FROM rfq_responses rr
               JOIN seller_profiles sp ON sp.id = rr.seller_id
               WHERE rr.rfq_id = $1
               ORDER BY rr.price ASC""",
            rfq_id,
        )

    return {
        "rfq": dict(rfq),
        "responses": [dict(r) for r in responses],
    }


@router.post("/{rfq_id}/respond")
async def respond_to_rfq(rfq_id: str, req: RFQResponseRequest,
                          user=Depends(get_current_user)):
    """Seller responds to an RFQ."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        # Verify RFQ exists and is open
        rfq = await conn.fetchrow(
            "SELECT id, status FROM rfq_requests WHERE id = $1",
            rfq_id,
        )
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")
        if rfq["status"] != "open":
            raise HTTPException(status_code=400, detail="RFQ is not open for responses")

        row = await conn.fetchrow(
            """INSERT INTO rfq_responses
               (rfq_id, seller_id, price, lead_time_days, notes, expires_at)
               VALUES ($1, $2, $3, $4, $5, now() + ($6 || ' days')::interval)
               RETURNING id, rfq_id, seller_id, price, lead_time_days, notes, expires_at, created_at""",
            rfq_id, req.seller_id, req.price, req.lead_time_days,
            req.notes, str(req.expires_in_days),
        )

    return dict(row)
