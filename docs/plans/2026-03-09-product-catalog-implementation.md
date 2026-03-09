# Product Catalog with Document Explorer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a table-driven Product Catalog page with expandable accordion rows showing extracted TDS/SDS fields, and a slide-out drawer for full extraction detail with confidence scores.

**Architecture:** Enhance existing `/products` page to a filterable table. Add two new backend endpoints (extraction detail + filter values). Reuse existing Neo4j graph queries and TDSSDSViewer component patterns.

**Tech Stack:** React + TypeScript + Tailwind CSS (frontend), FastAPI + Neo4j + asyncpg (backend), react-query for data fetching.

---

### Task 1: Backend — Add filters endpoint

**Files:**
- Modify: `services/knowledge_base_service.py`
- Modify: `routes/knowledge_base.py`
- Test: `tests/test_knowledge_base.py`

**Step 1: Write the failing test**

In `tests/test_knowledge_base.py` (create if needed):

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.knowledge_base_service import KnowledgeBaseService


@pytest.mark.asyncio
async def test_get_filters_returns_manufacturers_and_industries():
    mock_graph = MagicMock()
    mock_graph.execute_read = AsyncMock(side_effect=[
        [{"name": "Dow"}, {"name": "BASF"}],  # manufacturers
        [{"name": "Adhesives"}, {"name": "Coatings"}],  # industries
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    result = await svc.get_filters()
    assert result == {
        "manufacturers": ["BASF", "Dow"],
        "industries": ["Adhesives", "Coatings"],
    }
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge_base.py::test_get_filters_returns_manufacturers_and_industries -v`
Expected: FAIL — `AttributeError: 'KnowledgeBaseService' has no attribute 'get_filters'`

**Step 3: Implement get_filters in KnowledgeBaseService**

Add to `services/knowledge_base_service.py` at end of class:

```python
async def get_filters(self) -> dict:
    """Return available filter values for the product catalog."""
    mfr_results = await self._graph.execute_read(
        "MATCH (m:Manufacturer) RETURN m.name AS name ORDER BY m.name", {}
    )
    ind_results = await self._graph.execute_read(
        "MATCH (i:Industry) RETURN i.name AS name ORDER BY i.name", {}
    )
    return {
        "manufacturers": [r["name"] for r in mfr_results],
        "industries": [r["name"] for r in ind_results],
    }
```

**Step 4: Add the route**

Add to `routes/knowledge_base.py` after the `list_products` route:

```python
@router.get("/filters")
async def get_filters():
    """Return available manufacturers and industries for filter dropdowns."""
    svc = _get_svc()
    return await svc.get_filters()
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_knowledge_base.py::test_get_filters_returns_manufacturers_and_industries -v`
Expected: PASS

**Step 6: Commit**

```bash
git add services/knowledge_base_service.py routes/knowledge_base.py tests/test_knowledge_base.py
git commit -m "feat: add /knowledge-base/filters endpoint for manufacturer/industry dropdowns"
```

---

### Task 2: Backend — Add extraction detail endpoint

**Files:**
- Modify: `services/knowledge_base_service.py`
- Modify: `routes/knowledge_base.py`
- Modify: `tests/test_knowledge_base.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_get_product_extraction_returns_tds_sds_fields():
    mock_graph = MagicMock()
    mock_graph.execute_read = AsyncMock(side_effect=[
        [{"props": {"appearance": {"value": "Clear liquid", "confidence": 0.95}}}],  # TDS
        [{"props": {"ghs_classification": {"value": "Flam. Liq. 3", "confidence": 0.9}}}],  # SDS
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    result = await svc.get_product_extraction("SKU-001")
    assert result["sku"] == "SKU-001"
    assert "appearance" in result["tds"]["fields"]
    assert result["tds"]["fields"]["appearance"]["confidence"] == 0.95
    assert "ghs_classification" in result["sds"]["fields"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge_base.py::test_get_product_extraction_returns_tds_sds_fields -v`
Expected: FAIL — no `get_product_extraction` method

**Step 3: Implement get_product_extraction**

Add to `services/knowledge_base_service.py`:

```python
async def get_product_extraction(self, sku: str) -> dict:
    """Return full TDS + SDS extracted fields for a product from Neo4j."""
    tds_results = await self._graph.execute_read(
        "MATCH (:Part {sku: $sku})-[:HAS_TDS]->(t:TechnicalDataSheet) RETURN t {.*} AS props",
        {"sku": sku},
    )
    sds_results = await self._graph.execute_read(
        "MATCH (:Part {sku: $sku})-[:HAS_SDS]->(s:SafetyDataSheet) RETURN s {.*} AS props",
        {"sku": sku},
    )

    tds_props = tds_results[0]["props"] if tds_results else {}
    sds_props = sds_results[0]["props"] if sds_results else {}

    # Separate metadata from extracted fields
    tds_meta_keys = {"product_sku", "revision_date", "pdf_url"}
    sds_meta_keys = {"product_sku", "revision_date", "pdf_url", "cas_numbers"}

    tds_fields = {k: v for k, v in tds_props.items() if k not in tds_meta_keys}
    sds_fields = {k: v for k, v in sds_props.items() if k not in sds_meta_keys}

    return {
        "sku": sku,
        "tds": {
            "fields": tds_fields,
            "pdf_url": tds_props.get("pdf_url"),
            "revision_date": tds_props.get("revision_date"),
        },
        "sds": {
            "fields": sds_fields,
            "pdf_url": sds_props.get("pdf_url"),
            "revision_date": sds_props.get("revision_date"),
            "cas_numbers": sds_props.get("cas_numbers", []),
        },
    }
```

**Step 4: Add the route**

Add to `routes/knowledge_base.py`:

```python
@router.get("/products/{product_id}/extraction")
async def get_product_extraction(product_id: str):
    """Return full TDS + SDS extracted fields with confidence scores."""
    svc = _get_svc()
    result = await svc.get_product_extraction(product_id)
    return result
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_knowledge_base.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add services/knowledge_base_service.py routes/knowledge_base.py tests/test_knowledge_base.py
git commit -m "feat: add /knowledge-base/products/{sku}/extraction endpoint for TDS/SDS detail"
```

---

### Task 3: Backend — Enhance list_products with manufacturer/industry/doc filters

**Files:**
- Modify: `services/knowledge_base_service.py` (list_products method)
- Modify: `routes/knowledge_base.py` (list_products route)
- Modify: `tests/test_knowledge_base.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_list_products_with_manufacturer_filter():
    mock_graph = MagicMock()
    mock_graph.execute_read = AsyncMock(side_effect=[
        [{"total": 1}],
        [{"p": {"sku": "X-1", "name": "Epoxy A"}, "manufacturer": "Dow",
          "industries": ["Adhesives"], "has_tds": True, "has_sds": False}],
    ])
    svc = KnowledgeBaseService(pool=None, graph_service=mock_graph)
    result = await svc.list_products(page=1, page_size=25, manufacturer="Dow")
    assert result["total"] == 1
    assert result["items"][0]["manufacturer"] == "Dow"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge_base.py::test_list_products_with_manufacturer_filter -v`
Expected: FAIL — `list_products() got an unexpected keyword argument 'manufacturer'`

**Step 3: Enhance list_products**

Replace the `list_products` method in `services/knowledge_base_service.py`:

```python
async def list_products(self, page: int = 1, page_size: int = 25,
                        search: str | None = None,
                        manufacturer: str | None = None,
                        industry: str | None = None,
                        has_tds: bool | None = None,
                        has_sds: bool | None = None) -> dict:
    """List Part nodes with optional search, manufacturer, industry, and doc filters."""
    skip = (page - 1) * page_size
    params: dict = {"skip": skip, "limit": page_size}

    # Build WHERE conditions
    conditions = []
    if search:
        conditions.append(
            "(toLower(p.name) CONTAINS toLower($search)"
            " OR toLower(p.sku) CONTAINS toLower($search)"
            " OR toLower(p.cas_number) CONTAINS toLower($search))"
        )
        params["search"] = search
    if manufacturer:
        conditions.append("m.name = $manufacturer")
        params["manufacturer"] = manufacturer
    if industry:
        conditions.append("i.name = $industry")
        params["industry"] = industry

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Optional TDS/SDS existence filters applied in WITH
    having = []
    if has_tds is True:
        having.append("has_tds = true")
    elif has_tds is False:
        having.append("has_tds = false")
    if has_sds is True:
        having.append("has_sds = true")
    elif has_sds is False:
        having.append("has_sds = false")
    having_clause = f"WHERE {' AND '.join(having)}" if having else ""

    base = f"""
    MATCH (p:Part)
    OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
    OPTIONAL MATCH (p)-[:SERVES_INDUSTRY]->(i:Industry)
    OPTIONAL MATCH (p)-[:HAS_TDS]->(t:TechnicalDataSheet)
    OPTIONAL MATCH (p)-[:HAS_SDS]->(s:SafetyDataSheet)
    {where}
    WITH p, m.name AS manufacturer,
         collect(DISTINCT i.name) AS industries,
         count(DISTINCT t) > 0 AS has_tds,
         count(DISTINCT s) > 0 AS has_sds
    {having_clause}
    """

    count_query = base + "\nRETURN count(p) AS total"
    count_params = {k: v for k, v in params.items() if k not in ("skip", "limit")}
    count_result = await self._graph.execute_read(count_query, count_params)
    total = count_result[0]["total"] if count_result else 0

    data_query = base + """
    RETURN p {.*} AS product, manufacturer, industries, has_tds, has_sds
    ORDER BY p.name
    SKIP $skip LIMIT $limit
    """
    results = await self._graph.execute_read(data_query, params)

    items = []
    for row in results:
        item = dict(row["product"])
        item["manufacturer"] = row.get("manufacturer")
        item["industries"] = row.get("industries", [])
        item["has_tds"] = row.get("has_tds", False)
        item["has_sds"] = row.get("has_sds", False)
        items.append(item)

    return {"items": items, "page": page, "page_size": page_size, "total": total}
```

**Step 4: Update the route**

Update `list_products` route in `routes/knowledge_base.py`:

```python
@router.get("/products")
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    has_tds: Optional[bool] = Query(None),
    has_sds: Optional[bool] = Query(None),
):
    """Paginated product list from the knowledge graph with filters."""
    svc = _get_svc()
    result = await svc.list_products(
        page=page, page_size=page_size, search=search,
        manufacturer=manufacturer, industry=industry,
        has_tds=has_tds, has_sds=has_sds,
    )
    return result
```

**Step 5: Run tests**

Run: `pytest tests/test_knowledge_base.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add services/knowledge_base_service.py routes/knowledge_base.py tests/test_knowledge_base.py
git commit -m "feat: add manufacturer/industry/doc-status filters to product list endpoint"
```

---

### Task 4: Frontend — Add API functions for new endpoints

**Files:**
- Modify: `src/lib/api.ts`

**Step 1: Add types and API functions**

Add these types to `src/lib/api.ts` after the existing types section:

```typescript
export interface CatalogProduct {
  sku: string;
  name: string;
  description?: string;
  manufacturer?: string;
  cas_number?: string;
  industries: string[];
  has_tds: boolean;
  has_sds: boolean;
  source?: string;
}

export interface CatalogFilters {
  manufacturers: string[];
  industries: string[];
}

export interface ExtractionField {
  value: string | number | string[] | null;
  confidence: number;
}

export interface ProductExtraction {
  sku: string;
  tds: {
    fields: Record<string, ExtractionField | string | number | null>;
    pdf_url?: string;
    revision_date?: string;
  };
  sds: {
    fields: Record<string, ExtractionField | string | number | null>;
    pdf_url?: string;
    revision_date?: string;
    cas_numbers?: string[];
  };
}
```

Add these functions to the `api` object:

```typescript
// Product Catalog (enhanced)
getCatalogProducts: (params: {
  page?: number; pageSize?: number; search?: string;
  manufacturer?: string; industry?: string;
  has_tds?: boolean; has_sds?: boolean;
} = {}) => {
  const p = new URLSearchParams();
  if (params.page) p.set("page", String(params.page));
  if (params.pageSize) p.set("page_size", String(params.pageSize));
  if (params.search) p.set("search", params.search);
  if (params.manufacturer) p.set("manufacturer", params.manufacturer);
  if (params.industry) p.set("industry", params.industry);
  if (params.has_tds !== undefined) p.set("has_tds", String(params.has_tds));
  if (params.has_sds !== undefined) p.set("has_sds", String(params.has_sds));
  const qs = p.toString();
  return get<{ items: CatalogProduct[]; page: number; page_size: number; total: number }>(
    `/knowledge-base/products${qs ? `?${qs}` : ""}`
  );
},

getCatalogFilters: () => get<CatalogFilters>("/knowledge-base/filters"),

getProductExtraction: (sku: string) =>
  get<ProductExtraction>(`/knowledge-base/products/${encodeURIComponent(sku)}/extraction`),
```

**Step 2: Commit**

```bash
git add src/lib/api.ts
git commit -m "feat: add API functions for catalog filters and extraction detail"
```

---

### Task 5: Frontend — Rewrite Products.tsx as filterable table with expandable rows

**Files:**
- Modify: `src/pages/Products.tsx`

**Step 1: Rewrite Products.tsx**

Replace entire file with a table layout. Key elements:
- Search bar (debounced)
- Three filter dropdowns: Manufacturer, Industry, Doc Status
- Table with columns: SKU, Product Name, Manufacturer, TDS (check/dash), SDS (check/dash), Industries
- Sortable column headers
- Click a row to toggle accordion expansion
- Expanded section: two-column TDS/SDS fields using existing `TDSSDSViewer` pattern
- "View Full Details" button in expanded section (opens drawer — Task 6)
- Pagination at bottom

```tsx
import { useQuery } from "@tanstack/react-query";
import { api, CatalogProduct } from "@/lib/api";
import { useState, useMemo, useCallback } from "react";
import { cn } from "@/lib/utils";
import {
  Search, ChevronDown, ChevronRight, Check, Minus,
  FileText, Shield, Download, ExternalLink,
} from "lucide-react";
import ProductDrawer from "@/components/products/ProductDrawer";

type DocFilter = "all" | "has_tds" | "has_sds" | "missing_tds" | "missing_sds";

export default function Products() {
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [manufacturer, setManufacturer] = useState("");
  const [industry, setIndustry] = useState("");
  const [docFilter, setDocFilter] = useState<DocFilter>("all");
  const [expandedSku, setExpandedSku] = useState<string | null>(null);
  const [drawerSku, setDrawerSku] = useState<string | null>(null);

  // Derive has_tds / has_sds from docFilter
  const filterParams = useMemo(() => {
    const p: { has_tds?: boolean; has_sds?: boolean } = {};
    if (docFilter === "has_tds") p.has_tds = true;
    if (docFilter === "has_sds") p.has_sds = true;
    if (docFilter === "missing_tds") p.has_tds = false;
    if (docFilter === "missing_sds") p.has_sds = false;
    return p;
  }, [docFilter]);

  const { data, isLoading } = useQuery({
    queryKey: ["catalog-products", page, appliedSearch, manufacturer, industry, docFilter],
    queryFn: () =>
      api.getCatalogProducts({
        page, pageSize: 25, search: appliedSearch || undefined,
        manufacturer: manufacturer || undefined,
        industry: industry || undefined,
        ...filterParams,
      }),
  });

  const { data: filters } = useQuery({
    queryKey: ["catalog-filters"],
    queryFn: () => api.getCatalogFilters(),
  });

  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    setAppliedSearch(search);
    setPage(1);
  }, [search]);

  const products = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 25));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-montserrat font-bold text-neutral-900">Product Catalog</h1>
        <p className="text-neutral-500 text-sm mt-1">
          {total.toLocaleString()} products — Parts, Manufacturers, TDS & SDS Documents
        </p>
      </div>

      {/* Search + Filters */}
      <div className="flex flex-wrap gap-3">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-[300px]">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
            <input
              type="text" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, SKU, or CAS number..."
              className="w-full pl-10 pr-4 py-2 border border-neutral-300 rounded-lg text-sm
                         focus:outline-none focus:ring-2 focus:ring-industrial-600 bg-white"
            />
          </div>
          <button type="submit"
            className="px-4 py-2 bg-industrial-800 text-white text-sm font-medium rounded-lg hover:bg-industrial-900">
            Search
          </button>
        </form>

        <select value={manufacturer} onChange={(e) => { setManufacturer(e.target.value); setPage(1); }}
          className="px-3 py-2 border border-neutral-300 rounded-lg text-sm bg-white min-w-[160px]">
          <option value="">All Manufacturers</option>
          {(filters?.manufacturers ?? []).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>

        <select value={industry} onChange={(e) => { setIndustry(e.target.value); setPage(1); }}
          className="px-3 py-2 border border-neutral-300 rounded-lg text-sm bg-white min-w-[140px]">
          <option value="">All Industries</option>
          {(filters?.industries ?? []).map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>

        <select value={docFilter} onChange={(e) => { setDocFilter(e.target.value as DocFilter); setPage(1); }}
          className="px-3 py-2 border border-neutral-300 rounded-lg text-sm bg-white min-w-[140px]">
          <option value="all">All Docs</option>
          <option value="has_tds">Has TDS</option>
          <option value="has_sds">Has SDS</option>
          <option value="missing_tds">Missing TDS</option>
          <option value="missing_sds">Missing SDS</option>
        </select>

        {(appliedSearch || manufacturer || industry || docFilter !== "all") && (
          <button onClick={() => { setSearch(""); setAppliedSearch(""); setManufacturer(""); setIndustry(""); setDocFilter("all"); setPage(1); }}
            className="px-3 py-2 border border-neutral-300 text-neutral-600 text-sm rounded-lg hover:bg-neutral-50">
            Clear All
          </button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-industrial-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-16 bg-neutral-50 rounded-lg border border-dashed border-neutral-300">
          <p className="text-neutral-500 text-sm">No products found.</p>
        </div>
      ) : (
        <div className="border border-neutral-200 rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-neutral-50 border-b border-neutral-200">
                <th className="w-8 px-3 py-3"></th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">SKU</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product Name</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Manufacturer</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">TDS</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">SDS</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Industries</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <ProductRow
                  key={product.sku}
                  product={product}
                  isExpanded={expandedSku === product.sku}
                  onToggle={() => setExpandedSku(expandedSku === product.sku ? null : product.sku)}
                  onViewDetails={() => setDrawerSku(product.sku)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <p className="text-sm text-neutral-500">Page {page} of {totalPages}</p>
          <div className="flex gap-2">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}
              className={cn("px-4 py-2 text-sm font-medium rounded-lg border",
                page <= 1 ? "border-neutral-200 text-neutral-300 cursor-not-allowed" : "border-neutral-300 text-neutral-700 hover:bg-neutral-50"
              )}>Previous</button>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
              className={cn("px-4 py-2 text-sm font-medium rounded-lg border",
                page >= totalPages ? "border-neutral-200 text-neutral-300 cursor-not-allowed" : "border-neutral-300 text-neutral-700 hover:bg-neutral-50"
              )}>Next</button>
          </div>
        </div>
      )}

      {/* Drawer */}
      {drawerSku && (
        <ProductDrawer sku={drawerSku} onClose={() => setDrawerSku(null)} />
      )}
    </div>
  );
}

/* ---- Expandable Row Sub-component ---- */

function ProductRow({ product, isExpanded, onToggle, onViewDetails }: {
  product: CatalogProduct;
  isExpanded: boolean;
  onToggle: () => void;
  onViewDetails: () => void;
}) {
  return (
    <>
      <tr onClick={onToggle}
        className={cn(
          "border-b border-neutral-100 cursor-pointer hover:bg-neutral-50 transition-colors",
          isExpanded && "bg-industrial-50"
        )}>
        <td className="px-3 py-3 text-neutral-400">
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </td>
        <td className="px-4 py-3">
          <span className="font-mono text-xs bg-industrial-100 text-industrial-800 px-2 py-0.5 rounded">
            {product.sku}
          </span>
        </td>
        <td className="px-4 py-3 font-medium text-neutral-900 max-w-[300px] truncate">{product.name}</td>
        <td className="px-4 py-3 text-neutral-600">{product.manufacturer || "—"}</td>
        <td className="px-4 py-3 text-center">
          {product.has_tds
            ? <Check size={16} className="inline text-blue-600" />
            : <Minus size={16} className="inline text-neutral-300" />}
        </td>
        <td className="px-4 py-3 text-center">
          {product.has_sds
            ? <Check size={16} className="inline text-red-600" />
            : <Minus size={16} className="inline text-neutral-300" />}
        </td>
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {(product.industries || []).slice(0, 3).map((ind) => (
              <span key={ind} className="text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">
                {ind}
              </span>
            ))}
            {(product.industries || []).length > 3 && (
              <span className="text-xs text-neutral-400">+{product.industries.length - 3}</span>
            )}
          </div>
        </td>
      </tr>

      {isExpanded && (
        <tr>
          <td colSpan={7} className="bg-neutral-50 border-b border-neutral-200 px-8 py-4">
            <ExpandedProductDetail sku={product.sku} onViewDetails={onViewDetails} />
          </td>
        </tr>
      )}
    </>
  );
}

/* ---- Expanded Accordion Content ---- */

function ExpandedProductDetail({ sku, onViewDetails }: { sku: string; onViewDetails: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["product-extraction", sku],
    queryFn: () => api.getProductExtraction(sku),
  });

  if (isLoading) {
    return <div className="text-sm text-neutral-400 py-2">Loading extraction data...</div>;
  }

  if (!data) {
    return <div className="text-sm text-neutral-400 py-2">No extraction data available.</div>;
  }

  const tdsFields = data.tds?.fields ?? {};
  const sdsFields = data.sds?.fields ?? {};

  return (
    <div className="space-y-3">
      <div className="grid gap-4 md:grid-cols-2">
        {/* TDS Summary */}
        <div className="rounded-lg border border-neutral-200 bg-white">
          <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <FileText size={14} className="text-blue-600" />
              <span className="text-sm font-semibold text-neutral-700">TDS Fields</span>
            </div>
            {data.tds?.pdf_url && (
              <a href={data.tds.pdf_url} target="_blank" rel="noreferrer"
                className="flex items-center gap-1 text-xs text-industrial-600 hover:underline">
                <Download size={12} /> PDF
              </a>
            )}
          </div>
          <div className="p-3">
            {Object.keys(tdsFields).length > 0 ? (
              <dl className="space-y-1.5 text-sm">
                {Object.entries(tdsFields).slice(0, 8).map(([key, val]) => {
                  const display = typeof val === "object" && val !== null && "value" in val
                    ? String((val as { value: unknown }).value ?? "—")
                    : String(val ?? "—");
                  if (display === "—" || display === "null") return null;
                  return (
                    <div key={key} className="flex justify-between gap-3">
                      <dt className="text-neutral-400 capitalize">{key.replace(/_/g, " ")}</dt>
                      <dd className="text-right font-medium text-neutral-700 truncate max-w-[200px]">{display}</dd>
                    </div>
                  );
                })}
              </dl>
            ) : (
              <p className="text-sm italic text-neutral-400">No TDS data extracted</p>
            )}
          </div>
        </div>

        {/* SDS Summary */}
        <div className="rounded-lg border border-neutral-200 bg-white">
          <div className="flex items-center justify-between border-b border-neutral-100 px-4 py-2.5">
            <div className="flex items-center gap-2">
              <Shield size={14} className="text-red-600" />
              <span className="text-sm font-semibold text-neutral-700">SDS Fields</span>
            </div>
            {data.sds?.pdf_url && (
              <a href={data.sds.pdf_url} target="_blank" rel="noreferrer"
                className="flex items-center gap-1 text-xs text-industrial-600 hover:underline">
                <Download size={12} /> PDF
              </a>
            )}
          </div>
          <div className="p-3">
            {Object.keys(sdsFields).length > 0 ? (
              <dl className="space-y-1.5 text-sm">
                {Object.entries(sdsFields).slice(0, 8).map(([key, val]) => {
                  const display = typeof val === "object" && val !== null && "value" in val
                    ? String((val as { value: unknown }).value ?? "—")
                    : String(val ?? "—");
                  if (display === "—" || display === "null") return null;
                  return (
                    <div key={key} className="flex justify-between gap-3">
                      <dt className="text-neutral-400 capitalize">{key.replace(/_/g, " ")}</dt>
                      <dd className="text-right font-medium text-neutral-700 truncate max-w-[200px]">{display}</dd>
                    </div>
                  );
                })}
              </dl>
            ) : (
              <p className="text-sm italic text-neutral-400">No SDS data extracted</p>
            )}
          </div>
        </div>
      </div>

      <button onClick={onViewDetails}
        className="flex items-center gap-1.5 text-sm text-industrial-600 hover:text-industrial-800 font-medium">
        <ExternalLink size={14} /> View Full Details
      </button>
    </div>
  );
}
```

**Step 2: Verify it builds**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add src/pages/Products.tsx
git commit -m "feat: rewrite Product Catalog as filterable table with expandable TDS/SDS rows"
```

