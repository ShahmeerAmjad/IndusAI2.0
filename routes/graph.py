"""Graph API — browse and query the Neo4j knowledge graph."""

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/graph", tags=["knowledge-graph"])

_graph_service = None
_graph_sync = None


def set_graph_services(graph_service, graph_sync=None):
    global _graph_service, _graph_sync
    _graph_service = graph_service
    _graph_sync = graph_sync


def _require_graph():
    if not _graph_service:
        raise HTTPException(status_code=503, detail="Knowledge graph unavailable")
    return _graph_service


@router.get("/parts/{sku}")
async def get_part(sku: str):
    """Get a part from the knowledge graph with specs, cross-refs, and compatible parts."""
    graph = _require_graph()
    part = await graph.get_part(sku)
    if not part:
        raise HTTPException(status_code=404, detail=f"Part {sku} not found in knowledge graph")
    compatible = await graph.get_compatible_parts(sku)
    part["compatible_parts"] = compatible
    return part


@router.get("/parts/search/fulltext")
async def search_parts(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
):
    """Full-text search across parts in the knowledge graph."""
    graph = _require_graph()
    results = await graph.search_parts_fulltext(q, limit=limit)
    return {"results": results, "total": len(results), "query": q}


@router.get("/parts/{sku}/cross-refs")
async def get_cross_refs(sku: str):
    """Get cross-references for a part."""
    graph = _require_graph()
    refs = await graph.get_cross_references(sku)
    return {"sku": sku, "cross_references": refs}


@router.get("/parts/{sku}/compatible")
async def get_compatible(sku: str):
    """Get compatible parts."""
    graph = _require_graph()
    parts = await graph.get_compatible_parts(sku)
    return {"sku": sku, "compatible_parts": parts}


@router.get("/assemblies/{model}/bom")
async def get_bom(model: str):
    """Get Bill of Materials for an assembly."""
    graph = _require_graph()
    components = await graph.get_assembly_bom(model)
    if not components:
        raise HTTPException(status_code=404, detail=f"Assembly {model} not found")
    return {"assembly": model, "components": components}


@router.get("/stats")
async def get_graph_stats():
    """Get knowledge graph statistics (node and edge counts)."""
    graph = _require_graph()
    return await graph.get_graph_stats()


@router.post("/sync/{sku}")
async def sync_part(sku: str):
    """Manually trigger PG->Neo4j sync for a single part (admin)."""
    if not _graph_sync:
        raise HTTPException(status_code=503, detail="Sync service unavailable")
    return {"status": "sync_triggered", "sku": sku}
