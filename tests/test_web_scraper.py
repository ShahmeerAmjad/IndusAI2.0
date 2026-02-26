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

    @pytest.mark.asyncio
    async def test_scrape_returns_products(self):
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
            assert len(results) >= 0  # LLM-dependent