---

### Task 6: Frontend — Create ProductDrawer component

**Files:**
- Create: `src/components/products/ProductDrawer.tsx`

**Step 1: Create the drawer component**

This slide-out panel shows:
- Product header (name, SKU, manufacturer, industries)
- Full TDS extraction with confidence badges (grouped by category)
- Full SDS extraction with confidence badges (grouped by GHS section)
- Document download links
- Close button

```tsx
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X, FileText, Shield, Download, ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface ProductDrawerProps {
  sku: string;
  onClose: () => void;
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const color = confidence >= 0.8
    ? "bg-green-100 text-green-700"
    : confidence >= 0.5
      ? "bg-yellow-100 text-yellow-700"
      : "bg-red-100 text-red-700";
  return (
    <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-medium", color)}>
      {Math.round(confidence * 100)}%
    </span>
  );
}

function FieldGroup({ title, fields, icon }: {
  title: string;
  fields: Record<string, unknown>;
  icon?: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  const entries = Object.entries(fields).filter(([, v]) => {
    if (v == null) return false;
    if (typeof v === "object" && v !== null && "value" in v) return (v as { value: unknown }).value != null;
    return true;
  });

  if (entries.length === 0) return null;

  return (
    <div className="border border-neutral-200 rounded-lg overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-neutral-50 hover:bg-neutral-100 transition-colors text-left">
        {icon}
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="text-sm font-semibold text-neutral-700">{title}</span>
        <span className="text-xs text-neutral-400 ml-auto">{entries.length} fields</span>
      </button>
      {open && (
        <dl className="p-4 space-y-2 text-sm">
          {entries.map(([key, val]) => {
            let display: string;
            let confidence: number | null = null;

            if (typeof val === "object" && val !== null && "value" in val) {
              const typed = val as { value: unknown; confidence?: number };
              display = Array.isArray(typed.value)
                ? typed.value.join(", ")
                : String(typed.value ?? "—");
              confidence = typed.confidence ?? null;
            } else if (Array.isArray(val)) {
              display = val.join(", ");
            } else {
              display = String(val);
            }

            return (
              <div key={key} className="flex items-start justify-between gap-3">
                <dt className="text-neutral-400 capitalize shrink-0">{key.replace(/_/g, " ")}</dt>
                <dd className="text-right font-medium text-neutral-700 flex items-center gap-2">
                  <span className="break-words max-w-[280px]">{display}</span>
                  {confidence !== null && <ConfidenceBadge confidence={confidence} />}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </div>
  );
}

// Group TDS fields by category
const TDS_GROUPS: Record<string, string[]> = {
  "Physical Properties": [
    "appearance", "color", "odor", "form", "density", "specific_gravity",
    "bulk_density", "viscosity", "pH", "molecular_weight",
  ],
  "Thermal Properties": [
    "flash_point", "boiling_point", "melting_point", "glass_transition_temp",
    "vapor_pressure", "refractive_index",
  ],
  "Mechanical Properties": [
    "tensile_strength", "elongation", "hardness", "impact_strength",
    "adhesion_strength", "peel_strength", "shear_strength",
    "heat_deflection_temp", "thermal_conductivity",
  ],
  "Application": [
    "recommended_uses", "application_method", "application_temperature",
    "mix_ratio", "cure_time", "pot_life", "open_time", "set_time",
    "compatibility", "solubility", "particle_size",
  ],
  "Storage & Regulatory": [
    "shelf_life", "storage_conditions", "storage_temperature",
    "packaging", "regulatory_approvals", "product_name", "manufacturer",
    "product_line", "revision_date",
  ],
};

// Group SDS fields by GHS section
const SDS_GROUPS: Record<string, string[]> = {
  "Identification (Sec 1)": ["product_name", "supplier", "emergency_phone", "revision_date", "sds_number"],
  "Hazard Identification (Sec 2)": [
    "ghs_classification", "signal_word", "hazard_pictograms",
    "hazard_statements", "precautionary_statements",
  ],
  "Composition (Sec 3)": ["components", "cas_numbers"],
  "First Aid (Sec 4)": [
    "first_aid_inhalation", "first_aid_skin", "first_aid_eyes", "first_aid_ingestion",
  ],
  "PPE & Exposure (Sec 8)": [
    "exposure_limits", "respiratory_protection", "hand_protection",
    "eye_protection", "skin_protection",
  ],
  "Physical Properties (Sec 9)": [
    "appearance", "color", "odor", "pH", "density", "viscosity",
    "boiling_point", "flash_point", "vapor_pressure", "solubility",
  ],
  "Stability (Sec 10)": ["stability", "incompatible_materials", "decomposition_products"],
  "Toxicology (Sec 11)": [
    "ld50_oral", "lc50_inhalation", "skin_corrosion", "eye_damage",
    "carcinogenicity", "reproductive_toxicity", "mutagenicity",
  ],
  "Transport (Sec 14)": ["un_number", "shipping_name", "hazard_class", "packing_group"],
  "Regulatory (Sec 15)": ["sara_313", "california_prop_65", "cercla_rq"],
};

function groupFields(allFields: Record<string, unknown>, groups: Record<string, string[]>) {
  const grouped: Record<string, Record<string, unknown>> = {};
  const assigned = new Set<string>();

  for (const [groupName, keys] of Object.entries(groups)) {
    const g: Record<string, unknown> = {};
    for (const k of keys) {
      if (k in allFields) {
        g[k] = allFields[k];
        assigned.add(k);
      }
    }
    if (Object.keys(g).length > 0) {
      grouped[groupName] = g;
    }
  }

  // Ungrouped fields
  const other: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(allFields)) {
    if (!assigned.has(k)) other[k] = v;
  }
  if (Object.keys(other).length > 0) {
    grouped["Other"] = other;
  }

  return grouped;
}

export default function ProductDrawer({ sku, onClose }: ProductDrawerProps) {
  const { data: product } = useQuery({
    queryKey: ["catalog-product-detail", sku],
    queryFn: () => api.searchProducts(sku, 1, 1),
  });

  const { data: extraction, isLoading } = useQuery({
    queryKey: ["product-extraction", sku],
    queryFn: () => api.getProductExtraction(sku),
  });

  const productInfo = product?.items?.[0];

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-white shadow-2xl z-50 flex flex-col
                      animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-neutral-200 px-6 py-4">
          <div>
            <span className="font-mono text-xs bg-industrial-100 text-industrial-800 px-2 py-0.5 rounded">
              {sku}
            </span>
            <h2 className="text-lg font-semibold text-neutral-900 mt-1">
              {productInfo?.name || sku}
            </h2>
            {productInfo?.manufacturer && (
              <p className="text-sm text-neutral-500 mt-0.5">{productInfo.manufacturer}</p>
            )}
          </div>
          <button onClick={onClose}
            className="p-1.5 hover:bg-neutral-100 rounded-lg transition-colors">
            <X size={20} className="text-neutral-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="w-6 h-6 border-2 border-industrial-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : extraction ? (
            <>
              {/* TDS Section */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <FileText size={16} className="text-blue-600" />
                    <h3 className="font-semibold text-neutral-800">Technical Data Sheet</h3>
                  </div>
                  {extraction.tds?.pdf_url && (
                    <a href={extraction.tds.pdf_url} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1 text-xs bg-blue-50 text-blue-700 px-2.5 py-1 rounded-md hover:bg-blue-100">
                      <Download size={12} /> Open PDF
                    </a>
                  )}
                </div>
                {extraction.tds?.revision_date && (
                  <p className="text-xs text-neutral-400 mb-2">Revision: {extraction.tds.revision_date}</p>
                )}
                <div className="space-y-2">
                  {Object.entries(groupFields(extraction.tds?.fields ?? {}, TDS_GROUPS)).map(
                    ([groupName, fields]) => (
                      <FieldGroup key={groupName} title={groupName} fields={fields}
                        icon={<FileText size={12} className="text-blue-400" />} />
                    )
                  )}
                  {Object.keys(extraction.tds?.fields ?? {}).length === 0 && (
                    <p className="text-sm italic text-neutral-400">No TDS extraction data</p>
                  )}
                </div>
              </div>

              {/* SDS Section */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Shield size={16} className="text-red-600" />
                    <h3 className="font-semibold text-neutral-800">Safety Data Sheet</h3>
                  </div>
                  {extraction.sds?.pdf_url && (
                    <a href={extraction.sds.pdf_url} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1 text-xs bg-red-50 text-red-700 px-2.5 py-1 rounded-md hover:bg-red-100">
                      <Download size={12} /> Open PDF
                    </a>
                  )}
                </div>
                {extraction.sds?.revision_date && (
                  <p className="text-xs text-neutral-400 mb-2">Revision: {extraction.sds.revision_date}</p>
                )}
                {extraction.sds?.cas_numbers && extraction.sds.cas_numbers.length > 0 && (
                  <p className="text-xs text-neutral-500 mb-2">
                    CAS: {extraction.sds.cas_numbers.join(", ")}
                  </p>
                )}
                <div className="space-y-2">
                  {Object.entries(groupFields(extraction.sds?.fields ?? {}, SDS_GROUPS)).map(
                    ([groupName, fields]) => (
                      <FieldGroup key={groupName} title={groupName} fields={fields}
                        icon={<Shield size={12} className="text-red-400" />} />
                    )
                  )}
                  {Object.keys(extraction.sds?.fields ?? {}).length === 0 && (
                    <p className="text-sm italic text-neutral-400">No SDS extraction data</p>
                  )}
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-neutral-400">No extraction data available for this product.</p>
          )}
        </div>
      </div>
    </>
  );
}
```

