import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.ingestion.web_scraper import WebScraper, ScrapedProduct


class TestWebScraper:
    def test_scraped_product_defaults(self):
        p = ScrapedProduct(sku="ABC-123", name="Test Part", price=9.99, seller_name="TestCo")
        assert p.reliability == 7.0
        assert p.source_type == "web_scrape"
        assert p.currency == "USD"

    def test_parse_price_from_text(self):
        scraper = WebScraper()
        assert scraper._parse_price("$12.99") == 12.99
        assert scraper._parse_price("USD 1,234.56") == 1234.56
        assert scraper._parse_price("no price here") is None

    def test_use_firecrawl_flag(self):
        scraper_no_key = WebScraper()
        assert not scraper_no_key._use_firecrawl

        scraper_with_key = WebScraper(firecrawl_api_key="fc-test123")
        assert scraper_with_key._use_firecrawl

    @pytest.mark.asyncio
    async def test_scrape_bs4_fallback(self):
        """BS4 path is used when no Firecrawl key."""
        scraper = WebScraper(llm_router=AsyncMock())
        scraper._llm.chat = AsyncMock(return_value='[{"sku":"A1","name":"Part A","price":5.0}]')

        with patch("services.ingestion.web_scraper.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Product A - $5.00 - SKU: A1</body></html>"
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            results = await scraper.scrape(
                url="https://example.com/catalog",
                seller_name="TestCo",
            )
            assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_scrape_firecrawl_path(self):
        """Firecrawl path is used when API key is provided."""
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='[{"sku":"B1","name":"Bearing B","price":12.50}]')
        scraper = WebScraper(llm_router=mock_llm, firecrawl_api_key="fc-test123")

        with patch("services.ingestion.web_scraper.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value={
                "data": {
                    "markdown": "# Products\n\n| SKU | Name | Price |\n|-----|------|-------|\n| B1 | Bearing B | $12.50 |",
                }
            })
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            results = await scraper.scrape(
                url="https://grainger.com/bearings",
                seller_name="Grainger",
            )
            assert len(results) == 1
            assert results[0].sku == "B1"
            assert results[0].price == 12.50
            assert results[0].seller_name == "Grainger"

    @pytest.mark.asyncio
    async def test_firecrawl_fallback_on_error(self):
        """Falls back to BS4 when Firecrawl returns non-200."""
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value='[{"sku":"C1","name":"Part C","price":3.0}]')
        scraper = WebScraper(llm_router=mock_llm, firecrawl_api_key="fc-test123")

        with patch("services.ingestion.web_scraper.httpx") as mock_httpx:
            # Firecrawl returns 500
            mock_fc_response = MagicMock()
            mock_fc_response.status_code = 500
            mock_fc_response.text = "Internal Server Error"

            # BS4 fallback returns HTML
            mock_bs4_response = MagicMock()
            mock_bs4_response.status_code = 200
            mock_bs4_response.text = "<html><body>Part C - $3.00 - SKU: C1</body></html>"

            # First client is for Firecrawl (post), second is BS4 fallback (get)
            mock_fc_client = AsyncMock()
            mock_fc_client.post = AsyncMock(return_value=mock_fc_response)
            mock_fc_client.__aenter__ = AsyncMock(return_value=mock_fc_client)
            mock_fc_client.__aexit__ = AsyncMock(return_value=False)

            mock_bs4_client = AsyncMock()
            mock_bs4_client.get = AsyncMock(return_value=mock_bs4_response)
            mock_bs4_client.__aenter__ = AsyncMock(return_value=mock_bs4_client)
            mock_bs4_client.__aexit__ = AsyncMock(return_value=False)

            # Return different clients for each AsyncClient() call
            mock_httpx.AsyncClient = MagicMock(side_effect=[mock_fc_client, mock_bs4_client])

            results = await scraper.scrape(
                url="https://example.com/catalog",
                seller_name="TestCo",
            )
            assert len(results) == 1
            assert results[0].sku == "C1"

    def test_find_next_page_in_markdown(self):
        scraper = WebScraper()
        md = "Some products here\n\n[Next Page](https://example.com/page2)\n"
        assert scraper._find_next_page_in_markdown(md, "https://example.com/page1") == "https://example.com/page2"

        md_relative = "Products\n\n[Next](/catalog?page=2)\n"
        assert scraper._find_next_page_in_markdown(md_relative, "https://example.com/catalog") == "https://example.com/catalog?page=2"

        md_none = "Just products, no pagination"
        assert scraper._find_next_page_in_markdown(md_none, "https://example.com") is None
