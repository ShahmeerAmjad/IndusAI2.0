"""Email admin API — manage inboxes, OAuth tokens, trigger polls, view audit log."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.auth import get_current_user

router = APIRouter(prefix="/api/admin/email", tags=["email-admin"])

# Set by main.py
_db = None
_encryption = None
_ingestion_service = None


def set_email_admin_services(db_manager, encryption, ingestion_service):
    global _db, _encryption, _ingestion_service
    _db = db_manager
    _encryption = encryption
    _ingestion_service = ingestion_service


def _require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Request/Response Models ──


class AddInboxRequest(BaseModel):
    inbox_address: str = Field(..., description="Email address (e.g. sales@company.com)")
    provider: str = Field(default="gmail", description="Email provider")
    access_token: str = Field(..., description="OAuth2 access token")
    refresh_token: str = Field(..., description="OAuth2 refresh token")
    token_expiry: Optional[str] = Field(default=None, description="ISO datetime of token expiry")


class UpdateInboxRequest(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[str] = None
    is_active: Optional[bool] = None


class InboxResponse(BaseModel):
    inbox_address: str
    provider: str
    is_active: bool
    history_id: Optional[str]
    last_polled_at: Optional[str]
    created_at: str
    updated_at: str


# ── Endpoints ──


@router.get("/inboxes", response_model=list[InboxResponse])
async def list_inboxes(user=Depends(_require_admin)):
    """List all configured email inboxes."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT inbox_address, provider, is_active, history_id,
                      last_polled_at, created_at, updated_at
               FROM email_oauth_tokens ORDER BY created_at DESC"""
        )

    return [
        InboxResponse(
            inbox_address=r["inbox_address"],
            provider=r["provider"],
            is_active=r["is_active"],
            history_id=r["history_id"],
            last_polled_at=r["last_polled_at"].isoformat() if r["last_polled_at"] else None,
            created_at=r["created_at"].isoformat(),
            updated_at=r["updated_at"].isoformat(),
        )
        for r in rows
    ]


@router.post("/inboxes", status_code=201)
async def add_inbox(req: AddInboxRequest, user=Depends(_require_admin)):
    """Add a new email inbox with OAuth2 credentials."""
    if not _db or not _db.pool or not _encryption:
        raise HTTPException(status_code=503, detail="Service unavailable")

    # Encrypt tokens before storing
    enc_access = _encryption.encrypt(req.access_token)
    enc_refresh = _encryption.encrypt(req.refresh_token)

    token_expiry = None
    if req.token_expiry:
        try:
            token_expiry = datetime.fromisoformat(req.token_expiry)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid token_expiry format")

    try:
        async with _db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO email_oauth_tokens
                   (inbox_address, provider, access_token, refresh_token, token_expiry, is_active)
                   VALUES ($1, $2, $3, $4, $5, true)
                   ON CONFLICT (inbox_address) DO UPDATE SET
                       access_token = EXCLUDED.access_token,
                       refresh_token = EXCLUDED.refresh_token,
                       token_expiry = EXCLUDED.token_expiry,
                       is_active = true,
                       updated_at = now()""",
                req.inbox_address, req.provider, enc_access, enc_refresh, token_expiry,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save inbox: {e}")

    return {"status": "ok", "inbox_address": req.inbox_address, "encrypted": _encryption.is_configured}


@router.patch("/inboxes/{inbox_address}")
async def update_inbox(inbox_address: str, req: UpdateInboxRequest, user=Depends(_require_admin)):
    """Update an existing inbox's tokens or active status."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    updates = []
    params = []
    idx = 1

    if req.access_token is not None:
        idx += 1
        updates.append(f"access_token = ${idx}")
        params.append(_encryption.encrypt(req.access_token))
    if req.refresh_token is not None:
        idx += 1
        updates.append(f"refresh_token = ${idx}")
        params.append(_encryption.encrypt(req.refresh_token))
    if req.token_expiry is not None:
        idx += 1
        updates.append(f"token_expiry = ${idx}")
        try:
            params.append(datetime.fromisoformat(req.token_expiry))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid token_expiry format")
    if req.is_active is not None:
        idx += 1
        updates.append(f"is_active = ${idx}")
        params.append(req.is_active)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = now()")

    async with _db.pool.acquire() as conn:
        result = await conn.execute(
            f"UPDATE email_oauth_tokens SET {', '.join(updates)} WHERE inbox_address = $1",
            inbox_address, *params,
        )

    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail="Inbox not found")

    return {"status": "ok", "inbox_address": inbox_address}


@router.delete("/inboxes/{inbox_address}")
async def delete_inbox(inbox_address: str, user=Depends(_require_admin)):
    """Remove an inbox and its OAuth credentials."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM email_oauth_tokens WHERE inbox_address = $1",
            inbox_address,
        )

    if "DELETE 0" in result:
        raise HTTPException(status_code=404, detail="Inbox not found")

    return {"status": "ok", "deleted": inbox_address}


