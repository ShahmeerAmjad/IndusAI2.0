"""Tests for services.email.pii_scanner — regex PII detection and redaction."""

import pytest

from services.email.pii_scanner import PIIScanner, ScanResult


@pytest.fixture
def scanner():
    return PIIScanner()


class TestPIIScanner:
    def test_email_detected_and_redacted(self, scanner):
        result = scanner.scan("Contact me at john@example.com for details.")
        assert "email" in result.detected_types
        assert "[EMAIL REDACTED]" in result.redacted_text
        assert "john@example.com" not in result.redacted_text

    def test_phone_us_detected(self, scanner):
        result = scanner.scan("Call us at (555) 123-4567 today.")
        assert "phone_us" in result.detected_types
        assert "[PHONE REDACTED]" in result.redacted_text

    def test_ssn_detected(self, scanner):
        result = scanner.scan("SSN: 123-45-6789")
        assert "ssn" in result.detected_types
        assert "[SSN REDACTED]" in result.redacted_text
        assert "123-45-6789" not in result.redacted_text

    def test_credit_card_detected(self, scanner):
        result = scanner.scan("Card: 4111 1111 1111 1111")
        assert "credit_card" in result.detected_types
        assert "[CREDIT CARD REDACTED]" in result.redacted_text

    def test_cas_number_excluded_by_default(self, scanner):
        result = scanner.scan("CAS 7732-18-5 is water.")
        assert "cas_number" in result.detected_types
        # CAS should NOT be redacted by default
        assert "7732-18-5" in result.redacted_text
        assert result.redaction_count == 0

    def test_cas_number_redacted_when_requested(self, scanner):
        result = scanner.scan("CAS 7732-18-5 is water.", exclude_types=set())
        assert "cas_number" in result.detected_types
        assert "[CAS NUMBER REDACTED]" in result.redacted_text
        assert result.redaction_count > 0

    def test_no_pii_passthrough(self, scanner):
        text = "This is a normal message with no PII."
        result = scanner.scan(text)
        assert result.redacted_text == text
        assert result.detected_types == []
        assert result.redaction_count == 0

    def test_multiple_types_in_one_string(self, scanner):
        text = "Email john@test.com, call 555-123-4567, SSN 123-45-6789"
        result = scanner.scan(text)
        assert "email" in result.detected_types
        assert "phone_us" in result.detected_types
        assert "ssn" in result.detected_types
        assert result.redaction_count >= 3

    def test_empty_input(self, scanner):
        result = scanner.scan("")
        assert result.redacted_text == ""
        assert result.detected_types == []
        assert result.redaction_count == 0

    def test_redaction_count_accuracy(self, scanner):
        text = "Email a@b.com and c@d.com"
        result = scanner.scan(text)
        assert result.redaction_count == 2
        assert result.redacted_text.count("[EMAIL REDACTED]") == 2
