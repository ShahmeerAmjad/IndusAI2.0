"""MIME email parser — converts raw bytes or Gmail API payload to structured data."""

import base64
import email
import email.policy
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from io import StringIO

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1_000_000  # 1 MB


@dataclass
class AttachmentMeta:
    filename: str
    content_type: str
    size_bytes: int
    content_id: str | None = None
    gmail_attachment_id: str | None = None


@dataclass
class ParsedEmail:
    message_id: str
    thread_id: str | None
    from_address: str
    to_addresses: list[str] = field(default_factory=list)
    cc_addresses: list[str] = field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None
    attachments: list[AttachmentMeta] = field(default_factory=list)
    date: datetime | None = None
    raw_headers: dict[str, str] = field(default_factory=dict)
    encoding_issues: bool = False


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text via stdlib."""

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("br", "p", "div", "li", "tr"):
            self._pieces.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._pieces.append(data)

    def get_text(self) -> str:
        return "".join(self._pieces).strip()


class EmailParser:
    """Parse raw MIME bytes or Gmail API payload into ParsedEmail."""

    def parse_raw(self, raw_bytes: bytes) -> ParsedEmail:
        """Parse raw RFC-2822 MIME bytes."""
        msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

        message_id = msg.get("Message-ID", "") or ""
        from_addr = parseaddr(msg.get("From", ""))[1]
        to_addrs = self._parse_address_list(msg.get("To", ""))
        cc_addrs = self._parse_address_list(msg.get("Cc", ""))
        subject = msg.get("Subject", "") or ""

        # Thread ID: References (last) → In-Reply-To → message_id
        thread_id = self._extract_thread_id(msg)

        # Date
        date = None
        try:
            date_str = msg.get("Date")
            if date_str:
                date = parsedate_to_datetime(date_str)
        except Exception:
            pass

        # Headers
        raw_headers = {k: str(v) for k, v in msg.items()}

        # Body
        body_text, body_html, encoding_issues = self._extract_body(msg)

        # Truncate oversized body
        if len(body_text.encode("utf-8", errors="replace")) > MAX_BODY_BYTES:
            body_text = body_text[: MAX_BODY_BYTES // 4] + "\n[TRUNCATED]"

        # Attachments
        attachments = self._extract_attachments(msg)

        return ParsedEmail(
            message_id=message_id,
            thread_id=thread_id,
            from_address=from_addr,
            to_addresses=to_addrs,
            cc_addresses=cc_addrs,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            date=date,
            raw_headers=raw_headers,
            encoding_issues=encoding_issues,
        )

    def parse_gmail_payload(
        self, payload: dict, thread_id: str | None = None,
    ) -> ParsedEmail:
        """Parse a Gmail API message resource (format=full)."""
        headers = {
            h["name"]: h["value"]
            for h in payload.get("payload", payload).get("headers", [])
        }

        message_id = headers.get("Message-ID", headers.get("Message-Id", ""))
        from_addr = parseaddr(headers.get("From", ""))[1]
        to_addrs = self._parse_address_list(headers.get("To", ""))
        cc_addrs = self._parse_address_list(headers.get("Cc", ""))
        subject = headers.get("Subject", "")

        if not thread_id:
            thread_id = payload.get("threadId")

        date = None
        try:
            date_str = headers.get("Date")
            if date_str:
                date = parsedate_to_datetime(date_str)
        except Exception:
            pass

        # Extract body from Gmail payload parts
        body_text, body_html, attachments = self._walk_gmail_parts(
            payload.get("payload", payload)
        )

        if len(body_text.encode("utf-8", errors="replace")) > MAX_BODY_BYTES:
            body_text = body_text[: MAX_BODY_BYTES // 4] + "\n[TRUNCATED]"

        if not body_text and body_html:
            body_text = self._html_to_text(body_html)

        return ParsedEmail(
            message_id=message_id,
            thread_id=thread_id,
            from_address=from_addr,
            to_addresses=to_addrs,
            cc_addresses=cc_addrs,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            date=date,
            raw_headers=headers,
            encoding_issues=False,
        )

    # ── Internal helpers ──

    def _extract_body(self, msg) -> tuple[str, str | None, bool]:
        """Extract text and HTML bodies from a MIME message."""
        body_text = ""
        body_html = None
        encoding_issues = False

        if not msg.is_multipart():
            ct = msg.get_content_type()
            text = self._decode_part(msg)
            if text is None:
                encoding_issues = True
                text = ""
            if ct == "text/html":
                body_html = text
                body_text = self._html_to_text(text)
            else:
                body_text = text
            return body_text, body_html, encoding_issues

        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp:
                continue
            if ct == "text/plain" and not body_text:
                text = self._decode_part(part)
                if text is None:
                    encoding_issues = True
                    text = ""
                body_text = text
            elif ct == "text/html" and body_html is None:
                text = self._decode_part(part)
                if text is None:
                    encoding_issues = True
                    text = ""
                body_html = text

        # HTML-only: convert to text
        if not body_text and body_html:
            body_text = self._html_to_text(body_html)

        return body_text, body_html, encoding_issues

    def _decode_part(self, part) -> str | None:
        """Decode a MIME part's payload with charset fallback."""
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset)
        except (UnicodeDecodeError, LookupError):
            try:
                return payload.decode("latin-1")
            except Exception:
                return None

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text using stdlib HTMLParser."""
        extractor = _HTMLTextExtractor()
        try:
            extractor.feed(html)
        except Exception:
            # Fallback: strip tags with regex
            return re.sub(r"<[^>]+>", "", html).strip()
        return extractor.get_text()

    def _extract_thread_id(self, msg) -> str | None:
        """Extract thread ID from References (last) → In-Reply-To → None."""
        refs = msg.get("References", "")
        if refs:
            parts = refs.strip().split()
            if parts:
                return parts[-1]
        in_reply = msg.get("In-Reply-To", "")
        if in_reply:
            return in_reply.strip()
        return None

    def _parse_address_list(self, header: str) -> list[str]:
        """Parse a comma-separated address header into a list of emails."""
        if not header:
            return []
        return [
            parseaddr(addr.strip())[1]
            for addr in header.split(",")
            if parseaddr(addr.strip())[1]
        ]

    def _extract_attachments(self, msg) -> list[AttachmentMeta]:
        """Extract attachment metadata from a MIME message."""
        attachments = []
        for part in msg.walk():
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" not in disp:
                continue
            filename = part.get_filename() or "unnamed"
            payload = part.get_payload(decode=True)
            size = len(payload) if payload else 0
            content_id = part.get("Content-ID")
            attachments.append(AttachmentMeta(
                filename=filename,
                content_type=part.get_content_type(),
                size_bytes=size,
                content_id=content_id,
            ))
        return attachments

    def _walk_gmail_parts(
        self, payload: dict,
    ) -> tuple[str, str | None, list[AttachmentMeta]]:
        """Recursively walk Gmail API payload parts."""
        body_text = ""
        body_html = None
        attachments: list[AttachmentMeta] = []

        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data")

        if body_data and "text/plain" in mime_type:
            body_text = base64.urlsafe_b64decode(body_data + "==").decode(
                "utf-8", errors="replace"
            )
        elif body_data and "text/html" in mime_type:
            body_html = base64.urlsafe_b64decode(body_data + "==").decode(
                "utf-8", errors="replace"
            )

        # Check for attachment
        att_id = payload.get("body", {}).get("attachmentId")
        filename = payload.get("filename")
        if att_id and filename:
            attachments.append(AttachmentMeta(
                filename=filename,
                content_type=mime_type,
                size_bytes=payload.get("body", {}).get("size", 0),
                gmail_attachment_id=att_id,
            ))

        # Recurse into parts
        for part in payload.get("parts", []):
            t, h, a = self._walk_gmail_parts(part)
            if t and not body_text:
                body_text = t
            if h and body_html is None:
                body_html = h
            attachments.extend(a)

        return body_text, body_html, attachments
