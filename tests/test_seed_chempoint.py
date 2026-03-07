"""Test the end-to-end pipeline: scrape → extract → build graph nodes."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_seed_pipeline_creates_product_and_tds():
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    mock_scraper = MagicMock()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "POLYOX WSR-301",
        "manufacturer": "Dow",
        "cas_number": "25322-68-3",
        "product_line": "POLYOX Water-Soluble Resins",
        "industries": ["Adhesives", "Pharma"],
        "tds_url": "https://chempoint.com/docs/tds.pdf",
        "sds_url": "https://chempoint.com/docs/sds.pdf",
    }])
    mock_scraper.download_document = AsyncMock(return_value=b"fake-pdf")

    mock_doc_service = MagicMock()
    mock_doc_service.store_document = AsyncMock(return_value={"id": "doc-1"})
    mock_doc_service.extract_text_from_pdf = AsyncMock(return_value="Appearance: White powder")
    mock_doc_service.extract_tds_fields = AsyncMock(return_value={"appearance": "White powder"})
    mock_doc_service.extract_sds_fields = AsyncMock(return_value={"cas_numbers": ["25322-68-3"]})

    mock_graph = MagicMock()
    mock_graph.create_tds = AsyncMock()
    mock_graph.create_sds = AsyncMock()
    mock_graph.link_product_to_industry = AsyncMock()
    mock_graph.link_product_to_product_line = AsyncMock()

    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={"id": "prod-1", "sku": "POLYOX-WSR-301"})
    ))
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    pipeline = ChempointSeedPipeline(
        scraper=mock_scraper,
        doc_service=mock_doc_service,
        graph_service=mock_graph,
        db_manager=mock_db,
    )
    result = await pipeline.seed_from_url("https://chempoint.com/products/polyox-wsr301")
    assert result["products_created"] >= 1
    mock_graph.create_tds.assert_called_once()
    mock_graph.create_sds.assert_called_once()
    assert mock_graph.link_product_to_industry.call_count == 2  # Adhesives + Pharma


def _make_pipeline(scraper_return=None, doc_fields=None, db_row=None):
    """Helper to build a ChempointSeedPipeline with mocked dependencies."""
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    mock_scraper = MagicMock()
    mock_scraper.scrape_product_page = AsyncMock(return_value=scraper_return or [])
    mock_scraper.scrape_industry_page = AsyncMock(return_value=[])
    mock_scraper.download_document = AsyncMock(return_value=b"fake-pdf")

    mock_doc = MagicMock()
    mock_doc.store_document = AsyncMock(return_value={"id": "doc-1"})
    mock_doc.extract_text_from_pdf = AsyncMock(return_value="some text")
    mock_doc.extract_tds_fields = AsyncMock(return_value=doc_fields or {"appearance": "White"})
    mock_doc.extract_sds_fields = AsyncMock(return_value=doc_fields or {"cas_numbers": ["123"]})

    mock_graph = MagicMock()
    mock_graph.create_tds = AsyncMock()
    mock_graph.create_sds = AsyncMock()
    mock_graph.link_product_to_industry = AsyncMock()
    mock_graph.link_product_to_product_line = AsyncMock()

    row = db_row or {"id": "prod-1", "sku": "TEST-SKU"}
    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value=row)
    ))
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    pipeline = ChempointSeedPipeline(
        scraper=mock_scraper,
        doc_service=mock_doc,
        graph_service=mock_graph,
        db_manager=mock_db,
    )
    return pipeline, mock_scraper, mock_doc, mock_graph, mock_db


@pytest.mark.asyncio
async def test_seed_from_url_scraper_returns_empty():
    pipeline, scraper, doc, graph, db = _make_pipeline(scraper_return=[])
    result = await pipeline.seed_from_url("https://chempoint.com/empty")
    assert result == {"products_created": 0, "tds_stored": 0, "sds_stored": 0, "industries_linked": 0}
    graph.create_tds.assert_not_called()
    graph.create_sds.assert_not_called()


@pytest.mark.asyncio
async def test_seed_from_url_tds_download_fails():
    """TDS download fails but SDS still processed."""
    products = [{
        "name": "Test Product", "manufacturer": "Acme",
        "tds_url": "https://fail.com/tds.pdf",
        "sds_url": "https://ok.com/sds.pdf",
        "industries": [], "product_line": None,
    }]
    pipeline, scraper, doc, graph, db = _make_pipeline(scraper_return=products)

    call_count = 0
    original_download = scraper.download_document

    async def download_side_effect(url):
        if "fail.com" in url:
            raise Exception("Download failed")
        return b"fake-pdf"

    scraper.download_document = AsyncMock(side_effect=download_side_effect)

    result = await pipeline.seed_from_url("https://chempoint.com/test")
    assert result["products_created"] == 1
    # TDS failed, SDS should succeed
    assert result["sds_stored"] == 1
    assert result["tds_stored"] == 0


@pytest.mark.asyncio
async def test_seed_from_url_no_tds_sds_urls():
    """Product created but no doc processing when URLs missing."""
    products = [{
        "name": "Bare Product", "manufacturer": "Acme",
        "industries": ["Coatings"], "product_line": None,
    }]
    pipeline, scraper, doc, graph, db = _make_pipeline(scraper_return=products)
    result = await pipeline.seed_from_url("https://chempoint.com/bare")
    assert result["products_created"] == 1
    assert result["tds_stored"] == 0
    assert result["sds_stored"] == 0
    doc.store_document.assert_not_called()


@pytest.mark.asyncio
async def test_seed_from_industry():
    """Aggregated stats from multiple products via seed_from_industry."""
    pipeline, scraper, doc, graph, db = _make_pipeline()

    # Industry page returns product summaries with URLs
    scraper.scrape_industry_page = AsyncMock(return_value=[
        {"name": "Prod A", "url": "https://chempoint.com/a"},
        {"name": "Prod B", "url": "https://chempoint.com/b"},
    ])
    # Each seed_from_url call returns these stats
    scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "X", "manufacturer": "M",
        "tds_url": "https://x.com/tds.pdf", "sds_url": None,
        "industries": [], "product_line": None,
    }])

    result = await pipeline.seed_from_industry("https://chempoint.com/industry/adhesives")
    assert result["products_created"] == 2
    assert result["tds_stored"] == 2


@pytest.mark.asyncio
async def test_seed_from_industry_summary_without_url():
    """Skips products without URL in industry page results."""
    pipeline, scraper, doc, graph, db = _make_pipeline()

    scraper.scrape_industry_page = AsyncMock(return_value=[
        {"name": "Prod A", "url": None},
        {"name": "Prod B"},  # no url key at all
    ])

    result = await pipeline.seed_from_industry("https://chempoint.com/industry/x")
    assert result["products_created"] == 0
    scraper.scrape_product_page.assert_not_called()


@pytest.mark.asyncio
async def test_make_sku_edge_cases():
    from services.ingestion.seed_chempoint import _make_sku
    assert _make_sku("POLYOX WSR-301") == "POLYOX-WSR-301"
    assert _make_sku("  spaces  ") == "SPACES"
    assert _make_sku("special!@#chars") == "SPECIAL-CHARS"
    assert _make_sku("") == ""
    assert _make_sku("already-clean") == "ALREADY-CLEAN"


@pytest.mark.asyncio
async def test_seed_from_url_partial_product_failure():
    """Continues past failed products."""
    products = [
        {"name": "Good", "manufacturer": "M", "industries": [], "product_line": None},
        {"name": "Bad", "manufacturer": "M", "industries": [], "product_line": None},
        {"name": "Also Good", "manufacturer": "M", "industries": [], "product_line": None},
    ]
    pipeline, scraper, doc, graph, db = _make_pipeline(scraper_return=products)

    call_count = 0
    original_acquire = db.pool.acquire

    async def fetchrow_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("DB error")
        return {"id": f"prod-{call_count}", "sku": f"SKU-{call_count}"}

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await pipeline.seed_from_url("https://chempoint.com/multi")
    # 2 succeed, 1 fails but pipeline continues
    assert result["products_created"] == 2


@pytest.mark.asyncio
async def test_seed_from_url_product_line_linking():
    """graph.link_product_to_product_line called when product_line is present."""
    products = [{
        "name": "POLYOX WSR-301", "manufacturer": "Dow",
        "product_line": "POLYOX Resins",
        "industries": [],
    }]
    pipeline, scraper, doc, graph, db = _make_pipeline(scraper_return=products)
    await pipeline.seed_from_url("https://chempoint.com/polyox")
    graph.link_product_to_product_line.assert_called_once_with(
        "POLYOX-WSR-301", "POLYOX Resins", "Dow"
    )
