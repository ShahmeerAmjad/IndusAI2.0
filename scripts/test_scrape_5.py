"""Quick test: scrape 5 Chempoint product pages end-to-end through the pipeline."""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dotenv
dotenv.load_dotenv()

from services.ingestion.chempoint_scraper import ChempointScraper
from services.ingestion.seed_chempoint import ChempointSeedPipeline
from services.document_service import DocumentService
from services.graph.tds_sds_service import TDSSDSGraphService
from services.ai.claude_client import ClaudeClient
from services.ai.embedding_client import VoyageEmbeddingClient
from services.ai.llm_router import LLMRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("test_scrape")

# Valid Chempoint product page URLs (found from industry listing)
PRODUCT_URLS = [
    "https://www.chempoint.com/products/dow/dowfrost-glycol-thermal-fluids/dowfrost-propylene-glycol-thermal-fluids/dowfrost-hd",
    "https://www.chempoint.com/products/dow/ucon-polyalkylene-glycol-formulated-fluids/ucon-polyalkylene-glycol-metal-working-fluids/ucon-mwl-2",
    "https://www.chempoint.com/products/dow/dow-laminating-adhesives/robond/l-148eu",
    "https://www.chempoint.com/products/dow/dow-paraloid-impact-modifiers/paraloid-bta-impact-modifiers/paraloid-bta-730",
    "https://www.chempoint.com/products/dow/syltherm-silicone-thermal-fluids/syltherm-silicone-thermal-fluids/syltherm-800",
]


async def main():
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    voyage_key = os.getenv("VOYAGE_API_KEY", "")

    if not firecrawl_key:
        print("ERROR: FIRECRAWL_API_KEY not set")
        return
    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    # Set up services
    claude_client = ClaudeClient(api_key=anthropic_key)
    embedding_client = VoyageEmbeddingClient(api_key=voyage_key)
    llm = LLMRouter(claude_client=claude_client, embedding_client=embedding_client)
    scraper = ChempointScraper(firecrawl_api_key=firecrawl_key, llm_router=llm)

    # Quick test: scrape one page and see what comes back
    print("=" * 60)
    print("Step 1: Test scraping a single product page")
    print("=" * 60)
    products = await scraper.scrape_product_page(PRODUCT_URLS[0])
    print(f"Found {len(products)} products:")
    for p in products:
        print(f"  Name: {p.get('name')}")
        print(f"  Manufacturer: {p.get('manufacturer')}")
        print(f"  TDS URL: {p.get('tds_url')}")
        print(f"  SDS URL: {p.get('sds_url')}")
        print(f"  Industries: {p.get('industries')}")
        print()

    if not products:
        print("No products extracted — stopping here to debug.")
        return

    # Step 2: Test PDF download (Firecrawl fallback)
    print("=" * 60)
    print("Step 2: Test document download")
    print("=" * 60)
    test_sds = products[0].get("sds_url") or products[0].get("tds_url")
    if test_sds:
        try:
            content = await scraper.download_document(test_sds)
            print(f"Downloaded {len(content)} bytes from {test_sds}")
            print(f"First 200 chars: {content[:200]}")
        except Exception as e:
            print(f"Download failed: {e}")
            print("Trying fetch_document_text instead...")
            text = await scraper.fetch_document_text(test_sds)
            print(f"Got {len(text)} chars of text")
            print(f"First 500 chars: {text[:500]}")
    else:
        print("No doc URL found, skipping download test")

    # Step 3: Full pipeline for all 5 products
    print("\n" + "=" * 60)
    print("Step 3: Full pipeline for 5 products")
    print("=" * 60)

    from neo4j import AsyncGraphDatabase
    neo4j_driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "changeme"))

    class Neo4jClient:
        def __init__(self, driver):
            self._driver = driver
        async def execute_write(self, cypher, params=None):
            async with self._driver.session() as s:
                result = await s.run(cypher, params or {})
                return [record.data() async for record in result]
        async def execute_read(self, cypher, params=None):
            async with self._driver.session() as s:
                result = await s.run(cypher, params or {})
                return [record.data() async for record in result]

    neo4j_client = Neo4jClient(neo4j_driver)
    graph_service = TDSSDSGraphService(neo4j_client)

    import asyncpg
    pool = await asyncpg.create_pool("postgresql://chatbot:password@localhost:5432/chatbot")

    class DBManager:
        def __init__(self, pool):
            self.pool = pool

    db_manager = DBManager(pool)
    doc_service = DocumentService(db_manager=db_manager, ai_service=llm)

    pipeline = ChempointSeedPipeline(
        scraper=scraper,
        doc_service=doc_service,
        graph_service=graph_service,
        db_manager=db_manager,
        llm_router=llm,
    )

    total_stats = {"products_created": 0, "products_updated": 0, "tds_stored": 0,
                   "sds_stored": 0, "industries_linked": 0, "errors": 0}

    def on_progress(event):
        stage = event.get("stage", "")
        product = event.get("product", "")
        detail = event.get("detail", "")
        if stage in ("downloading_pdf", "extracting", "building_graph", "firecrawl_fallback", "error"):
            logger.info("[%s] %s — %s", stage, product, detail)

    for i, url in enumerate(PRODUCT_URLS):
        print(f"\n--- [{i+1}/5] {url.split('/')[-1]} ---")
        try:
            stats = await pipeline.seed_from_url(url, on_progress=on_progress)
            print(f"  {stats}")
            for k in total_stats:
                total_stats[k] += stats.get(k, 0)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()
            total_stats["errors"] += 1

    print(f"\n{'='*60}")
    print(f"FINAL TOTALS: {total_stats}")
    print(f"{'='*60}")

    # Verify in DBs
    count = await pool.fetchval("SELECT count(*) FROM documents")
    print(f"Documents in PG: {count}")

    async with neo4j_driver.session() as s:
        r = await s.run("MATCH (t:TechnicalDataSheet) RETURN count(t) AS cnt")
        rec = await r.single()
        print(f"TDS nodes in Neo4j: {rec['cnt']}")
        r = await s.run("MATCH (s:SafetyDataSheet) RETURN count(s) AS cnt")
        rec = await r.single()
        print(f"SDS nodes in Neo4j: {rec['cnt']}")

    await pool.close()
    await neo4j_driver.close()


if __name__ == "__main__":
    asyncio.run(main())
