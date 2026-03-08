"""CLI script to seed the knowledge graph from Chempoint.

Usage:
    python -m scripts.seed_chempoint --industries "Adhesives,Coatings,Pharma" --max-products 50
    python -m scripts.seed_chempoint --url "https://chempoint.com/products/polyox-wsr301"
"""
import argparse
import asyncio
import logging
import os
import sys

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel

console = Console()

# Chempoint industry page URLs
INDUSTRY_URLS = {
    "Adhesives": "https://www.chempoint.com/en-us/products/industry/adhesives-and-sealants",
    "Coatings": "https://www.chempoint.com/en-us/products/industry/paints-and-coatings",
    "Pharma": "https://www.chempoint.com/en-us/products/industry/pharmaceutical",
    "Personal Care": "https://www.chempoint.com/en-us/products/industry/personal-care",
    "Water Treatment": "https://www.chempoint.com/en-us/products/industry/water-treatment",
    "Food & Beverage": "https://www.chempoint.com/en-us/products/industry/food-and-beverage",
    "Plastics": "https://www.chempoint.com/en-us/products/industry/plastics-and-rubber",
    "Energy": "https://www.chempoint.com/en-us/products/industry/energy",
    "Agriculture": "https://www.chempoint.com/en-us/products/industry/agriculture",
    "Construction": "https://www.chempoint.com/en-us/products/industry/building-and-construction",
}


async def run_seed(args):
    """Run the seeding pipeline."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from services.database_manager import DatabaseManager
    from services.graph.neo4j_client import Neo4jClient
    from services.ai.llm_router import LLMRouter
    from services.document_service import DocumentService
    from services.graph.tds_sds_service import TDSSDSGraphService
    from services.ingestion.chempoint_scraper import ChempointScraper
    from services.ingestion.seed_chempoint import ChempointSeedPipeline

    # Init services
    db = DatabaseManager(os.getenv("DATABASE_URL", "postgresql://chatbot:password@localhost:5432/chatbot"))
    await db.initialize()

    neo4j = Neo4jClient(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "changeme"),
    )
    await neo4j.verify_connectivity()

    llm = LLMRouter(api_key=os.getenv("ANTHROPIC_API_KEY"))
    doc_service = DocumentService(db, ai_service=llm)
    graph_service = TDSSDSGraphService(neo4j)

    scraper = ChempointScraper(
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""),
        llm_router=llm,
    )

    pipeline = ChempointSeedPipeline(
        scraper=scraper, doc_service=doc_service,
        graph_service=graph_service, db_manager=db,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        if args.url:
            task = progress.add_task("Ingesting product...", total=None)

            def on_progress(event):
                current_stage = event.get("stage", "")
                current_product = event.get("product", "")
                detail = event.get("detail", "")
                progress.update(task, description=f"[{current_stage}] {current_product or detail}")

            result = await pipeline.seed_from_url(args.url, on_progress=on_progress)
            progress.update(task, completed=True)

        else:
            industries = [i.strip() for i in args.industries.split(",")]
            urls = []
            for ind in industries:
                if ind in INDUSTRY_URLS:
                    urls.append(INDUSTRY_URLS[ind])
                else:
                    console.print(f"[yellow]Unknown industry: {ind}. Skipping.[/yellow]")

            if not urls:
                console.print("[red]No valid industries found. Available:[/red]")
                for k in INDUSTRY_URLS:
                    console.print(f"  - {k}")
                return

            task = progress.add_task(f"Seeding {len(urls)} industries...", total=len(urls))

            def on_progress(event):
                stage = event.get("stage", "")
                product = event.get("product", "")
                detail = event.get("detail", "")
                if stage == "discovering":
                    progress.advance(task)
                progress.update(task, description=f"[{stage}] {product or detail}")

            result = await pipeline.seed_from_industries(urls, on_progress=on_progress)
            progress.update(task, completed=len(urls))

    # Summary
    console.print()
    summary = Table(title="Seed Pipeline Results", show_header=True)
    summary.add_column("Metric", style="bold")
    summary.add_column("Count", justify="right")
    for key, val in result.items():
        color = "green" if val > 0 else "dim"
        summary.add_row(key.replace("_", " ").title(), f"[{color}]{val}[/{color}]")
    console.print(Panel(summary))

    await db.close()
    await neo4j.close()


def main():
    parser = argparse.ArgumentParser(description="Seed knowledge graph from Chempoint")
    parser.add_argument("--url", help="Single product URL to ingest")
    parser.add_argument("--industries", default="Adhesives,Coatings,Pharma,Personal Care,Water Treatment",
                        help="Comma-separated industry names")
    parser.add_argument("--max-products", type=int, default=50, help="Max products per industry")
    args = parser.parse_args()
    asyncio.run(run_seed(args))


if __name__ == "__main__":
    main()
