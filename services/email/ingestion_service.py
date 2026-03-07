"""Email ingestion orchestrator — polls inboxes, deduplicates, redacts PII, encrypts, stores."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Module-level DI (same pattern as other services)
_ingestion_service = None


def set_ingestion_service(svc):
    global _ingestion_service
    _ingestion_service = svc


def get_ingestion_service():
    return _ingestion_service


class EmailIngestionService:
    """Orchestrates email ingestion: poll → parse → PII scan → encrypt → store."""

    MAX_ATTACHMENT_BYTES = 25_000_000  # 25 MB
    MAX_BODY_BYTES = 1_000_000        # 1 MB
    DEDUP_TTL_SECONDS = 604_800       # 7 days
    MAX_QUEUE_SIZE = 200              # backpressure threshold

    def __init__(
        self,
        db_manager,
        connector,
        parser,
        pii_scanner,
        encryption,
        logger=None,
        attachment_dir="data/email_attachments",
        max_messages_per_poll=50,
        redis_client=None,
        post_ingest_callback=None,
    ):
        self._db = db_manager
        self._connector = connector
        self._parser = parser
        self._pii = pii_scanner
        self._enc = encryption
        self._log = logger or logging.getLogger(__name__)
        self._attachment_dir = attachment_dir
        self._max_per_poll = max_messages_per_poll
        self._redis = redis_client
        self._post_ingest_callback = post_ingest_callback

    def set_post_ingest_callback(self, callback):
        """Set callback invoked after each message is stored. Signature: async fn(message_id, body)."""
        self._post_ingest_callback = callback

    async def poll_all_inboxes(self) -> dict:
        """APScheduler entry point: poll every active inbox."""
        stats = {"inboxes": 0, "messages": 0, "errors": 0, "skipped_backpressure": False}

        # Backpressure: skip if too many unprocessed messages
        try:
            async with self._db.pool.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM inbound_messages WHERE status = 'new'"
                )
            if count and count > self.MAX_QUEUE_SIZE:
                self._log.warning(
                    "Backpressure: %d unprocessed messages, skipping poll cycle", count
                )
                stats["skipped_backpressure"] = True
                return stats
        except Exception as e:
            self._log.error("Backpressure check failed: %s", e)

        inboxes = await self.get_active_inboxes()
        stats["inboxes"] = len(inboxes)

        for inbox in inboxes:
            try:
                result = await self.poll_inbox(inbox)
                stats["messages"] += result.get("processed", 0)
                stats["errors"] += result.get("errors", 0)
            except Exception as e:
                self._log.error("Poll failed for %s: %s", inbox.get("inbox_address"), e)
                stats["errors"] += 1
                await self._audit(
                    "fetch_error", None,
                    inbox_address=inbox.get("inbox_address"),
                    detail={"error": str(e)},
                )

        self._log.info(
            "Poll complete: %d inboxes, %d messages, %d errors",
            stats["inboxes"], stats["messages"], stats["errors"],
        )
        return stats

    async def poll_inbox(self, inbox_config: dict) -> dict:
        """Poll a single inbox for new messages."""
        inbox = inbox_config["inbox_address"]
        history_id = inbox_config.get("history_id")
        result = {"processed": 0, "errors": 0, "deduped": 0}

        messages = await self._connector.list_new_messages(
            inbox, history_id, max_results=self._max_per_poll,
        )

        new_history_id = None
        for msg_stub in messages:
            gmail_id = msg_stub.get("id", "")
            try:
                if await self._is_duplicate(gmail_id):
                    result["deduped"] += 1
                    await self._audit("deduped_skip", None, gmail_id=gmail_id, inbox_address=inbox)
                    continue

                success = await self._process_message(inbox, msg_stub)
                if success:
                    result["processed"] += 1
                else:
                    result["errors"] += 1
            except Exception as e:
                self._log.error("Process message %s failed: %s", gmail_id, e)
                result["errors"] += 1
                await self._audit(
                    "parse_error", None, gmail_id=gmail_id,
                    inbox_address=inbox, detail={"error": str(e)},
                )

        # Update history_id and last_polled_at
        try:
            if messages:
                new_history_id = await self._connector.get_history_id(inbox)
            async with self._db.pool.acquire() as conn:
                updates = ["last_polled_at = now()", "updated_at = now()"]
                params = [inbox]
                if new_history_id:
                    updates.append(f"history_id = ${len(params) + 1}")
                    params.append(new_history_id)
                await conn.execute(
                    f"UPDATE email_oauth_tokens SET {', '.join(updates)} "
                    f"WHERE inbox_address = $1",
                    *params,
                )
        except Exception as e:
            self._log.error("Update history_id failed for %s: %s", inbox, e)

        return result

    async def _process_message(self, inbox: str, raw_message: dict) -> bool:
        """Fetch, parse, scan, encrypt, store a single message."""
        gmail_id = raw_message.get("id", "")

        # Fetch full payload
        payload = await self._connector.get_message(inbox, gmail_id)

        # Parse
        parsed = self._parser.parse_gmail_payload(payload, thread_id=payload.get("threadId"))

        # PII scan: redacted body for LLM, original for encrypted storage
        original_body = parsed.body_text
        scan_result = self._pii.scan(original_body)
        redacted_body = scan_result.redacted_text
        pii_detected = len(scan_result.detected_types) > 0

        # Encrypt original body
        encrypted_body = self._enc.encrypt(original_body)

        # Store
        message_id = await self._store_message(
            parsed=parsed,
            inbox=inbox,
            gmail_id=gmail_id,
            redacted_body=redacted_body,
            encrypted_body=encrypted_body,
            pii_redacted=pii_detected,
            raw_payload=payload,
        )

        # Log PII redaction if detected
        if scan_result.redaction_count > 0:
            await self._audit(
                "pii_redacted", message_id, gmail_id=gmail_id,
                inbox_address=inbox,
                detail={
                    "types": scan_result.detected_types,
                    "count": scan_result.redaction_count,
                },
            )

        # Download attachments (skip oversized)
        for att in parsed.attachments:
            if att.size_bytes > self.MAX_ATTACHMENT_BYTES:
                self._log.warning(
                    "Skipping oversized attachment %s (%d bytes)", att.filename, att.size_bytes
                )
                continue
            await self._store_attachment(inbox, gmail_id, att)

        # Audit
        size_bytes = len(original_body.encode("utf-8", errors="replace"))
        await self._audit(
            "ingested", message_id, gmail_id=gmail_id,
            inbox_address=inbox,
            detail={"subject": parsed.subject, "size_bytes": size_bytes},
        )

        # Mark in Redis
        await self._mark_processed(gmail_id)

        # Post-ingest: auto-classify and generate AI draft (fire-and-forget)
        if self._post_ingest_callback:
            try:
                await self._post_ingest_callback(message_id, redacted_body)
            except Exception as e:
                self._log.warning("Post-ingest callback failed for %s (non-fatal): %s", message_id, e)

        return True

    async def _is_duplicate(self, gmail_message_id: str) -> bool:
        """Check dedup: Redis SET NX first, PG unique index fallback."""
        if self._redis:
            try:
                key = f"email:dedup:{gmail_message_id}"
                result = await self._redis.set(key, "1", nx=True, ex=self.DEDUP_TTL_SECONDS)
                if result is None:
                    return True  # Already exists
                return False
            except Exception:
                pass  # Fall through to PG

        # PG fallback
        try:
            async with self._db.pool.acquire() as conn:
                row = await conn.fetchval(
                    "SELECT 1 FROM inbound_messages WHERE gmail_message_id = $1",
                    gmail_message_id,
                )
                return row is not None
        except Exception:
            return False

    async def _mark_processed(self, gmail_message_id: str):
        """Mark message as processed in Redis (if available)."""
        if self._redis:
            try:
                key = f"email:dedup:{gmail_message_id}"
                await self._redis.set(key, "1", ex=self.DEDUP_TTL_SECONDS)
            except Exception:
                pass

    async def _store_message(
        self, parsed, inbox, gmail_id, redacted_body,
        encrypted_body, pii_redacted, raw_payload,
    ) -> str:
        """Insert into inbound_messages, return message UUID."""
        message_id = str(uuid.uuid4())
        size_bytes = len(parsed.body_text.encode("utf-8", errors="replace"))

        raw_json = {
            "encrypted_body": encrypted_body,
            "headers": parsed.raw_headers,
        }

        async with self._db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO inbound_messages
                   (id, channel, from_address, to_address, subject, body,
                    raw_payload, attachments, status, thread_id,
                    gmail_message_id, body_encrypted, pii_redacted, size_bytes, created_at)
                   VALUES ($1, 'email', $2, $3, $4, $5, $6, $7, 'new', $8,
                           $9, $10, $11, $12, $13)""",
                uuid.UUID(message_id),
                parsed.from_address,
                ",".join(parsed.to_addresses) if parsed.to_addresses else inbox,
                parsed.subject,
                redacted_body,
                json.dumps(raw_json),
                json.dumps([
                    {"filename": a.filename, "content_type": a.content_type,
                     "size_bytes": a.size_bytes}
                    for a in parsed.attachments
                ]),
                parsed.thread_id,
                gmail_id,
                self._enc.is_configured,
                pii_redacted,
                size_bytes,
                parsed.date or datetime.now(timezone.utc),
            )

        return message_id

    async def _store_attachment(self, inbox: str, message_id: str, att) -> str | None:
        """Download and store attachment to filesystem."""
        if not att.gmail_attachment_id:
            return None

        try:
            data = await self._connector.get_attachment(inbox, message_id, att.gmail_attachment_id)
            dir_path = os.path.join(self._attachment_dir, message_id)
            os.makedirs(dir_path, exist_ok=True)
            file_path = os.path.join(dir_path, att.filename)
            with open(file_path, "wb") as f:
                f.write(data)
            return file_path
        except Exception as e:
            self._log.error("Attachment download failed: %s", e)
            return None

    async def _audit(
        self, event_type: str, message_id: str | None,
        gmail_id: str | None = None,
        inbox_address: str | None = None,
        detail: dict | None = None,
    ) -> None:
        """Append to email_audit_log. Swallows all exceptions."""
        try:
            async with self._db.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO email_audit_log
                       (event_type, message_id, gmail_message_id, inbox_address, detail)
                       VALUES ($1, $2, $3, $4, $5)""",
                    event_type,
                    uuid.UUID(message_id) if message_id else None,
                    gmail_id,
                    inbox_address,
                    json.dumps(detail) if detail else None,
                )
        except Exception as e:
            self._log.debug("Audit log write failed (non-fatal): %s", e)

    async def get_active_inboxes(self) -> list[dict]:
        """Return all active inbox configurations."""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT inbox_address, history_id, last_polled_at "
                "FROM email_oauth_tokens WHERE is_active = true"
            )
        return [dict(r) for r in rows]

    async def purge_old_messages(self, days: int = 90) -> int:
        """Nullify raw_payload for messages older than N days."""
        async with self._db.pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE inbound_messages
                   SET raw_payload = NULL
                   WHERE channel = 'email'
                     AND raw_payload IS NOT NULL
                     AND created_at < now() - ($1 || ' days')::interval""",
                str(days),
            )
        # Parse "UPDATE N" response
        try:
            count = int(result.split()[-1])
        except (ValueError, IndexError):
            count = 0
        self._log.info("Purged raw_payload for %d messages older than %d days", count, days)
        return count
