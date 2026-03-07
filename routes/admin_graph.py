"""Admin debug API — graph stats, seller freshness, sourcing logs, reliability, seed pipeline."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routes.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Set by main.py
_graph_service = None
_db = None
_seed_pipeline = None


def set_admin_services(graph_service, db_manager):
    global _graph_service, _db
    _graph_service = graph_service
    _db = db_manager


def set_seed_pipeline(pipeline):
    global _seed_pipeline
    _seed_pipeline = pipeline


def _require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/graph/stats")
async def graph_stats(user=Depends(_require_admin)):
    """Neo4j node and edge counts by type."""
    if not _graph_service:
        return {"nodes": {}, "edges": {}, "error": "Graph service unavailable"}
    return await _graph_service.get_graph_stats()


@router.get("/sellers/freshness")
async def seller_freshness(user=Depends(_require_admin)):
    """Seller listing freshness — stale count, last scrape times."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        total = await conn.fetchval("SELECT count(*) FROM seller_listings")
        stale = await conn.fetchval(
            "SELECT count(*) FROM seller_listings WHERE stale_after < now()"
        )
        sellers = await conn.fetch("""
            SELECT sp.name, count(sl.id) AS listings,
                   count(*) FILTER (WHERE sl.stale_after < now()) AS stale_count,
                   max(sl.last_verified_at) AS last_verified
            FROM seller_profiles sp
            LEFT JOIN seller_listings sl ON sl.seller_id = sp.id
            GROUP BY sp.id, sp.name
            ORDER BY sp.name
        """)

    return {
        "total_listings": total,
        "stale_listings": stale,
        "fresh_listings": total - stale,
        "sellers": [
            {
                "name": r["name"],
                "listings": r["listings"],
                "stale_count": r["stale_count"],
                "last_verified": r["last_verified"].isoformat() if r["last_verified"] else None,
            }
            for r in sellers
        ],
    }


@router.get("/sourcing/recent")
async def recent_sourcing(user=Depends(_require_admin)):
    """Recent sourcing queries with results summary."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sr.id, sr.query_text, sr.intent, sr.parts_found,
                   sr.created_at, u.email AS user_email, o.name AS org_name
            FROM sourcing_requests sr
            LEFT JOIN users u ON u.id = sr.user_id
            LEFT JOIN organizations o ON o.id = sr.buyer_org_id
            ORDER BY sr.created_at DESC
            LIMIT 50
        """)

    return [
        {
            "id": str(r["id"]),
            "query": r["query_text"],
            "intent": r["intent"],
            "parts_found": r["parts_found"],
            "user_email": r["user_email"],
            "org_name": r["org_name"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.get("/reliability/scores")
async def reliability_scores(user=Depends(_require_admin)):
    """Reliability score distribution across seller listings."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        dist = await conn.fetch("""
            SELECT
                CASE
                    WHEN reliability >= 8 THEN 'high (8-10)'
                    WHEN reliability >= 5 THEN 'medium (5-8)'
                    WHEN reliability >= 3 THEN 'low (3-5)'
                    ELSE 'very_low (0-3)'
                END AS bucket,
                count(*) AS count,
                round(avg(reliability)::numeric, 2) AS avg_score
            FROM seller_listings
            GROUP BY bucket
            ORDER BY avg_score DESC
        """)
        avg_overall = await conn.fetchval(
            "SELECT round(avg(reliability)::numeric, 2) FROM seller_listings"
        )

    return {
        "average_reliability": float(avg_overall) if avg_overall else 0,
        "distribution": [
            {"bucket": r["bucket"], "count": r["count"], "avg_score": float(r["avg_score"])}
            for r in dist
        ],
    }


@router.get("/orders/recent")
async def recent_orders(user=Depends(_require_admin)):
    """Recent sourcing orders placed from chat."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT so.id, so.seller_name, so.sku, so.qty, so.unit_price,
                   so.total, so.status, so.created_at,
                   u.email AS user_email, o.name AS org_name
            FROM sourcing_orders so
            LEFT JOIN users u ON u.id = so.user_id
            LEFT JOIN organizations o ON o.id = so.buyer_org_id
            ORDER BY so.created_at DESC
            LIMIT 50
        """)

    return [
        {
            "id": str(r["id"]),
            "seller_name": r["seller_name"],
            "sku": r["sku"],
            "qty": r["qty"],
            "unit_price": float(r["unit_price"]),
            "total": float(r["total"]),
            "status": r["status"],
            "user_email": r["user_email"],
            "org_name": r["org_name"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


class SeedChempointRequest(BaseModel):
    url: str
    mode: str = "product"  # "product" or "industry"


@router.post("/seed-chempoint")
async def seed_chempoint(body: SeedChempointRequest, user=Depends(_require_admin)):
    """Scrape a Chempoint page and populate the knowledge graph."""
    if not _seed_pipeline:
        raise HTTPException(status_code=503, detail="Seed pipeline not configured")

    if body.mode == "industry":
        stats = await _seed_pipeline.seed_from_industry(body.url)
    else:
        stats = await _seed_pipeline.seed_from_url(body.url)

    return {"status": "ok", "stats": stats}
