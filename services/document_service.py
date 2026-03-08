"""TDS/SDS document storage, text extraction, and structured field parsing."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/documents")

TDS_EXTRACTION_PROMPT = """Extract the following fields from this Technical Data Sheet text.
Return JSON with keys: appearance, density, flash_point, pH, viscosity,
storage_conditions, melting_point, boiling_point, solubility, molecular_weight.
Omit keys if data is not present. Text:

{text}"""

SDS_EXTRACTION_PROMPT = """Extract the following fields from this Safety Data Sheet text.
Return JSON with keys: ghs_classification, cas_numbers (list), un_number,
hazard_statements (list), precautionary_statements (list), first_aid,
ppe_requirements, storage_requirements, disposal_methods.
Omit keys if data is not present. Text:

{text}"""

TDS_CONFIDENCE_PROMPT = """Extract ALL of the following fields from this Technical Data Sheet.
For each field, return a JSON object with "value" and "confidence" (0.0-1.0).
Confidence reflects how certain you are the extracted value is correct.
If a field is not found, return {{"value": null, "confidence": 0.0}}.

Fields to extract:
- appearance, color, odor, density, viscosity, pH, flash_point
- boiling_point, melting_point, solubility, molecular_weight
- shelf_life, storage_conditions, recommended_uses (list)

Return ONLY valid JSON object. No markdown.

Text:
{text}"""

SDS_CONFIDENCE_PROMPT = """Extract ALL of the following fields from this Safety Data Sheet.
For each field, return a JSON object with "value" and "confidence" (0.0-1.0).
Confidence reflects how certain you are the extracted value is correct.
If a field is not found, return {{"value": null, "confidence": 0.0}}.

Fields to extract:
- ghs_classification, hazard_statements (list), precautionary_statements (list)
- cas_numbers (list), un_number, dot_class
- first_aid, fire_fighting, ppe_requirements
- environmental_hazards, disposal_methods, transport_info

Return ONLY valid JSON object. No markdown.

Text:
{text}"""


class DocumentService:
    def __init__(self, db_manager, ai_service=None):
        self._db = db_manager
        self._ai = ai_service

    async def store_document(self, product_id: str, doc_type: str,
                             file_bytes: bytes, file_name: str,
                             source_url: str | None = None) -> dict:
        """Save document file to disk and insert metadata into documents table."""
        doc_dir = DATA_DIR / product_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = str(doc_dir / f"{doc_type}_{file_name}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO documents (product_id, doc_type, file_path, file_name,
                   file_size_bytes, source_url)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   RETURNING id, product_id, doc_type, file_path, file_name,
                   file_size_bytes, is_current, created_at""",
                product_id, doc_type, file_path, file_name,
                len(file_bytes), source_url,
            )
        return dict(row)

    async def extract_tds_fields_with_confidence(self, text: str) -> dict:
        """Extract TDS fields with per-field confidence scores."""
        return await self._call_llm(TDS_CONFIDENCE_PROMPT.format(text=text[:8000]))

    async def extract_sds_fields_with_confidence(self, text: str) -> dict:
        """Extract SDS fields with per-field confidence scores."""
        return await self._call_llm(SDS_CONFIDENCE_PROMPT.format(text=text[:8000]))

    async def extract_tds_fields(self, text: str) -> dict:
        """Use LLM to extract structured TDS fields from raw text."""
        return await self._call_llm(TDS_EXTRACTION_PROMPT.format(text=text[:8000]))

    async def extract_sds_fields(self, text: str) -> dict:
        """Use LLM to extract structured SDS fields from raw text."""
        return await self._call_llm(SDS_EXTRACTION_PROMPT.format(text=text[:8000]))

    async def get_documents_for_product(self, product_id: str) -> list[dict]:
        """Return current TDS/SDS documents for a product."""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, doc_type, file_name, file_path, is_current, created_at
                   FROM documents
                   WHERE product_id = $1 AND is_current = TRUE
                   ORDER BY doc_type""",
                product_id,
            )
        return [dict(r) for r in rows]

    async def get_document_by_id(self, doc_id: str) -> dict | None:
        """Get a single document by ID."""
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE id = $1", doc_id,
            )
        return dict(row) if row else None

    async def search_documents(self, query: str, doc_type: str | None = None,
                               limit: int = 20) -> list[dict]:
        """Search documents by keyword in file_name or product_id."""
        conditions = ["(file_name ILIKE $1 OR product_id ILIKE $1)"]
        params = [f"%{query}%"]
        idx = 2
        if doc_type:
            conditions.append(f"doc_type = ${idx}")
            params.append(doc_type)
            idx += 1
        params.append(limit)
        sql = f"""SELECT id, product_id, doc_type, file_name, is_current, created_at
                  FROM documents
                  WHERE {' AND '.join(conditions)}
                  ORDER BY created_at DESC LIMIT ${idx}"""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]

    async def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF bytes using pdfplumber."""
        import pdfplumber
        import io
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    async def _call_llm(self, prompt: str) -> dict:
        """Call AI service and parse JSON response."""
        if self._ai is None:
            raise RuntimeError("AI service not configured")
        raw = await self._ai.chat(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        return json.loads(cleaned)
