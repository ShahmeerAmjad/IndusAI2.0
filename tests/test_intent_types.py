"""Test that IntentType enum has all 9 supplier-sales intents."""
import pytest

def test_intent_type_has_9_intents():
    from services.ai.models import IntentType
    expected = [
        "place_order", "request_quote", "request_tds_sds",
        "order_status", "technical_support", "return_complaint",
        "reorder", "account_inquiry", "sample_request",
    ]
    actual = [i.value for i in IntentType]
    for e in expected:
        assert e in actual, f"Missing intent: {e}"

def test_multi_intent_result_model():
    from services.ai.models import MultiIntentResult, IntentResult, IntentType
    result = MultiIntentResult(intents=[
        IntentResult(intent=IntentType.REQUEST_QUOTE, confidence=0.95, text_span="quote for 500kg"),
        IntentResult(intent=IntentType.REQUEST_TDS_SDS, confidence=0.98, text_span="send me the SDS"),
    ])
    assert len(result.intents) == 2

def test_entity_result_has_cas_and_po():
    from services.ai.models import EntityResult
    er = EntityResult(
        part_numbers=["WSR-301"],
        cas_numbers=["25322-68-3"],
        po_numbers=["PO-12345"],
        quantities={"WSR-301": 500},
    )
    assert er.cas_numbers == ["25322-68-3"]
    assert er.po_numbers == ["PO-12345"]
