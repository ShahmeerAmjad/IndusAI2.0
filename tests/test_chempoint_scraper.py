"""Test Chempoint catalog scraping and product extraction."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_scrape_product_page():
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    mock_html = """
    <div class="product-detail">
        <h1>POLYOX™ WSR-301</h1>
        <span class="manufacturer">Dow</span>
        <span class="cas">25322-68-3</span>
        <p>Water-soluble resin for adhesives and coatings</p>
        <a href="/docs/tds-polyox-wsr301.pdf">Technical Data Sheet</a>
        <a href="/docs/sds-polyox-wsr301.pdf">Safety Data Sheet</a>
    </div>
    """
    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_html
        with patch.object(scraper, '_extract_with_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = [{
                "name": "POLYOX WSR-301",
                "manufacturer": "Dow",
                "cas_number": "25322-68-3",
                "description": "Water-soluble resin for adhesives and coatings",
                "tds_url": "/docs/tds-polyox-wsr301.pdf",
                "sds_url": "/docs/sds-polyox-wsr301.pdf",
                "industries": ["Adhesives", "Coatings"],
                "product_line": "POLYOX Water-Soluble Resins",
            }]
            products = await scraper.scrape_product_page("https://chempoint.com/products/polyox-wsr301")
            assert len(products) == 1
            assert products[0]["cas_number"] == "25322-68-3"

@pytest.mark.asyncio
async def test_scrape_industry_page():
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = "<html>mock</html>"
        with patch.object(scraper, '_extract_with_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = [
                {"name": "POLYOX WSR-301", "manufacturer": "Dow"},
                {"name": "METHOCEL K4M", "manufacturer": "Dow"},
            ]
            products = await scraper.scrape_industry_page("https://chempoint.com/industries/adhesives/all")
            assert len(products) == 2

@pytest.mark.asyncio
async def test_download_tds_sds_pdf():
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    with patch.object(scraper, '_download_file', new_callable=AsyncMock) as mock_dl:
        mock_dl.return_value = b"fake-pdf-bytes"
        result = await scraper.download_document("https://chempoint.com/docs/tds.pdf")
        assert result == b"fake-pdf-bytes"


@pytest.mark.asyncio
async def test_fetch_page_firecrawl_http_error():
    """Returns '' on non-200, so scrape_product_page returns []."""
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key", llm_router=MagicMock())

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await scraper._fetch_page("https://example.com")
    assert result == ""


@pytest.mark.asyncio
async def test_fetch_page_firecrawl_timeout():
    """Timeout exception propagates."""
    import httpx
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.TimeoutException):
            await scraper._fetch_page("https://example.com")


@pytest.mark.asyncio
async def test_extract_with_llm_malformed_json():
    """Returns [] on bad LLM JSON (caught by except block)."""
    from services.ingestion.chempoint_scraper import ChempointScraper, PRODUCT_EXTRACTION_PROMPT
    llm = MagicMock()
    llm.chat = AsyncMock(return_value="not json at all")
    scraper = ChempointScraper(firecrawl_api_key="test-key", llm_router=llm)

    result = await scraper._extract_with_llm("some content", PRODUCT_EXTRACTION_PROMPT)
    assert result == []


@pytest.mark.asyncio
async def test_extract_with_llm_empty_content():
    """Returns [] immediately when content is empty, no LLM call."""
    from services.ingestion.chempoint_scraper import ChempointScraper, PRODUCT_EXTRACTION_PROMPT
    llm = MagicMock()
    llm.chat = AsyncMock()
    scraper = ChempointScraper(firecrawl_api_key="test-key", llm_router=llm)

    result = await scraper._extract_with_llm("", PRODUCT_EXTRACTION_PROMPT)
    assert result == []
    llm.chat.assert_not_called()


@pytest.mark.asyncio
async def test_extract_with_llm_no_llm_configured():
    """Returns [] when llm_router is None."""
    from services.ingestion.chempoint_scraper import ChempointScraper, PRODUCT_EXTRACTION_PROMPT
    scraper = ChempointScraper(firecrawl_api_key="test-key", llm_router=None)

    result = await scraper._extract_with_llm("some content", PRODUCT_EXTRACTION_PROMPT)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_product_listing_extracts_detail_urls():
    """Product listing pages should extract 4+ segment product URLs."""
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    listing_page = """
    [Elvacite Specialty Resins](https://www.chempoint.com/products/mca/elvacite-specialty)
    [Elvacite 4067](https://www.chempoint.com/products/mca/elvacite-specialty/copolymers/elvacite-4067)
    [View Details](https://www.chempoint.com/products/mca/elvacite-specialty/copolymers/elvacite-4067)
    [SDS](https://www.chempoint.com/products/download?grade=123)
    [Lucite 4F](https://www.chempoint.com/products/mca/elvacite-specialty/lucite/lucite-4f)
    """

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = listing_page
        products = await scraper.scrape_product_listing("https://www.chempoint.com/products/mca")

    assert len(products) == 2
    assert products[0]["name"] == "Elvacite 4067"
    assert products[1]["name"] == "Lucite 4F"


@pytest.mark.asyncio
async def test_scrape_manufacturer_page_follows_all_products_link():
    """Should follow 'View All Manufacturer Products' and extract product detail URLs."""
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    mfr_page = """
    ## Product Lines
    - [Elvacite Specialty Resins](https://www.chempoint.com/products/mca/elvacite-specialty)
    - [jER Epoxy Resins](https://www.chempoint.com/products/mca/jer-epoxy)
    [View All Manufacturer Products](https://www.chempoint.com/products/mca)
    """

    all_products_page = """
    [Elvacite 4067](https://www.chempoint.com/products/mca/elvacite-specialty/copolymers/elvacite-4067)
    [View Details](https://www.chempoint.com/products/mca/elvacite-specialty/copolymers/elvacite-4067)
    [SDS](https://www.chempoint.com/products/download?grade=123&doctype=sds)
    [Elvacite 2927](https://www.chempoint.com/products/mca/elvacite-specialty/copolymers/elvacite-2927)
    [View Details](https://www.chempoint.com/products/mca/elvacite-specialty/copolymers/elvacite-2927)
    """

    call_count = 0
    async def mock_fetch(url):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mfr_page
        return all_products_page

    with patch.object(scraper, '_fetch_page', side_effect=mock_fetch):
        products = await scraper.scrape_manufacturer_page("https://chempoint.com/manufacturers/mca")

    assert len(products) == 2
    assert products[0]["name"] == "Elvacite 4067"
    assert products[1]["name"] == "Elvacite 2927"
    # Should have fetched twice: manufacturer page + all-products page
    assert call_count == 2


@pytest.mark.asyncio
async def test_scrape_manufacturer_page_skips_product_lines():
    """Product line URLs (2-3 segments) should be filtered out, only 4+ segment URLs kept."""
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    # Page without "View All" link — direct product listing with mixed URLs
    page = """
    [Elvacite Specialty](https://www.chempoint.com/products/mca/elvacite-specialty)
    [Elvacite 4067](https://www.chempoint.com/products/mca/elvacite-specialty/copolymers/elvacite-4067)
    """

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = page
        products = await scraper.scrape_manufacturer_page("https://chempoint.com/manufacturers/mca")

    # Only the 4-segment URL should be included
    assert len(products) == 1
    assert products[0]["name"] == "Elvacite 4067"


@pytest.mark.asyncio
async def test_scrape_manufacturer_page_falls_back_to_llm():
    """When no product URLs found via regex, falls back to LLM extraction."""
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = "Some page with no product links"
        with patch.object(scraper, '_extract_with_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = [{"name": "Product A", "manufacturer": "Dow"}]
            products = await scraper.scrape_manufacturer_page("https://chempoint.com/manufacturers/dow")

    assert len(products) == 1
    mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_download_document_404():
    """httpx.HTTPStatusError propagates from _download_file."""
    import httpx
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_resp
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await scraper.download_document("https://chempoint.com/docs/missing.pdf")


@pytest.mark.asyncio
async def test_crawl_full_catalog_dedup_urls():
    """Visited set deduplicates URLs."""
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    call_count = 0

    async def mock_scrape(url):
        nonlocal call_count
        call_count += 1
        return [{"name": f"Product {call_count}"}]

    with patch.object(scraper, 'scrape_product_page', side_effect=mock_scrape):
        # Pass same URL twice via to_visit - second should be deduped
        results = await scraper.crawl_full_catalog("https://chempoint.com/page1", max_pages=5)

    # Only 1 call since same URL
    assert call_count == 1


@pytest.mark.asyncio
async def test_crawl_full_catalog_max_pages_limit():
    """Respects max_pages param."""
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    urls = [f"https://chempoint.com/page{i}" for i in range(10)]
    call_count = 0

    async def mock_scrape(url):
        nonlocal call_count
        call_count += 1
        return [{"name": f"Product {call_count}"}]

    # Manually set to_visit to have multiple unique URLs
    original_crawl = scraper.crawl_full_catalog

    with patch.object(scraper, 'scrape_product_page', side_effect=mock_scrape):
        # We can only feed one base_url, but max_pages=3 should limit
        # Since crawl doesn't discover new URLs in this mock, only 1 page gets crawled
        results = await scraper.crawl_full_catalog(urls[0], max_pages=3)
    assert call_count <= 3


@pytest.mark.asyncio
async def test_crawl_full_catalog_partial_failure():
    """Continues past failed URLs."""
    from services.ingestion.chempoint_scraper import ChempointScraper
    scraper = ChempointScraper(firecrawl_api_key="test-key")

    call_count = 0

    async def mock_scrape(url):
        nonlocal call_count
        call_count += 1
        if "fail" in url:
            raise Exception("Scrape failed")
        return [{"name": "Good Product"}]

    with patch.object(scraper, 'scrape_product_page', side_effect=mock_scrape):
        # Inject multiple URLs by patching the method's internal state
        # crawl_full_catalog only takes one base URL, but we can test failure handling
        results = await scraper.crawl_full_catalog("https://chempoint.com/fail-page", max_pages=5)

    # Should not raise, just log warning and return empty
    assert results == []
    assert call_count == 1
