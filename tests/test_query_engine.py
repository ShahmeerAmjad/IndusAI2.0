import pytest
from unittest.mock import AsyncMock, MagicMock

from services.ai.models import IntentType, IntentResult, EntityResult
from services.ai.entity_extractor import EntityExtractor
from services.ai.part_number_parser import PartNumberParser
from services.graphrag.query_engine import GraphRAGQueryEngine, QueryResult
from services.graphrag.context_merger import ContextMerger, MergedContext, PartContext
from services.intent_classifier import IntentClassifier, INTENT_TO_MESSAGE_TYPE


# --- ContextMerger Tests ---

class TestContextMerger:
    @pytest.mark.asyncio
    async def test_merge_basic(self):
        merger = ContextMerger()
        results = [
            {"sku": "6204-2RS", "name": "Bearing", "manufacturer": "SKF",
             "specs": [{"name": "bore_mm", "value": 20, "unit": "mm"}]},
        ]
        context = await merger.merge(results)
        assert len(context.parts) == 1
        assert context.parts[0].sku == "6204-2RS"

    @pytest.mark.asyncio
    async def test_merge_empty(self):
        merger = ContextMerger()
        context = await merger.merge([])
        assert len(context.parts) == 0

    @pytest.mark.asyncio
    async def test_merge_with_inventory(self):
        mock_inventory = AsyncMock()
        mock_inventory.check_inventory.return_value = {
            "locations": [{"warehouse_code": "WH-01", "quantity": 150}]
        }
        merger = ContextMerger(inventory_service=mock_inventory)

        context = await merger.merge([{"sku": "6204-2RS", "name": "Bearing"}])
        assert context.parts[0].inventory == {"WH-01": 150}

    @pytest.mark.asyncio
    async def test_merge_with_pricing(self):
        mock_pricing = AsyncMock()
        mock_pricing.get_price.return_value = {
            "list_price": 5.50, "final_price": 4.75
        }
        merger = ContextMerger(pricing_service=mock_pricing)

        context = await merger.merge([{"sku": "6204-2RS", "name": "Bearing"}])
        assert context.parts[0].pricing["list_price"] == 5.50

    def test_context_to_text(self):
        context = MergedContext(parts=[
            PartContext(
                sku="6204-2RS", name="Deep Groove Bearing",
                manufacturer="SKF", category="Ball Bearings",
                specs=[{"name": "bore_mm", "value": 20, "unit": "mm"}],
                inventory={"WH-01": 150},
                pricing={"list_price": 5.50},
            ),
        ])
        text = context.to_text()
        assert "6204-2RS" in text
        assert "SKF" in text
        assert "bore_mm" in text
        assert "150" in text

    def test_context_to_text_empty(self):
        context = MergedContext()
        assert "No matching data" in context.to_text()


# --- IntentClassifier Tests ---

class TestIntentClassifier:
    def test_regex_classify_order(self):
        classifier = IntentClassifier()
        msg_type, confidence = classifier.classify("What is the status of my order #12345?")
        from models.models import MessageType
        assert msg_type == MessageType.ORDER_STATUS
        assert confidence >= 0.8

    def test_regex_classify_product(self):
        classifier = IntentClassifier()
        msg_type, _ = classifier.classify("Do you have bearing 6204-2RS in stock?")
        from models.models import MessageType
        assert msg_type == MessageType.PRODUCT_INQUIRY

    @pytest.mark.asyncio
    async def test_classify_intent_regex_fallback(self):
        classifier = IntentClassifier()  # No LLM
        result = await classifier.classify_intent("Track order PO-12345")
        assert result.intent == IntentType.ORDER_STATUS
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_classify_intent_with_llm(self):
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = '{"intent": "part_lookup", "confidence": 0.92}'

        classifier = IntentClassifier(llm_router=mock_llm)
        result = await classifier.classify_intent("Do you have 6204-2RS bearings?")
        assert result.intent == IntentType.PART_LOOKUP
        assert result.confidence == 0.92

    def test_intent_to_message_type_mapping(self):
        from models.models import MessageType
        assert INTENT_TO_MESSAGE_TYPE[IntentType.ORDER_STATUS] == MessageType.ORDER_STATUS
        assert INTENT_TO_MESSAGE_TYPE[IntentType.PART_LOOKUP] == MessageType.PRODUCT_INQUIRY
        assert INTENT_TO_MESSAGE_TYPE[IntentType.RETURN_REQUEST] == MessageType.RETURNS


# --- GraphRAGQueryEngine Tests ---

