import pytest
from unittest.mock import AsyncMock, MagicMock

from services.ai.part_number_parser import PartNumberParser
from services.ingestion.parser import CatalogParser, COLUMN_ALIASES
from services.ingestion.normalizer import CatalogNormalizer, NormalizedProduct
from services.ingestion.resolver import EntityResolver, ResolutionResult
from services.ingestion.graph_builder import GraphBuilder, BuildResult
from services.ingestion.pipeline import IngestionPipeline, IngestionResult


# --- CatalogParser Tests ---

class TestCatalogParser:
    @pytest.mark.asyncio
    async def test_parse_csv_basic(self):
        parser = CatalogParser()
        csv_data = (
            "sku,name,category,manufacturer,price\n"
            "6204-2RS,Deep Groove Bearing,Bearings,SKF,5.50\n"
            "M8x30,Hex Bolt M8,Fasteners,Generic,0.25\n"
        ).encode("utf-8")

        products = await parser.parse_csv(csv_data)
        assert len(products) == 2
        assert products[0]["part_number"] == "6204-2RS"
        assert products[1]["part_number"] == "M8x30"

    @pytest.mark.asyncio
    async def test_parse_csv_alternate_columns(self):
        parser = CatalogParser()
        csv_data = (
            "part_number,description,brand,list_price\n"
            "NSK-6205,Ball Bearing 25mm,NSK,6.75\n"
        ).encode("utf-8")

        products = await parser.parse_csv(csv_data)
        assert len(products) == 1
        assert products[0]["part_number"] == "NSK-6205"
        assert products[0]["manufacturer"] == "NSK"

    @pytest.mark.asyncio
    async def test_parse_csv_empty(self):
        parser = CatalogParser()
        csv_data = "sku,name\n".encode("utf-8")

        products = await parser.parse_csv(csv_data)
        assert len(products) == 0

    @pytest.mark.asyncio
    async def test_parse_csv_skips_no_sku(self):
        parser = CatalogParser()
        csv_data = (
            "sku,name\n"
            ",No SKU Product\n"
            "VALID-123,Valid Product\n"
        ).encode("utf-8")

        products = await parser.parse_csv(csv_data)
        assert len(products) == 1
        assert products[0]["part_number"] == "VALID-123"

    def test_column_aliases_coverage(self):
        assert "sku" in COLUMN_ALIASES
        assert "name" in COLUMN_ALIASES
        assert "manufacturer" in COLUMN_ALIASES
        assert "price" in COLUMN_ALIASES


# --- CatalogNormalizer Tests ---

class TestCatalogNormalizer:
    def setup_method(self):
        self.parser = PartNumberParser()
        self.normalizer = CatalogNormalizer(self.parser)

    @pytest.mark.asyncio
    async def test_normalize_bearing(self):
        raw = [{"part_number": "6204-2RS", "name": "Bearing", "manufacturer": "SKF"}]
        results = await self.normalizer.normalize(raw)
        assert len(results) == 1
        assert results[0].sku == "6204-2RS"
        assert results[0].manufacturer == "SKF"
        assert results[0].category == "Ball Bearings"

    @pytest.mark.asyncio
    async def test_normalize_preserves_raw_specs(self):
        raw = [{
            "part_number": "CUSTOM-123", "name": "Widget",
            "specifications": {"weight_kg": "1.5", "material": "steel"}
        }]
        results = await self.normalizer.normalize(raw)
        assert len(results) == 1
        assert results[0].specs.get("weight_kg") == "1.5"

    @pytest.mark.asyncio
    async def test_normalize_skips_no_sku(self):
        raw = [{"name": "No SKU"}]
        results = await self.normalizer.normalize(raw)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_normalize_price_parsing(self):
        raw = [{"part_number": "X1", "name": "Item", "unit_price": "$1,234.56"}]
        results = await self.normalizer.normalize(raw)
        assert results[0].unit_price == 1234.56


# --- EntityResolver Tests ---

