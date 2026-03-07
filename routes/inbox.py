"""Inbound message inbox API — list, detail, classify, approve, escalate, feedback."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/inbox", tags=["inbox"])

# Module-level DI (set by main.py)
_db = None
_classifier = None
_response_engine = None


def set_inbox_services(db_manager=None, classifier=None, response_engine=None):
    global _db, _classifier, _response_engine
    _db = db_manager
    _classifier = classifier
    _response_engine = response_engine


# ── Request / Response Models ──


class DraftUpdateRequest(BaseModel):
    response_text: str


class FeedbackRequest(BaseModel):
    original_intent: str
    corrected_intent: str
    notes: Optional[str] = None


class SimulateRequest(BaseModel):
    from_address: str = "demo@customer.com"
    subject: str = "Customer inquiry"
    body: str
    channel: str = "email"


# ── Endpoints ──


@router.get("/messages/stats")
async def message_stats():
    """Dashboard stats: count by status, by intent, avg response time."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with _db.pool.acquire() as conn:
        by_status = await conn.fetch(
            "SELECT status, COUNT(*) AS count FROM inbound_messages GROUP BY status"
        )
        by_intent = await conn.fetch(
            """SELECT intent_elem->>'intent' AS intent, COUNT(*) AS count
               FROM inbound_messages
               CROSS JOIN LATERAL jsonb_array_elements(
                   CASE WHEN intents IS NOT NULL AND length(intents::text) > 2
                        THEN intents::jsonb ELSE '[]'::jsonb END
               ) AS intent_elem
               WHERE intents IS NOT NULL AND intents::text != ''
               GROUP BY intent_elem->>'intent'
               ORDER BY count DESC"""
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM inbound_messages")
    return {
        "total": total or 0,
        "by_status": [dict(r) for r in by_status],
        "by_intent": [dict(r) for r in by_intent],
    }


@router.get("/messages")
async def list_messages(
    status: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    intent: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List inbound messages with filters and pagination."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    conditions = []
    params = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if channel:
        conditions.append(f"channel = ${idx}")
        params.append(channel)
        idx += 1
    if intent:
        conditions.append(f"intents ILIKE ${idx}")
        params.append(f"%{intent}%")
        idx += 1
    if assigned_to:
        conditions.append(f"assigned_to = ${idx}")
        params.append(assigned_to)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params.append(limit)
    params.append(offset)

    sql = f"""SELECT id, from_address, subject, status, channel, intents,
                     ai_confidence, assigned_to, created_at
              FROM inbound_messages {where}
              ORDER BY created_at DESC
              LIMIT ${idx} OFFSET ${idx + 1}"""

    async with _db.pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM inbound_messages {where}",
            *params[:-2],
        )

    return {
        "messages": [dict(r) for r in rows],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/messages/{message_id}")
async def get_message(message_id: str):
    """Get full message detail with AI draft and intents."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with _db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, from_address, subject, body, status, channel,
                      intents, ai_draft_response, ai_confidence,
                      assigned_to, customer_account_id, created_at
               FROM inbound_messages WHERE id = $1""",
            message_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    return dict(row)


@router.patch("/messages/{message_id}/classify")
async def classify_message(message_id: str):
    """Trigger (re-)classification of a message."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    if not _classifier:
        raise HTTPException(status_code=503, detail="Classifier unavailable")

    async with _db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, body FROM inbound_messages WHERE id = $1",
            message_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")

    result = await _classifier.classify(row["body"])

    intents_json = json.dumps([
        {"intent": r.intent.value, "confidence": r.confidence, "text_span": r.text_span}
        for r in result.intents
    ])

    # Generate AI draft if response engine available
    ai_draft = None
    ai_confidence = None
    if _response_engine and result.intents:
        try:
            draft = await _response_engine.generate_draft(
                row["body"], result, customer_account=None,
            )
            ai_draft = draft["response_text"]
            ai_confidence = draft["confidence"]
        except Exception as exc:
            logger.warning("Draft generation failed: %s", exc)

    async with _db.pool.acquire() as conn:
        await conn.execute(
            """UPDATE inbound_messages
               SET intents = $1, ai_draft_response = $2, ai_confidence = $3,
                   status = CASE WHEN status = 'new' THEN 'classified' ELSE status END
               WHERE id = $4""",
            intents_json, ai_draft, ai_confidence, message_id,
        )

    return {"message_id": message_id, "intents": intents_json, "status": "classified"}


@router.patch("/messages/{message_id}/approve")
async def approve_message(message_id: str):
    """Mark message as approved (human approved the AI draft)."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with _db.pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE inbound_messages SET status = 'approved' WHERE id = $1",
            message_id,
        )
    return {"message_id": message_id, "status": "approved"}


@router.patch("/messages/{message_id}/escalate")
async def escalate_message(message_id: str, assigned_to: Optional[str] = Query(None)):
    """Escalate message to a human agent."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with _db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE inbound_messages SET status = 'escalated', assigned_to = $1 WHERE id = $2",
            assigned_to, message_id,
        )
    return {"message_id": message_id, "status": "escalated", "assigned_to": assigned_to}


@router.patch("/messages/{message_id}/draft")
async def update_draft(message_id: str, body: DraftUpdateRequest):
    """Update the AI draft text (human edits)."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with _db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE inbound_messages SET ai_draft_response = $1 WHERE id = $2",
            body.response_text, message_id,
        )
    return {"message_id": message_id, "draft_updated": True}


@router.post("/messages/{message_id}/feedback")
async def submit_feedback(message_id: str, body: FeedbackRequest):
    """Log a classification correction to classification_feedback table."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with _db.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO classification_feedback
               (message_id, original_intent, corrected_intent, notes)
               VALUES ($1, $2, $3, $4)""",
            message_id, body.original_intent, body.corrected_intent, body.notes,
        )
    return {"message_id": message_id, "feedback_recorded": True}


@router.post("/messages/simulate")
async def simulate_inbound(req: SimulateRequest):
    """Simulate an inbound message — classify, draft, and store."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Classify
    intents_data = []
    if _classifier:
        result = await _classifier.classify(req.body)
        intents_data = [
            {"intent": r.intent.value, "confidence": r.confidence, "text_span": r.text_span}
            for r in result.intents
        ]
    intents_json = json.dumps(intents_data)

    # Generate AI draft
    ai_draft = None
    ai_confidence = None
    if _response_engine and _classifier and result.intents:
        try:
            draft = await _response_engine.generate_draft(
                req.body, result, customer_account=None,
            )
            ai_draft = draft["response_text"]
            ai_confidence = draft["confidence"]
        except Exception as exc:
            logger.warning("Draft generation failed for simulated message: %s", exc)

    status = "draft_ready" if ai_draft else ("classified" if intents_data else "new")

    async with _db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO inbound_messages
               (channel, from_address, subject, body, intents, status,
                ai_draft_response, ai_confidence)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING id""",
            req.channel, req.from_address, req.subject, req.body,
            intents_json, status, ai_draft, ai_confidence,
        )

    return {
        "message_id": str(row["id"]) if row else None,
        "intents": intents_data,
        "status": status,
        "ai_draft": ai_draft,
        "ai_confidence": ai_confidence,
    }
