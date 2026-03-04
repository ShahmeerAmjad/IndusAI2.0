"""Tests for MultiIntentClassifier."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.ai.models import IntentType, MultiIntentResult
from services.multi_intent_classifier import MultiIntentClassifier


@pytest.fixture
def classifier():
    return MultiIntentClassifier(llm_router=None)


@pytest.fixture
def classifier_with_llm():
    llm = AsyncMock()
    return MultiIntentClassifier(llm_router=llm), llm


class TestPatternClassification:
    """Test synchronous pattern matching."""

    def test_single_intent_quote(self, classifier):
        result = classifier.classify_patterns("Can I get a quote for 100 units of SKU-1234?")
        intents = {r.intent for r in result.intents}
        assert IntentType.REQUEST_QUOTE in intents

    def test_single_intent_tds_sds(self, classifier):
        result = classifier.classify_patterns("Please send me the SDS for product ABC-100")
        intents = {r.intent for r in result.intents}
        assert IntentType.REQUEST_TDS_SDS in intents

    def test_multi_intent_three_intents(self, classifier):
        """Email with quote request, TDS request, and sample request."""
        email = (
            "Hi, I'd like to get a quote for your epoxy resin line. "
            "Also, can you send me the TDS and SDS for product EP-200? "
            "If possible, I'd love to get a free sample before ordering."
        )
        result = classifier.classify_patterns(email)
        intents = {r.intent for r in result.intents}
        assert IntentType.REQUEST_QUOTE in intents
        assert IntentType.REQUEST_TDS_SDS in intents
        assert IntentType.SAMPLE_REQUEST in intents
        assert len(result.intents) >= 3

    def test_reorder_intent(self, classifier):
        result = classifier.classify_patterns("I'd like to re-order the same as last time.")
        intents = {r.intent for r in result.intents}
        assert IntentType.REORDER in intents

    def test_sample_request(self, classifier):
        result = classifier.classify_patterns("Can we get a trial batch for evaluation?")
        intents = {r.intent for r in result.intents}
        assert IntentType.SAMPLE_REQUEST in intents

    def test_return_complaint(self, classifier):
        result = classifier.classify_patterns("The shipment arrived damaged. I need a refund or RMA.")
        intents = {r.intent for r in result.intents}
        assert IntentType.RETURN_COMPLAINT in intents

    def test_entity_extraction_part_number(self, classifier):
        result = classifier.classify_patterns("Need a quote for SKU-4567, 50 pcs")
        assert "SKU-4567" in result.entities.part_numbers

    def test_entity_extraction_po_number(self, classifier):
        result = classifier.classify_patterns("What's the status of PO-12345?")
        assert any("12345" in o for o in result.entities.order_numbers)

    def test_entity_extraction_cas_number(self, classifier):
        result = classifier.classify_patterns(
            "Send the SDS for CAS 7732-18-5 and CAS 64-17-5"
        )
        assert "7732-18-5" in result.entities.cas_numbers
        assert "64-17-5" in result.entities.cas_numbers

    def test_no_intent_found(self, classifier):
        result = classifier.classify_patterns("Hello, just wanted to say hi.")
        assert len(result.intents) == 0

    def test_deduplication(self, classifier):
        """Same intent shouldn't appear twice even if multiple patterns match."""
        result = classifier.classify_patterns(
            "I need a quote. Can you send me pricing? What's the cost?"
        )
        quote_intents = [r for r in result.intents if r.intent == IntentType.REQUEST_QUOTE]
        assert len(quote_intents) == 1
        # But confidence should be boosted for multiple matches
        assert quote_intents[0].confidence > 0.75

    def test_text_span_populated(self, classifier):
        result = classifier.classify_patterns("Please send the SDS for this product")
        tds_results = [r for r in result.intents if r.intent == IntentType.REQUEST_TDS_SDS]
        assert len(tds_results) == 1
        assert tds_results[0].text_span is not None


class TestAsyncClassification:
    """Test async classify() with LLM fallback."""

    @pytest.mark.asyncio
    async def test_pattern_match_no_llm_needed(self, classifier):
        result = await classifier.classify("I need a quote for product X")
        intents = {r.intent for r in result.intents}
        assert IntentType.REQUEST_QUOTE in intents

    @pytest.mark.asyncio
    async def test_llm_fallback_for_ambiguous(self, classifier_with_llm):
        clf, llm = classifier_with_llm
        llm.chat.return_value = json.dumps({
            "intents": [
                {"intent": "technical_support", "confidence": 0.8, "text_span": "formulation help"},
            ]
        })
        # Ambiguous text that won't match patterns well
        result = await clf.classify("We're having some issues with the batch we received")
        # Should have called LLM
        assert llm.chat.called

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self, classifier_with_llm):
        clf, llm = classifier_with_llm
        llm.chat.side_effect = Exception("API timeout")
        # Should not raise, returns pattern result (even if empty)
        result = await clf.classify("Random gibberish that matches nothing")
        assert isinstance(result, MultiIntentResult)

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json(self, classifier_with_llm):
        clf, llm = classifier_with_llm
        llm.chat.return_value = "not valid json at all"
        result = await clf.classify("Some ambiguous message")
        assert isinstance(result, MultiIntentResult)


class TestModuleDI:
    """Test module-level dependency injection."""

    def test_set_get_classifier(self):
        from services.multi_intent_classifier import set_classifier, get_classifier
        mock = MagicMock()
        set_classifier(mock)
        assert get_classifier() is mock
        set_classifier(None)
