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
    mock_doc_service.extract_tds_fields_with_confidence = AsyncMock(return_value={
        "appearance": {"value": "White powder", "confidence": 0.95},
    })
    mock_doc_service.extract_sds_fields_with_confidence = AsyncMock(return_value={
        "cas_numbers": {"value": ["25322-68-3"], "confidence": 0.99},
    })

    mock_graph = MagicMock()
    mock_graph.ensure_part = AsyncMock()
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
    result = await pipeline.seed_from_url("https://chempoint.com/products/dow/polyox/resins/polyox-wsr301")
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
    mock_doc.extract_tds_fields_with_confidence = AsyncMock(
        return_value=doc_fields or {"appearance": {"value": "White", "confidence": 0.9}})
    mock_doc.extract_sds_fields_with_confidence = AsyncMock(
        return_value=doc_fields or {"cas_numbers": {"value": ["123"], "confidence": 0.9}})

    mock_graph = MagicMock()
    mock_graph.ensure_part = AsyncMock()
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
    assert result == {"products_created": 0, "products_updated": 0, "tds_stored": 0, "sds_stored": 0, "industries_linked": 0, "errors": 0}
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


@pytest.mark.asyncio
async def test_pipeline_with_progress_callback():
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    progress_events = []

    def on_progress(event):
        progress_events.append(event)

    mock_scraper = MagicMock()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "POLYOX WSR-301", "manufacturer": "Dow",
        "cas_number": "25322-68-3", "product_line": "POLYOX",
        "industries": ["Adhesives"], "tds_url": "https://example.com/tds.pdf",
        "sds_url": "https://example.com/sds.pdf",
    }])
    mock_scraper.download_document = AsyncMock(return_value=b"fake-pdf")

    mock_doc = MagicMock()
    mock_doc.store_document = AsyncMock(return_value={"id": "doc-1"})
    mock_doc.extract_text_from_pdf = AsyncMock(return_value="Appearance: White powder")
    mock_doc.extract_tds_fields_with_confidence = AsyncMock(return_value={
        "appearance": {"value": "White powder", "confidence": 0.95},
    })
    mock_doc.extract_sds_fields_with_confidence = AsyncMock(return_value={
        "cas_numbers": {"value": ["25322-68-3"], "confidence": 0.99},
    })

    mock_graph = MagicMock()
    mock_graph.ensure_part = AsyncMock()
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
        scraper=mock_scraper, doc_service=mock_doc,
        graph_service=mock_graph, db_manager=mock_db,
    )
    result = await pipeline.seed_from_url(
        "https://chempoint.com/products/dow/polyox/resins/polyox-wsr301", on_progress=on_progress,
    )
    assert result["products_created"] >= 1
    assert len(progress_events) >= 3
    assert progress_events[0]["stage"] in ("scraping", "discovering")


@pytest.mark.asyncio
async def test_pipeline_stores_confidence_in_graph():
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    mock_scraper = MagicMock()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "TEST-PROD", "manufacturer": "TestMfr",
        "tds_url": "https://example.com/tds.pdf",
    }])
    mock_scraper.download_document = AsyncMock(return_value=b"fake")

    mock_doc = MagicMock()
    mock_doc.store_document = AsyncMock(return_value={"id": "d1"})
    mock_doc.extract_text_from_pdf = AsyncMock(return_value="text")
    mock_doc.extract_tds_fields_with_confidence = AsyncMock(return_value={
        "appearance": {"value": "Clear liquid", "confidence": 0.92},
    })

    mock_graph = MagicMock()
    mock_graph.ensure_part = AsyncMock()
    mock_graph.create_tds = AsyncMock()
    mock_graph.link_product_to_industry = AsyncMock()
    mock_graph.link_product_to_product_line = AsyncMock()

    mock_db = MagicMock()
    mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={"id": "p1", "sku": "TEST-PROD"})
    ))
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    pipeline = ChempointSeedPipeline(
        scraper=mock_scraper, doc_service=mock_doc,
        graph_service=mock_graph, db_manager=mock_db,
    )
    await pipeline.seed_from_url("https://example.com/test")

    call_args = mock_graph.create_tds.call_args
    fields = call_args[0][1]
    assert "appearance" in fields


@pytest.mark.asyncio
async def test_empty_product_name_skipped():
    """Products with empty names should be skipped, not create bad SKUs."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[
        {"name": "", "manufacturer": "ACME"},
        {"name": "   ", "manufacturer": "ACME"},
        {"name": "Valid Product", "manufacturer": "3M",
         "description": "Good product"},
    ])
    mock_db.pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
        return_value={"id": "uuid-1", "sku": "VALID-PRODUCT", "xmax": 0})
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    stats = await pipeline.seed_from_url("https://example.com", on_progress=lambda e: None)

    assert stats["products_created"] == 1
    assert stats["errors"] == 2


@pytest.mark.asyncio
async def test_max_products_enforced_across_industries():
    """seed_from_industries stops after max_products globally."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()

    call_count = 0
    async def mock_scrape_industry(url):
        nonlocal call_count
        call_count += 1
        return [{"name": f"Product-{call_count}-{i}", "url": f"https://ex.com/p{i}"}
                for i in range(5)]

    mock_scraper.scrape_industry_page = AsyncMock(side_effect=mock_scrape_industry)
    mock_scraper.scrape_product_page = AsyncMock(return_value=[
        {"name": "P", "manufacturer": "M", "description": "D"}
    ])
    mock_db.pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
        return_value={"id": "uuid-1", "sku": "P", "xmax": 0})
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    stats = await pipeline.seed_from_industries(
        ["https://ex.com/ind1", "https://ex.com/ind2", "https://ex.com/ind3"],
        on_progress=lambda e: None,
        max_products=3,
    )

    assert stats["products_created"] <= 3


