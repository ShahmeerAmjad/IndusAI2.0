"""TDS/SDS document storage, text extraction, and structured field parsing."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/documents")

TDS_EXTRACTION_PROMPT = """Extract ALL available fields from this Technical Data Sheet.
Return a JSON object. Omit keys where data is not present. Text:

{text}"""

SDS_EXTRACTION_PROMPT = """Extract ALL available fields from this Safety Data Sheet.
Return a JSON object. Omit keys where data is not present. Text:

{text}"""

TDS_CONFIDENCE_PROMPT = """Extract ALL of the following fields from this Technical Data Sheet.
For each field, return a JSON object with "value" and "confidence" (0.0-1.0).
Confidence reflects how certain you are the extracted value is correct.
If a field is not found, return {{"value": null, "confidence": 0.0}}.

PHYSICAL PROPERTIES:
- appearance, color, odor, form (solid/liquid/powder/pellet)
- density, specific_gravity, bulk_density
- viscosity, pH, molecular_weight
- flash_point, boiling_point, melting_point, glass_transition_temp
- solubility, vapor_pressure, particle_size, refractive_index

PERFORMANCE & APPLICATION:
- recommended_uses (list), application_method, application_temperature
- mix_ratio, cure_time, pot_life, open_time, set_time
- tensile_strength, elongation, hardness, impact_strength
- heat_deflection_temp, thermal_conductivity
- adhesion_strength, peel_strength, shear_strength
- compatibility (list of compatible substrates/materials)

STORAGE & HANDLING:
- shelf_life, storage_conditions, storage_temperature
- packaging (available sizes/containers)

REGULATORY & IDENTIFICATION:
- product_name, manufacturer, product_line
- regulatory_approvals (list: FDA, NSF, Kosher, Halal, etc.)
- revision_date

Return ONLY valid JSON object. No markdown.

Text:
{text}"""

SDS_CONFIDENCE_PROMPT = """Extract ALL of the following fields from this Safety Data Sheet.
For each field, return a JSON object with "value" and "confidence" (0.0-1.0).
Confidence reflects how certain you are the extracted value is correct.
If a field is not found, return {{"value": null, "confidence": 0.0}}.

IDENTIFICATION (Section 1):
- product_name, supplier, emergency_phone, revision_date, sds_number

HAZARD IDENTIFICATION (Section 2):
- ghs_classification (list), signal_word (Danger/Warning/None)
- hazard_pictograms (list of GHS codes, e.g. GHS05, GHS07)
- hazard_statements (list with H-codes, e.g. "H314 Causes severe skin burns")
- precautionary_statements (list with P-codes)

COMPOSITION (Section 3):
- components (list of objects: {{"name", "cas_number", "concentration"}})

FIRST AID (Section 4):
- first_aid_inhalation, first_aid_skin, first_aid_eyes, first_aid_ingestion

FIRE FIGHTING (Section 5):
- extinguishing_media, fire_fighting_equipment

PPE & EXPOSURE (Section 8):
- exposure_limits (list of objects: {{"substance", "type", "value"}})
- respiratory_protection, hand_protection, eye_protection, skin_protection

PHYSICAL PROPERTIES (Section 9):
- appearance, color, odor, pH, density, viscosity
- boiling_point, flash_point, vapor_pressure, solubility

STABILITY & REACTIVITY (Section 10):
- stability, incompatible_materials, decomposition_products

TOXICOLOGY (Section 11):
- ld50_oral, lc50_inhalation, skin_corrosion, eye_damage
- carcinogenicity, reproductive_toxicity, mutagenicity

ECOLOGY (Section 12):
- ecotoxicity_fish, ecotoxicity_daphnia, biodegradability, bioaccumulation

DISPOSAL (Section 13):
- disposal_methods

TRANSPORT (Section 14):
- un_number, shipping_name, hazard_class, packing_group

REGULATORY (Section 15):
- sara_313, california_prop_65, cercla_rq

Return ONLY valid JSON object. No markdown.

Text:
{text}"""


class DocumentService:
    def __init__(self, db_manager, ai_service=None):
        self._db = db_manager
        self._ai = ai_service

    async def store_document(self, product_id: str, doc_type: str,
                             file_bytes: bytes, file_name: str,
                             source_url: str | None = None,
                             content_format: str = "pdf") -> dict:
        """Save document file to disk and insert metadata into documents table.

        Args:
            content_format: 'pdf' for real PDF binary, 'markdown' for Firecrawl text fallback.
        """
        doc_dir = DATA_DIR / str(product_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        # Use appropriate extension based on content format
        ext = ".md" if content_format == "markdown" else ""
        file_path = str(doc_dir / f"{doc_type}_{file_name}{ext}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO documents (product_id, doc_type, file_path, file_name,
                   file_size_bytes, source_url, content_format)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING id, product_id, doc_type, file_path, file_name,
                   file_size_bytes, content_format, is_current, created_at""",
                product_id, doc_type, file_path, file_name,
                len(file_bytes), source_url, content_format,
            )
        return dict(row)

    async def extract_tds_fields_with_confidence(self, text: str) -> dict:
        """Extract TDS fields with per-field confidence scores."""
        return await self._call_llm(TDS_CONFIDENCE_PROMPT.format(text=text[:12000]))

    async def extract_sds_fields_with_confidence(self, text: str) -> dict:
        """Extract SDS fields with per-field confidence scores."""
        return await self._call_llm(SDS_CONFIDENCE_PROMPT.format(text=text[:12000]))

    async def extract_tds_fields(self, text: str) -> dict:
        """Use LLM to extract structured TDS fields from raw text."""
        return await self._call_llm(TDS_EXTRACTION_PROMPT.format(text=text[:12000]))

    async def extract_sds_fields(self, text: str) -> dict:
        """Use LLM to extract structured SDS fields from raw text."""
        return await self._call_llm(SDS_EXTRACTION_PROMPT.format(text=text[:12000]))

    async def get_documents_for_product(self, product_id: str) -> list[dict]:
        """Return current TDS/SDS documents for a product."""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, doc_type, file_name, file_path, content_format, source_url, is_current, created_at
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

    async def count_documents(self) -> dict:
        """Return total document count and breakdown by type."""
        async with self._db.pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM documents")
            rows = await conn.fetch(
                "SELECT doc_type, COUNT(*) AS cnt FROM documents GROUP BY doc_type"
            )
        by_type = {r["doc_type"]: r["cnt"] for r in rows}
        return {"total": total or 0, "tds": by_type.get("TDS", 0), "sds": by_type.get("SDS", 0)}

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
        raw = await self._ai.chat(
            messages=[{"role": "user", "content": prompt}],
            task="tds_extraction",
            max_tokens=8192,
            temperature=0.1,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        return json.loads(cleaned)
