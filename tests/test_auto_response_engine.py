"""Tests for AutoResponseEngine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai.models import (
    EntityResult, IntentResult, IntentType, MultiIntentResult,
)
from services.auto_response_engine import AutoResponseEngine


@pytest.fixture
def mock_graph():
    g = AsyncMock()
    g.get_part.return_value = {
        "sku": "EP-200", "name": "Epoxy Resin EP-200",
        "manufacturer": "ChemCorp", "category": "Adhesives",
    }
    g.search_parts_fulltext.return_value = [
        {"node": {"sku": "EP-200", "name": "Epoxy Resin EP-200"}}
    ]
    return g


@pytest.fixture
def mock_tds_sds():
    t = AsyncMock()
    t.get_tds_properties.return_value = {
        "props": {
            "viscosity": "1200 cP", "cure_time": "24h",
            "pdf_url": "/docs/EP-200-TDS.pdf",
        }
    }
    t.get_sds_properties.return_value = {
        "props": {
            "flash_point": "200°C", "hazard_class": "Non-hazardous",
            "pdf_url": "/docs/EP-200-SDS.pdf",
        }
    }
    return t


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.chat.return_value = (
        "Dear Customer,\n\nThank you for your inquiry. "
        "Please find the requested information below.\n\n"
        "Best regards,\nSupport Team"
    )
    return llm


@pytest.fixture
def engine(mock_graph, mock_tds_sds, mock_llm):
    return AutoResponseEngine(
        graph_service=mock_graph,
        tds_sds_service=mock_tds_sds,
        llm_router=mock_llm,
        db_manager=None,
    )


def _make_classification(*intent_types, entities=None):
    """Helper to build a MultiIntentResult."""
    intents = [
        IntentResult(intent=it, confidence=0.85)
        for it in intent_types
    ]
    return MultiIntentResult(
        intents=intents,
        entities=entities or EntityResult(),
    )


class TestGenerateDraft:
    """Test the main generate_draft flow."""

    @pytest.mark.asyncio
    async def test_tds_sds_response_with_attachments(self, engine, mock_tds_sds):
        classification = _make_classification(
            IntentType.REQUEST_TDS_SDS,
            entities=EntityResult(part_numbers=["EP-200"]),
        )
        result = await engine.generate_draft(
            "Please send TDS and SDS for EP-200",
            classification,
            customer_account="ACME Corp",
        )
        assert result["response_text"]
        assert "/docs/EP-200-TDS.pdf" in result["attachments"]
        assert "/docs/EP-200-SDS.pdf" in result["attachments"]
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_quote_response_with_pricing(self, engine, mock_graph):
        classification = _make_classification(
            IntentType.REQUEST_QUOTE,
            entities=EntityResult(
                part_numbers=["EP-200"],
                quantities={"EP-200": 100},
            ),
        )
        result = await engine.generate_draft(
            "Need a quote for 100 units of EP-200",
            classification,
            customer_account="ACME Corp",
        )
        assert result["response_text"]
        assert "request_quote" in result["metadata"]["intents"]
        mock_graph.get_part.assert_called_with("EP-200")

    @pytest.mark.asyncio
    async def test_multi_intent_combined(self, engine):
        classification = _make_classification(
            IntentType.REQUEST_QUOTE,
            IntentType.REQUEST_TDS_SDS,
            IntentType.SAMPLE_REQUEST,
            entities=EntityResult(part_numbers=["EP-200"]),
        )
        result = await engine.generate_draft(
            "Quote + TDS + sample please for EP-200",
            classification,
            customer_account="ACME Corp",
        )
        assert len(result["metadata"]["intents"]) == 3
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_missing_product_graceful(self):
        """No graph service → still produces a draft."""
        engine = AutoResponseEngine(
            graph_service=None,
            tds_sds_service=None,
            llm_router=AsyncMock(return_value="Draft response here"),
        )
        engine._llm.chat = AsyncMock(return_value="Draft response here")
        classification = _make_classification(
            IntentType.REQUEST_QUOTE,
            entities=EntityResult(part_numbers=["UNKNOWN-SKU"]),
        )
        result = await engine.generate_draft(
            "Quote for UNKNOWN-SKU",
            classification,
        )
        assert result["response_text"]

    @pytest.mark.asyncio
    async def test_no_graph_service_fallback(self):
        """Engine works without graph service."""
        llm = AsyncMock()
        llm.chat.return_value = "Fallback draft"
        engine = AutoResponseEngine(llm_router=llm)

        classification = _make_classification(
            IntentType.ORDER_STATUS,
            entities=EntityResult(order_numbers=["PO-12345"], po_numbers=["PO-12345"]),
        )
        result = await engine.generate_draft(
            "Where is PO-12345?",
            classification,
        )
        assert result["response_text"] == "Fallback draft"
        assert result["confidence"] > 0

    @pytest.mark.asyncio
    async def test_no_intents_returns_empty(self, engine):
        classification = MultiIntentResult(intents=[], entities=EntityResult())
        result = await engine.generate_draft("Hello", classification)
        assert result["response_text"] == ""
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_confidence_reduced_on_errors(self):
        """When all context gathering fails, confidence is halved."""
        graph = AsyncMock()
        graph.get_part.side_effect = Exception("DB down")
        llm = AsyncMock()
        llm.chat.return_value = "Draft with errors"

        engine = AutoResponseEngine(graph_service=graph, llm_router=llm)
        classification = _make_classification(
            IntentType.TECHNICAL_SUPPORT,
            entities=EntityResult(part_numbers=["X"]),
        )
        result = await engine.generate_draft("Help with X", classification)
        # Handler raises → context has error → data_factor = 0.5 or 0.75
        assert result["confidence"] <= 0.85


class TestConfidenceCalculation:
    """Test confidence logic."""

    def test_full_confidence(self):
        engine = AutoResponseEngine()
        classification = _make_classification(IntentType.REQUEST_QUOTE)
        contexts = [{"intent": "request_quote", "context": {"products": []}}]
        conf = engine._calculate_confidence(classification, contexts)
        assert conf == 0.85  # 0.85 * 1.0

    def test_reduced_for_all_errors(self):
        engine = AutoResponseEngine()
        classification = _make_classification(IntentType.REQUEST_QUOTE)
        contexts = [{"intent": "request_quote", "context": {"error": "DB down"}}]
        conf = engine._calculate_confidence(classification, contexts)
        assert conf == round(0.85 * 0.5, 3)

    def test_partial_errors(self):
        engine = AutoResponseEngine()
        classification = _make_classification(
            IntentType.REQUEST_QUOTE, IntentType.ORDER_STATUS
        )
        contexts = [
            {"intent": "request_quote", "context": {"products": []}},
            {"intent": "order_status", "context": {"error": "not found"}},
        ]
        conf = engine._calculate_confidence(classification, contexts)
        assert conf == round(0.85 * 0.75, 3)


class TestBatchProcessInbox:
    """Test batch email processing."""

    @pytest.mark.asyncio
    async def test_batch_process_inbox(self, engine):
        """batch_process_inbox should process multiple emails and return aggregate stats."""
        emails = [
            {"id": "msg-1", "body": "Need TDS for product EP-200",
             "classification": _make_classification(IntentType.REQUEST_TDS_SDS,
                                                     entities=EntityResult(part_numbers=["EP-200"]))},
            {"id": "msg-2", "body": "Quote for product EP-200",
             "classification": _make_classification(IntentType.REQUEST_QUOTE,
                                                     entities=EntityResult(part_numbers=["EP-200"],
                                                                           quantities={"EP-200": 50}))},
        ]

        results = await engine.batch_process_inbox(emails)

        assert len(results) == 2
        assert all(r["response_text"] for r in results)
        assert results[0]["metadata"]["intents"] == ["request_tds_sds"]

    @pytest.mark.asyncio
    async def test_batch_process_inbox_with_error(self, engine, mock_llm):
        """If one email fails, others should still be processed."""
        call_count = 0
        async def flaky_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("LLM timeout")
            return "Draft response"

        mock_llm.chat.side_effect = flaky_chat

        emails = [
            {"id": "msg-1", "body": "Hello",
             "classification": _make_classification(IntentType.REQUEST_QUOTE,
                                                     entities=EntityResult(part_numbers=["EP-200"]))},
            {"id": "msg-2", "body": "World",
             "classification": _make_classification(IntentType.ORDER_STATUS,
                                                     entities=EntityResult(order_numbers=["PO-1"]))},
        ]

        results = await engine.batch_process_inbox(emails)
        assert len(results) == 2
        # First failed, second should succeed
        assert any(r["response_text"] for r in results)

    @pytest.mark.asyncio
    async def test_batch_process_inbox_progress_callback(self, engine):
        """Progress callback should be called for each email."""
        progress_events = []
        emails = [
            {"id": "msg-1", "body": "Test",
             "classification": _make_classification(IntentType.ORDER_STATUS,
                                                     entities=EntityResult(order_numbers=["PO-1"]))},
        ]

        await engine.batch_process_inbox(emails, on_progress=progress_events.append)
        assert any(e.get("stage") == "processing" for e in progress_events)
        assert any(e.get("stage") == "done" for e in progress_events)


class TestModuleDI:
    def test_set_get_response_engine(self):
        from services.auto_response_engine import set_response_engine, get_response_engine
        mock = MagicMock()
        set_response_engine(mock)
        assert get_response_engine() is mock
        set_response_engine(None)