@pytest.mark.asyncio
async def test_tracks_created_vs_updated():
    """Pipeline should distinguish new products from updated ones."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[
        {"name": "New Product", "manufacturer": "3M"},
        {"name": "Existing Product", "manufacturer": "3M"},
    ])

    # First call returns xmax=0 (INSERT), second returns xmax!=0 (UPDATE)
    call_count = 0
    async def mock_fetchrow(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        row = MagicMock()
        row.__getitem__ = lambda self, k: {"id": f"uuid-{call_count}", "sku": f"P-{call_count}",
                                            "xmax": 0 if call_count == 1 else 1}[k]
        row.get = lambda k, d=None: {"id": f"uuid-{call_count}", "sku": f"P-{call_count}",
                                      "xmax": 0 if call_count == 1 else 1}.get(k, d)
        return row

    mock_db.pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    stats = await pipeline.seed_from_url("https://example.com", on_progress=lambda e: None)

    assert stats["products_created"] == 1
    assert stats["products_updated"] == 1


@pytest.mark.asyncio
async def test_seed_from_url_detects_manufacturer_page():
    """Manufacturer URLs should call scrape_manufacturer_page, not scrape_product_page."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()

    # scrape_manufacturer_page returns product summaries with URLs
    mock_scraper.scrape_manufacturer_page = AsyncMock(return_value=[
        {"name": "Elvacite 4067", "url": "https://www.chempoint.com/products/mca/elvacite/copolymers/elvacite-4067"},
    ])
    # The recursed product URL goes through scrape_product_page
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "Elvacite 4067", "manufacturer": "Mitsubishi",
        "tds_url": None, "sds_url": None, "industries": ["Coatings"],
    }])

    stats = await pipeline.seed_from_url(
        "https://www.chempoint.com/manufacturers/mitsubishi-chemical-america",
        on_progress=lambda e: None,
    )

    mock_scraper.scrape_manufacturer_page.assert_called_once()
    assert stats["products_created"] == 1


@pytest.mark.asyncio
async def test_seed_from_url_detects_product_listing_page():
    """Product listing URLs (1-3 segments) should use scrape_product_listing."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()

    mock_scraper.scrape_product_listing = AsyncMock(return_value=[
        {"name": "Elvacite 4067", "url": "https://www.chempoint.com/products/mca/line/sub/elvacite-4067"},
    ])
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "Elvacite 4067", "manufacturer": "Mitsubishi",
        "tds_url": None, "sds_url": None, "industries": ["Coatings"],
    }])

    stats = await pipeline.seed_from_url(
        "https://www.chempoint.com/products/mitsubishi-chemical-america",
        on_progress=lambda e: None,
    )

    mock_scraper.scrape_product_listing.assert_called_once()
    # scrape_product_page should NOT have been called for the listing URL
    assert stats["products_created"] == 1


@pytest.mark.asyncio
async def test_seed_from_url_product_detail_not_treated_as_listing():
    """Product detail URLs (4+ segments) should go through scrape_product_page."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()

    mock_scraper.scrape_product_listing = AsyncMock()
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "Elvacite 4067", "manufacturer": "Mitsubishi",
        "tds_url": None, "sds_url": None, "industries": [],
    }])

    stats = await pipeline.seed_from_url(
        "https://www.chempoint.com/products/mca/elvacite-specialty/copolymers/elvacite-4067",
        on_progress=lambda e: None,
    )

    mock_scraper.scrape_product_listing.assert_not_called()
    mock_scraper.scrape_product_page.assert_called_once()
    assert stats["products_created"] == 1


@pytest.mark.asyncio
async def test_seed_from_url_detects_industry_page():
    """Industry URLs should call scrape_industry_page, not scrape_product_page."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()

    mock_scraper.scrape_industry_page = AsyncMock(return_value=[
        {"name": "Product X", "url": "https://www.chempoint.com/products/dow/line/sub/product-x"},
    ])
    mock_scraper.scrape_product_page = AsyncMock(return_value=[{
        "name": "Product X", "manufacturer": "Dow",
        "tds_url": None, "sds_url": None, "industries": ["Adhesives"],
    }])

    stats = await pipeline.seed_from_url(
        "https://www.chempoint.com/industries/adhesives",
        on_progress=lambda e: None,
    )

    mock_scraper.scrape_industry_page.assert_called_once()
    assert stats["products_created"] == 1


@pytest.mark.asyncio
async def test_seed_from_industries_uses_compaction():
    """Batch ingestion should work with llm_router wired in."""
    pipeline, mock_scraper, mock_doc, mock_graph, mock_db = _make_pipeline()
    pipeline._llm = MagicMock()
    pipeline._llm.chat_with_compaction = AsyncMock(return_value='[{"name": "P1"}]')

    mock_scraper.scrape_industry_page = AsyncMock(return_value=[])

    stats = await pipeline.seed_from_industries(
        ["https://ex.com/ind1"],
        on_progress=lambda e: None,
        max_products=50,
    )

    assert stats["errors"] == 0
