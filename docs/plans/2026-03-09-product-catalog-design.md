# Product Catalog with Document Explorer — Design

**Date:** 2026-03-09
**Status:** Approved

## Problem

The current Knowledge Base page shows products with basic TDS/SDS indicators but lacks:
- A proper table-driven catalog view with filtering and sorting
- Visibility into extracted TDS/SDS fields (what the LLM actually pulled from PDFs)
- Ability to open/download actual documents from the UI
- Confidence scores on extraction quality
- Cross-referencing by manufacturer, industry, or document status

## Solution

Enhance the Product Catalog page (`/products`) with three layers of detail:

1. **Table view** — scannable, filterable, sortable
2. **Expandable row** — key extracted fields inline (accordion)
3. **Slide-out drawer** — full extraction detail with confidence scores and raw text

## UI Specification

### Layer 1: Table View

Columns:
| Column | Source | Sortable |
|--------|--------|----------|
| Part SKU | product.sku | Yes |
| Product Name | product.name | Yes |
| Manufacturer | product.manufacturer | Yes |
| TDS | green check / grey dash | Yes (has/missing) |
| SDS | green check / grey dash | Yes (has/missing) |
| Industries | comma-joined badges | No |

Controls:
- **Search bar** — filters by name, SKU, CAS number, manufacturer (debounced 300ms)
- **Manufacturer filter** — dropdown populated from API
- **Industry filter** — dropdown populated from API
- **Doc status filter** — "All", "Has TDS", "Has SDS", "Missing TDS", "Missing SDS"
- **Pagination** — page size 25, standard prev/next

### Layer 2: Expandable Row (Accordion)

Click a row to toggle. Two-column layout below the row:

**Left column — TDS Fields:**
- Appearance, Color, Odor, Form
- Density, Viscosity, pH, Flash Point
- Melting Point, Boiling Point, Solubility
- Storage Conditions, Shelf Life
- Download TDS button (if pdf_url exists)

**Right column — SDS Fields:**
- GHS Classification, Signal Word
- CAS Numbers, UN Number
- Hazard Statements (H-codes)
- Precautionary Statements (P-codes)
- PPE Requirements
- First Aid summary
- Download SDS button (if pdf_url exists)

Fields that are null/empty are hidden, not shown as "N/A".

### Layer 3: Slide-out Drawer

Triggered by "View Full Details" button in the expanded row. Slides in from the right, ~50% viewport width.

**Sections:**

1. **Product Header**
   - Name, SKU, manufacturer, category, description
   - Industries as colored badges

2. **TDS Extraction** (collapsible section groups)
   - Physical Properties: appearance, color, odor, form, density, viscosity, pH, etc.
   - Thermal Properties: flash point, melting point, boiling point, autoignition temp
   - Chemical Properties: solubility, molecular weight, vapor pressure
   - Application: recommended uses, application method, cure conditions
   - Storage: storage conditions, shelf life, packaging
   - Each field shows: label, value, confidence badge (green >=0.8, yellow >=0.5, red <0.5)

3. **SDS Extraction** (grouped by GHS sections 1-16)
   - Section 1: Identification
   - Section 2: Hazard Identification (GHS classification, signal word, hazard/precautionary statements)
   - Section 3: Composition (CAS numbers, concentrations)
   - Section 4: First Aid Measures
   - Section 5: Fire Fighting
   - Section 6: Accidental Release
   - Section 7: Handling and Storage
   - Section 8: Exposure Controls / PPE
   - Section 9: Physical/Chemical Properties
   - Sections 10-16: Stability, Toxicology, Ecological, Disposal, Transport, Regulatory, Other
   - Each field shows confidence badge

4. **Documents** (tab or section at bottom)
   - List of all document versions (current flagged)
   - Columns: Type, File Name, Size, Uploaded, Status (current/superseded)
   - Download button per document
   - Open in new tab button (if PDF)

5. **Raw Extraction** (collapsible, for debugging)
   - Raw text extracted from PDF via pdfplumber
   - Helps verify extraction quality

## Backend Changes

### New endpoint: `GET /api/v1/knowledge-base/products/{sku}/extraction`

Returns full TDS + SDS extracted fields with confidence scores from Neo4j.

```json
{
  "sku": "ABC-123",
  "tds": {
    "fields": {
      "appearance": {"value": "Clear liquid", "confidence": 0.95},
      "density": {"value": "1.05 g/cm³", "confidence": 0.88}
    },
    "pdf_url": "https://...",
    "revision_date": "2025-01-15"
  },
  "sds": {
    "fields": {
      "ghs_classification": {"value": "Flammable Liquid Cat 3", "confidence": 0.92},
      "cas_numbers": {"value": ["64-17-5"], "confidence": 0.99}
    },
    "pdf_url": "https://...",
    "revision_date": "2025-02-01"
  },
  "documents": [
    {"id": "uuid", "doc_type": "TDS", "file_name": "abc-tds.pdf", "file_size_bytes": 245000, "is_current": true, "created_at": "..."}
  ],
  "raw_text": {"tds": "...", "sds": "..."}
}
```

### Enhanced: `GET /api/v1/knowledge-base/products`

Add query params:
- `manufacturer` — filter by manufacturer name
- `industry` — filter by industry name
- `has_tds` — boolean filter
- `has_sds` — boolean filter

Response already includes basic TDS/SDS info; no change to shape needed.

### New endpoint: `GET /api/v1/knowledge-base/filters`

Returns available filter values:
```json
{
  "manufacturers": ["Dow", "BASF", "3M", ...],
  "industries": ["Adhesives", "Coatings", ...]
}
```

## Existing Components to Reuse

- `TDSSDSViewer` — adapt for the expandable row display
- `GraphExplorer` — unchanged, stays in Knowledge Base
- `IngestionPanel` — unchanged, stays in Knowledge Base
- `api.ts` — add new API functions

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/pages/Products.tsx` | Rewrite — table + expandable rows + drawer |
| `src/components/products/ProductDrawer.tsx` | New — slide-out detail drawer |
| `src/components/products/TDSSDSViewer.tsx` | Enhance — add confidence badges, grouped sections |
| `src/lib/api.ts` | Add new API functions |
| `routes/knowledge_base.py` | Add extraction + filters endpoints |
| `services/knowledge_base_service.py` | Add extraction + filter methods |

## Future: OCR Pipeline

Current extraction uses LLM (Claude) to parse PDF text. Future improvement:
- Add OCR option (e.g., Tesseract, Amazon Textract, or Google Document AI) for scanned PDFs
- Could be cheaper for high-volume extraction
- Architecture note: extraction is already behind `DocumentService.extract_tds_fields_with_confidence()` — swap implementation without changing callers
- Decision deferred until volume justifies cost comparison

## Non-Goals

- No inline PDF viewer (open in new tab is sufficient for MVP)
- No document editing/annotation
- No bulk document upload from this page (use Ingestion tab)
- No export to CSV/Excel from catalog (future)