@router.post("/poll")
async def trigger_poll(user=Depends(_require_admin)):
    """Manually trigger an email poll cycle (all active inboxes)."""
    if not _ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service unavailable")

    result = await _ingestion_service.poll_all_inboxes()
    return {"status": "ok", **result}


@router.post("/poll/{inbox_address}")
async def trigger_poll_inbox(inbox_address: str, user=Depends(_require_admin)):
    """Manually trigger a poll for a specific inbox."""
    if not _ingestion_service:
        raise HTTPException(status_code=503, detail="Ingestion service unavailable")

    # Check inbox exists
    async with _db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT inbox_address, history_id, last_polled_at "
            "FROM email_oauth_tokens WHERE inbox_address = $1 AND is_active = true",
            inbox_address,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Inbox not found or inactive")

    result = await _ingestion_service.poll_inbox(dict(row))
    return {"status": "ok", "inbox_address": inbox_address, **result}


@router.get("/audit")
async def get_audit_log(
    limit: int = 50,
    inbox_address: Optional[str] = None,
    event_type: Optional[str] = None,
    user=Depends(_require_admin),
):
    """View email audit log with optional filters."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query = "SELECT * FROM email_audit_log WHERE 1=1"
    params = []
    idx = 0

    if inbox_address:
        idx += 1
        query += f" AND inbox_address = ${idx}"
        params.append(inbox_address)
    if event_type:
        idx += 1
        query += f" AND event_type = ${idx}"
        params.append(event_type)

    idx += 1
    query += f" ORDER BY created_at DESC LIMIT ${idx}"
    params.append(limit)

    async with _db.pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [dict(r) for r in rows]


@router.get("/stats")
async def email_stats(user=Depends(_require_admin)):
    """Email pipeline health dashboard data."""
    if not _db or not _db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _db.pool.acquire() as conn:
        inbox_count = await conn.fetchval(
            "SELECT COUNT(*) FROM email_oauth_tokens WHERE is_active = true"
        )
        active_inboxes = await conn.fetch(
            """SELECT inbox_address, last_polled_at, history_id
               FROM email_oauth_tokens WHERE is_active = true"""
        )
        queue_size = await conn.fetchval(
            "SELECT COUNT(*) FROM inbound_messages WHERE status = 'new' AND channel = 'email'"
        )
        today_ingested = await conn.fetchval(
            """SELECT COUNT(*) FROM inbound_messages
               WHERE channel = 'email' AND created_at >= CURRENT_DATE"""
        )
        recent_errors = await conn.fetchval(
            """SELECT COUNT(*) FROM email_audit_log
               WHERE event_type IN ('parse_error', 'fetch_error')
                 AND created_at >= now() - interval '24 hours'"""
        )

    return {
        "active_inboxes": inbox_count,
        "inboxes": [
            {
                "address": r["inbox_address"],
                "last_polled": r["last_polled_at"].isoformat() if r["last_polled_at"] else None,
                "has_history_id": r["history_id"] is not None,
            }
            for r in active_inboxes
        ],
        "queue_size": queue_size,
        "today_ingested": today_ingested,
        "errors_24h": recent_errors,
    }


@router.post("/generate-encryption-key")
async def generate_encryption_key(user=Depends(_require_admin)):
    """Generate a new Fernet encryption key (for .env setup)."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    return {
        "key": key,
        "instruction": "Add this to your .env file as EMAIL_ENCRYPTION_KEY=<key>",
        "warning": "Store securely. If lost, encrypted email bodies cannot be decrypted.",
    }