class TestGraphRAGQueryEngine:
    @pytest.fixture
    def engine(self):
        mock_graph = AsyncMock()
        mock_llm = AsyncMock()
        mock_classifier = AsyncMock()
        extractor = EntityExtractor()
        parser = PartNumberParser()

        mock_classifier.classify_intent.return_value = IntentResult(
            intent=IntentType.PART_LOOKUP, confidence=0.9
        )

        engine = GraphRAGQueryEngine(
            graph_service=mock_graph,
            llm_router=mock_llm,
            intent_classifier=mock_classifier,
            entity_extractor=extractor,
            part_parser=parser,
        )
        return engine, mock_graph, mock_llm

    @pytest.mark.asyncio
    async def test_process_query_graph_hit(self, engine):
        eng, mock_graph, mock_llm = engine

        # Graph returns a part
        mock_graph.get_part.return_value = {
            "sku": "6204-2RS", "name": "Deep Groove Bearing",
            "manufacturer": "SKF", "specs": [], "cross_refs": [],
        }
        mock_llm.chat.return_value = "The SKF 6204-2RS is a deep groove ball bearing."

        result = await eng.process_query("Tell me about 6204-2RS")

        assert result.parts_found >= 1
        assert "6204-2RS" in result.response
        assert result.intent.intent == IntentType.PART_LOOKUP

    @pytest.mark.asyncio
    async def test_process_query_vector_fallback(self, engine):
        eng, mock_graph, mock_llm = engine

        # Graph returns nothing
        mock_graph.get_part.return_value = None
        mock_graph.resolve_part.return_value = []
        mock_graph.search_parts_fulltext.return_value = []

        # Vector returns results
        mock_llm.embed_query.return_value = [0.1] * 1024
        mock_graph.search_parts_vector.return_value = [
            {"node": {"sku": "SIMILAR-001", "name": "Similar Part", "score": 0.85}}
        ]
        mock_llm.chat.return_value = "I found a similar part."

        result = await eng.process_query("Find me a 25mm sealed bearing")

        assert "Vector" in " ".join(result.graph_paths)
        assert result.parts_found >= 1

    @pytest.mark.asyncio
    async def test_process_query_no_results(self, engine):
        eng, mock_graph, mock_llm = engine

        mock_graph.get_part.return_value = None
        mock_graph.resolve_part.return_value = []
        mock_graph.search_parts_fulltext.return_value = []
        mock_llm.embed_query.return_value = [0.1] * 1024
        mock_graph.search_parts_vector.return_value = []
        mock_llm.chat.return_value = "I couldn't find matching parts."

        result = await eng.process_query("Do you have widget XYZ-999?")
        assert result.parts_found == 0

    @pytest.mark.asyncio
    async def test_process_query_llm_failure_fallback(self, engine):
        eng, mock_graph, mock_llm = engine

        mock_graph.get_part.return_value = {
            "sku": "6204-2RS", "name": "Bearing",
            "specs": [], "cross_refs": [],
        }
        mock_llm.chat.side_effect = RuntimeError("API down")

        result = await eng.process_query("Tell me about 6204-2RS")

        # Should fallback to structured response
        assert "6204-2RS" in result.response or "parts" in result.response.lower()

    @pytest.mark.asyncio
    async def test_process_query_with_sourcing(self):
        """Test the enhanced flow with seller matching."""
        mock_graph = AsyncMock()
        mock_llm = AsyncMock()
        mock_classifier = AsyncMock()
        mock_seller = AsyncMock()
        extractor = EntityExtractor()
        parser = PartNumberParser()

        mock_classifier.classify_intent.return_value = IntentResult(
            intent=IntentType.PART_LOOKUP, confidence=0.9
        )

        # Seller service returns listings
        mock_seller.find_listings_for_parts.return_value = [
            {
                "part_sku": "6204-2RS", "sku": "GR-6204", "price": 4.50,
                "seller_name": "Grainger", "seller_id": "s1",
                "qty_available": 200, "lead_time_days": 2,
                "reliability": 8.0, "warehouse_id": "w1",
                "lat": None, "lng": None,
            },
        ]

        from services.intelligence.price_comparator import PriceComparator
        engine = GraphRAGQueryEngine(
            graph_service=mock_graph,
            llm_router=mock_llm,
            intent_classifier=mock_classifier,
            entity_extractor=extractor,
            part_parser=parser,
            seller_service=mock_seller,
            price_comparator=PriceComparator(),
        )

        mock_graph.get_part.return_value = {
            "sku": "6204-2RS", "name": "Deep Groove Bearing",
            "manufacturer": "SKF", "specs": [], "cross_refs": [],
        }
        mock_llm.chat.return_value = "Found bearing from Grainger at $4.50/ea."

        result = await engine.process_query("Tell me about 6204-2RS")
        assert result.parts_found >= 1
        assert len(result.sourcing_results) == 1
        assert result.sourcing_results[0].seller_name == "Grainger"
        assert result.sourcing_results[0].unit_price == 4.50
