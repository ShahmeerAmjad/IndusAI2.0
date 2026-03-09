"""Test the enhanced extraction prompts on PARALOID KMX 100Pro."""

import asyncio
import json
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
logger = logging.getLogger("test_single")

PRODUCT_URL = "https://www.chempoint.com/products/dow/dow-paraloid-impact-modifiers/paraloid-bpm-impact-modifiers/paraloid-kmx-100pro"


async def main():
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    voyage_key = os.getenv("VOYAGE_API_KEY", "")

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

    def on_progress(event):
        stage = event.get("stage", "")
        product = event.get("product", "")
        detail = event.get("detail", "")
        logger.info("[%s] %s — %s", stage, product, detail)

    print(f"Scraping: {PRODUCT_URL}\n")
    stats = await pipeline.seed_from_url(PRODUCT_URL, on_progress=on_progress)
    print(f"\nPipeline stats: {stats}\n")

    # Now query Neo4j for the results
    async with neo4j_driver.session() as s:
        # Find the product
        r = await s.run("""
            MATCH (p:Part)
            WHERE p.name CONTAINS 'KMX' OR p.sku CONTAINS 'KMX'
            OPTIONAL MATCH (p)-[:HAS_TDS]->(t:TechnicalDataSheet)
            OPTIONAL MATCH (p)-[:HAS_SDS]->(sd:SafetyDataSheet)
            OPTIONAL MATCH (p)-[:SERVES_INDUSTRY]->(i:Industry)
            RETURN p.sku AS sku, p.name AS name,
                   t {.*} AS tds, sd {.*} AS sds,
                   collect(DISTINCT i.name) AS industries
        """)
        records = [rec async for rec in r]

        for rec in records:
            print("=" * 70)
            print(f"PRODUCT: {rec['name']} ({rec['sku']})")
            print(f"Industries: {rec['industries']}")

            if rec['tds']:
                print(f"\n--- TDS ({len(rec['tds'])} fields) ---")
                for k, v in sorted(rec['tds'].items()):
                    if v and k not in ('product_sku', 'revision_date'):
                        val = str(v)
                        if len(val) > 120:
                            val = val[:120] + "..."
                        print(f"  {k:35s} {val}")

            if rec['sds']:
                print(f"\n--- SDS ({len(rec['sds'])} fields) ---")
                for k, v in sorted(rec['sds'].items()):
                    if v and k not in ('product_sku', 'revision_date'):
                        val = str(v)
                        if len(val) > 120:
                            val = val[:120] + "..."
                        print(f"  {k:35s} {val}")

            print("=" * 70)

    await pool.close()
    await neo4j_driver.close()


if __name__ == "__main__":
    asyncio.run(main())
