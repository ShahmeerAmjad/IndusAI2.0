"""Email ingestion pipeline — Gmail connector, parser, PII scanner, encryption."""

from services.email.encryption import FernetEncryption
from services.email.pii_scanner import PIIScanner, ScanResult
from services.email.parser import EmailParser, ParsedEmail, AttachmentMeta
from services.email.connector import EmailConnector, GmailConnector
from services.email.ingestion_service import (
    EmailIngestionService,
    set_ingestion_service,
    get_ingestion_service,
)

__all__ = [
    "FernetEncryption",
    "PIIScanner",
    "ScanResult",
    "EmailParser",
    "ParsedEmail",
    "AttachmentMeta",
    "EmailConnector",
    "GmailConnector",
    "EmailIngestionService",
    "set_ingestion_service",
    "get_ingestion_service",
]