**Step 2: Verify it builds**

Run: `npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add src/components/products/ProductDrawer.tsx
git commit -m "feat: add ProductDrawer slide-out with grouped TDS/SDS fields and confidence badges"
```

---

### Task 7: Frontend — Update Sidebar navigation for Product Catalog

**Files:**
- Modify: `src/components/layout/Sidebar.tsx`

**Step 1: Verify Product Catalog is already in the sidebar**

The sidebar already has a "Product Catalog" entry linking to `/products`. Verify it exists and is in the "Products" group alongside "Knowledge Base". If the icon or label needs updating, make that change. The description should hint at the new capabilities: "Parts, TDS & SDS".

No code changes needed if the sidebar already links to `/products`. Just verify.

**Step 2: Commit (if changes needed)**

```bash
git add src/components/layout/Sidebar.tsx
git commit -m "chore: update sidebar Product Catalog label"
```

---

### Task 8: Integration test — verify end-to-end

**Files:**
- Modify: `tests/test_knowledge_base.py`

**Step 1: Add route-level tests**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_filters_route():
    """Test GET /api/v1/knowledge-base/filters returns manufacturers and industries."""
    from routes.knowledge_base import router, set_kb_service
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    mock_svc = MagicMock()
    mock_svc.get_filters = AsyncMock(return_value={
        "manufacturers": ["Dow", "BASF"],
        "industries": ["Adhesives"],
    })
    set_kb_service(mock_svc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/knowledge-base/filters")
    assert resp.status_code == 200
    data = resp.json()
    assert "Dow" in data["manufacturers"]
    assert "Adhesives" in data["industries"]


@pytest.mark.asyncio
async def test_extraction_route():
    """Test GET /api/v1/knowledge-base/products/{sku}/extraction."""
    from routes.knowledge_base import router, set_kb_service
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    mock_svc = MagicMock()
    mock_svc.get_product_extraction = AsyncMock(return_value={
        "sku": "TEST-001",
        "tds": {"fields": {"appearance": {"value": "Clear", "confidence": 0.9}}, "pdf_url": None, "revision_date": None},
        "sds": {"fields": {}, "pdf_url": None, "revision_date": None, "cas_numbers": []},
    })
    set_kb_service(mock_svc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/knowledge-base/products/TEST-001/extraction")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sku"] == "TEST-001"
    assert data["tds"]["fields"]["appearance"]["confidence"] == 0.9
```

**Step 2: Run all tests**

Run: `pytest tests/test_knowledge_base.py -v`
Expected: ALL PASS

**Step 3: Run frontend build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build`
Expected: Build succeeds with no errors

**Step 4: Commit**

```bash
git add tests/test_knowledge_base.py
git commit -m "test: add integration tests for filters and extraction endpoints"
```
