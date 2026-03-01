"""Sourcing API — AI-powered part search and comparison."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.auth import get_current_user

router = APIRouter(prefix="/api/sourcing", tags=["sourcing"])

# Set by main.py
_query_engine = None
_seller_service = None
_db = None


def set_sourcing_services(query_engine, seller_service, db_manager):
    global _query_engine, _seller_service, _db
    _query_engine = query_engine
    _seller_service = seller_service
    _db = db_manager


class SourcingQuery(BaseModel):
    query: str = Field(min_length=1)
    qty: int = Field(default=1, ge=1)
    location_id: str | None = None
    debug: bool = False


class SourcingOrderRequest(BaseModel):
    seller_name: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    qty: int = Field(ge=1)
    unit_price: float = Field(gt=0)


@router.post("/search")
async def sourcing_search(req: SourcingQuery, user=Depends(get_current_user)):
    """AI-powered part sourcing search."""
    if not _query_engine:
        raise HTTPException(status_code=503, detail="Sourcing engine unavailable")

    result = await _query_engine.process_query(
        message=req.query,
        customer_id=user.get("org_id"),
    )

    response = {
        "response": result.response,
        "parts_found": result.parts_found,
        "intent": result.intent.intent.value if result.intent else None,
        "sourcing_results": [
            {
                "sku": sr.sku,
                "name": sr.name,
                "seller_name": sr.seller_name,
                "unit_price": sr.unit_price,
                "total_cost": sr.total_cost(req.qty),
                "transit_days": sr.transit_days,
                "shipping_cost": sr.shipping_cost,
                "distance_km": sr.distance_km,
                "qty_available": sr.qty_available,
                "manufacturer": sr.manufacturer,
            }
            for sr in result.sourcing_results
        ],
    }

    if req.debug and user.get("role") == "admin":
        response["debug"] = {
            "graph_paths": result.graph_paths,
            "scores": [sr.debug for sr in result.sourcing_results],
        }

    # Log sourcing request
    if _db and _db.pool:
        try:
            import json
            async with _db.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO sourcing_requests
                       (buyer_org_id, user_id, query_text, intent, results_json, parts_found)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    user.get("org_id"), user.get("user_id"),
                    req.query, response.get("intent"),
                    json.dumps(response["sourcing_results"]),
                    result.parts_found,
                )
        except Exception:
            pass  # Non-critical logging

    return response


@router.post("/order")
async def sourcing_order(req: SourcingOrderRequest, user=Depends(get_current_user)):
    """Place an order from sourcing results."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    total = round(req.unit_price * req.qty, 2)

    async with _db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO sourcing_orders
               (buyer_org_id, user_id, seller_name, sku, qty, unit_price, total, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'confirmed')
               RETURNING id, status""",
            user.get("org_id"), user.get("user_id"),
            req.seller_name, req.sku, req.qty, req.unit_price, total,
        )

    return {
        "order_id": str(row["id"]),
        "status": row["status"],
        "message": f"Order confirmed — {req.qty}x {req.sku} from {req.seller_name} at ${total:.2f}",
    }
