"""Scrape 5 Industrial Coatings products from Chempoint to populate the database."""

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
logger = logging.getLogger("test_scrape_coatings")

# Valid product URLs from industrial-coatings sub-page (diverse manufacturers)
PRODUCT_URLS = [
    "https://www.chempoint.com/products/janssen-pmp/janssen-pmp-microbial-control/zinc-pyrion/zinc-pyrion-powder",
    "https://www.chempoint.com/products/mitsubishi-chemical-america/elvacite-specialty-acrylic-resins/elvacite-methacrylate-copolymers/elvacite-4067",
    "https://www.chempoint.com/products/eastman/eastman-cellulose-esters/cellulose-acetate-butyrate/cab-381-2",
    "https://www.chempoint.com/products/dorf-ketal/tyzor-organic-titanates-and-zirconates/tyzor-organic-titanates/tyzor-9000",
    "https://www.chempoint.com/products/iff/methocel-water-soluble-cellulose-ethers/methocel-water-soluble-cellulose-ethers/methocel-f50",
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

    claude_client = ClaudeClient(api_key=anthropic_key)
    embedding_client = VoyageEmbeddingClient(api_key=voyage_key)
    llm = LLMRouter(claude_client=claude_client, embedding_client=embedding_client)
    scraper = ChempointScraper(firecrawl_api_key=firecrawl_key, llm_router=llm)

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
        scraper=scraper, doc_service=doc_service,
        graph_service=graph_service, db_manager=db_manager, llm_router=llm,
    )

    total_stats = {"products_created": 0, "products_updated": 0, "tds_stored": 0,
                   "sds_stored": 0, "industries_linked": 0, "errors": 0}

    def on_progress(event):
        stage = event.get("stage", "")
        product = event.get("product", "")
        detail = event.get("detail", "")
        if stage in ("downloading_pdf", "extracting", "building_graph", "firecrawl_fallback", "error", "complete", "processing"):
            logger.info("[%s] %s — %s", stage, product, detail)

    for i, url in enumerate(PRODUCT_URLS):
        slug = url.split("/")[-1]
        print(f"\n--- [{i+1}/{len(PRODUCT_URLS)}] {slug} ---")
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

    # Verify counts
    async with neo4j_driver.session() as s:
        r = await s.run("MATCH (p:Part) RETURN count(p) AS cnt")
        rec = await r.single()
        print(f"Total Parts in Neo4j: {rec['cnt']}")
        r = await s.run("MATCH (t:TechnicalDataSheet) RETURN count(t) AS cnt")
        rec = await r.single()
        print(f"Total TDS nodes: {rec['cnt']}")
        r = await s.run("MATCH (s:SafetyDataSheet) RETURN count(s) AS cnt")
        rec = await r.single()
        print(f"Total SDS nodes: {rec['cnt']}")

    await pool.close()
    await neo4j_driver.close()


if __name__ == "__main__":
    asyncio.run(main())
