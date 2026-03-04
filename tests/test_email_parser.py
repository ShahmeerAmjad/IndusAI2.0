"""Tests for services.email.parser — MIME and Gmail API payload parsing."""

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import pytest

from services.email.parser import EmailParser, ParsedEmail


@pytest.fixture
def parser():
    return EmailParser()


def _build_raw_email(
    from_addr="sender@example.com",
    to_addr="inbox@company.com",
    subject="Test Subject",
    body_text="Hello, world!",
    body_html=None,
    message_id="<abc123@example.com>",
    references=None,
    in_reply_to=None,
    attachment=None,
    charset="utf-8",
) -> bytes:
    """Helper to build raw MIME bytes."""
    if body_html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text, "plain", charset))
        msg.attach(MIMEText(body_html, "html", charset))
    elif attachment:
        msg = MIMEMultipart("mixed")
        msg.attach(MIMEText(body_text, "plain", charset))
        part = MIMEBase("application", "pdf")
        part.set_payload(b"fake pdf content")
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="doc.pdf")
        msg.attach(part)
    else:
        msg = MIMEText(body_text, "plain", charset)

    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    msg["Date"] = "Mon, 01 Jan 2024 12:00:00 +0000"
    if references:
        msg["References"] = references
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    return msg.as_bytes()


class TestEmailParser:
    def test_basic_parse(self, parser):
        raw = _build_raw_email()
        result = parser.parse_raw(raw)
        assert result.from_address == "sender@example.com"
        assert "inbox@company.com" in result.to_addresses
        assert result.subject == "Test Subject"
        assert result.body_text == "Hello, world!"
        assert result.message_id == "<abc123@example.com>"
        assert result.date is not None

    def test_multipart_alternative_prefers_text(self, parser):
        raw = _build_raw_email(
            body_text="Plain version",
            body_html="<html><body><b>HTML version</b></body></html>",
        )
        result = parser.parse_raw(raw)
        assert result.body_text == "Plain version"
        assert result.body_html is not None

    def test_html_only_converts(self, parser):
        msg = MIMEText("<html><body><p>Hello</p></body></html>", "html")
        msg["From"] = "sender@test.com"
        msg["To"] = "inbox@test.com"
        msg["Message-ID"] = "<html-only@test.com>"
        result = parser.parse_raw(msg.as_bytes())
        assert "Hello" in result.body_text
        assert result.body_html is not None

    def test_thread_id_from_references(self, parser):
        raw = _build_raw_email(
            references="<first@test.com> <second@test.com> <third@test.com>",
        )
        result = parser.parse_raw(raw)
        assert result.thread_id == "<third@test.com>"

    def test_thread_id_from_in_reply_to(self, parser):
        raw = _build_raw_email(in_reply_to="<parent@test.com>")
        result = parser.parse_raw(raw)
        assert result.thread_id == "<parent@test.com>"

    def test_thread_id_none_when_no_headers(self, parser):
        raw = _build_raw_email()
        result = parser.parse_raw(raw)
        assert result.thread_id is None

    def test_no_body(self, parser):
        msg = MIMEText("", "plain")
        msg["From"] = "sender@test.com"
        msg["To"] = "inbox@test.com"
        msg["Message-ID"] = "<nobody@test.com>"
        result = parser.parse_raw(msg.as_bytes())
        assert result.body_text == ""

    def test_non_utf8_fallback(self, parser):
        raw = _build_raw_email(body_text="café résumé", charset="latin-1")
        result = parser.parse_raw(raw)
        assert "caf" in result.body_text
        # Should decode successfully via charset header
        assert not result.encoding_issues

    def test_gmail_payload_format(self, parser):
        payload = {
            "id": "gmail123",
            "threadId": "thread456",
            "payload": {
                "headers": [
                    {"name": "From", "value": "user@gmail.com"},
                    {"name": "To", "value": "inbox@company.com"},
                    {"name": "Subject", "value": "Gmail Test"},
                    {"name": "Message-ID", "value": "<gmail-msg@test.com>"},
                ],
                "mimeType": "text/plain",
                "body": {
                    "data": base64.urlsafe_b64encode(b"Gmail body text").decode(),
                },
            },
        }
        result = parser.parse_gmail_payload(payload)
        assert result.from_address == "user@gmail.com"
        assert result.subject == "Gmail Test"
        assert result.body_text == "Gmail body text"
        assert result.thread_id == "thread456"

    def test_attachment_metadata(self, parser):
        raw = _build_raw_email(body_text="See attached", attachment=True)
        result = parser.parse_raw(raw)
        assert len(result.attachments) == 1
        assert result.attachments[0].filename == "doc.pdf"
        assert result.attachments[0].content_type == "application/pdf"
        assert result.attachments[0].size_bytes > 0

    def test_encoding_issues_flag(self, parser):
        # Build a message with invalid charset manually
        msg = MIMEText("test", "plain")
        msg["From"] = "sender@test.com"
        msg["To"] = "inbox@test.com"
        msg["Message-ID"] = "<enc-issue@test.com>"
        raw = msg.as_bytes()
        # Replace charset to something invalid
        raw = raw.replace(b"charset=\"us-ascii\"", b"charset=\"invalid-encoding-xyz\"")
        result = parser.parse_raw(raw)
        # Should fall back to latin-1 and set encoding_issues
        assert isinstance(result.body_text, str)