class TestEntityResolver:
    @pytest.fixture
    def mock_graph(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_resolve_new_product(self, mock_graph):
        mock_graph.get_part.return_value = None
        mock_graph.resolve_part.return_value = []
        mock_graph.search_parts_fulltext.return_value = []

        resolver = EntityResolver(mock_graph)
        product = NormalizedProduct(sku="NEW-001", name="New Part")
        result = await resolver.resolve([product])

        assert len(result.new) == 1
        assert result.new[0].status == "new"

    @pytest.mark.asyncio
    async def test_resolve_exact_match(self, mock_graph):
        mock_graph.get_part.return_value = {"sku": "EXISTS-001", "name": "Existing"}

        resolver = EntityResolver(mock_graph)
        product = NormalizedProduct(sku="EXISTS-001", name="Existing Part")
        result = await resolver.resolve([product])

        assert len(result.matched) == 1
        assert result.matched[0].match_source == "exact_sku"
        assert result.matched[0].match_confidence == 1.0

    @pytest.mark.asyncio
    async def test_resolve_cross_ref(self, mock_graph):
        mock_graph.get_part.return_value = None
        mock_graph.resolve_part.return_value = [{"sku": "ORIG-001", "name": "Original"}]
        mock_graph.search_parts_fulltext.return_value = []

        resolver = EntityResolver(mock_graph)
        product = NormalizedProduct(sku="XREF-001", name="Cross Ref Part")
        result = await resolver.resolve([product])

        assert len(result.matched) == 1
        assert result.matched[0].match_source == "cross_ref"

    @pytest.mark.asyncio
    async def test_total_property(self, mock_graph):
        mock_graph.get_part.return_value = None
        mock_graph.resolve_part.return_value = []
        mock_graph.search_parts_fulltext.return_value = []

        resolver = EntityResolver(mock_graph)
        products = [
            NormalizedProduct(sku="A", name="A"),
            NormalizedProduct(sku="B", name="B"),
        ]
        result = await resolver.resolve(products)
        assert result.total == 2


# --- GraphBuilder Tests ---

class TestGraphBuilder:
    @pytest.fixture
    def mock_graph(self):
        g = AsyncMock()
        g.upsert_part.return_value = {"sku": "TEST"}
        g.update_price_range.return_value = None
        g.add_cross_reference.return_value = {}
        return g

    @pytest.mark.asyncio
    async def test_build_new_products(self, mock_graph):
        builder = GraphBuilder(mock_graph)
        product = NormalizedProduct(sku="NEW-001", name="New Part", category="Bearings")

        from services.ingestion.resolver import ResolvedProduct
        resolved = ResolutionResult(
            new=[ResolvedProduct(product=product, status="new")],
        )

        result = await builder.build(resolved)
        assert result.created == 1
        assert result.updated == 0
        mock_graph.upsert_part.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_with_price(self, mock_graph):
        builder = GraphBuilder(mock_graph)
        product = NormalizedProduct(sku="P-001", name="Part", unit_price=9.99)

        from services.ingestion.resolver import ResolvedProduct
        resolved = ResolutionResult(
            new=[ResolvedProduct(product=product, status="new")],
        )

        await builder.build(resolved)
        mock_graph.update_price_range.assert_called_once_with("P-001", 9.99, 9.99)


# --- IngestionPipeline Tests ---

class TestIngestionPipeline:
    @pytest.mark.asyncio
    async def test_ingest_csv_full_pipeline(self):
        # Set up mock components
        mock_parser = AsyncMock()
        mock_parser.parse_csv.return_value = [
            {"part_number": "6204-2RS", "name": "Bearing", "manufacturer": "SKF"},
        ]

        part_parser = PartNumberParser()
        normalizer = CatalogNormalizer(part_parser)

        mock_graph = AsyncMock()
        mock_graph.get_part.return_value = None
        mock_graph.resolve_part.return_value = []
        mock_graph.search_parts_fulltext.return_value = []
        mock_graph.upsert_part.return_value = {"sku": "6204-2RS"}

        resolver = EntityResolver(mock_graph)
        builder = GraphBuilder(mock_graph)

        pipeline = IngestionPipeline(
            parser=mock_parser,
            normalizer=normalizer,
            resolver=resolver,
            builder=builder,
        )

        result = await pipeline.ingest_csv(b"dummy")

        assert result.total_parsed == 1
        assert result.total_normalized == 1
        assert result.created == 1
        assert result.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_ingest_empty_csv(self):
        mock_parser = AsyncMock()
        mock_parser.parse_csv.return_value = []

        pipeline = IngestionPipeline(
            parser=mock_parser,
            normalizer=MagicMock(),
            resolver=MagicMock(),
            builder=MagicMock(),
        )

        result = await pipeline.ingest_csv(b"empty")
        assert result.total_parsed == 0
        assert result.success_rate == 0.0
