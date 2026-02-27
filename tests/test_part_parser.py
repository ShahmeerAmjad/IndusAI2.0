from services.ai.part_number_parser import PartNumberParser
from services.ai.entity_extractor import EntityExtractor
from services.ai.models import PartCategory


class TestPartNumberParser:
    def setup_method(self):
        self.parser = PartNumberParser()

    def test_parse_bearing(self):
        results = self.parser.parse("6204-2RS")
        assert len(results) >= 1
        assert results[0].category == PartCategory.BEARING

    def test_parse_metric_fastener(self):
        results = self.parser.parse("M8x1.25x30")
        assert len(results) >= 1
        assert results[0].category == PartCategory.METRIC_FASTENER

    def test_parse_imperial_fastener(self):
        results = self.parser.parse("1/4-20 x 1.5")
        assert len(results) >= 1
        assert results[0].category == PartCategory.IMPERIAL_FASTENER

    def test_parse_belt(self):
        results = self.parser.parse("A48")
        assert len(results) >= 1
        assert results[0].category == PartCategory.BELT

    def test_parse_multiple(self):
        results = self.parser.parse("I need 6204-2RS and M8x1.25x30")
        assert len(results) >= 2

    def test_parse_empty(self):
        results = self.parser.parse("")
        assert len(results) == 0

    def test_parse_single_unknown(self):
        result = self.parser.parse_single("random text")
        assert result.category == PartCategory.UNKNOWN
        assert result.confidence == 0.0

    def test_bearing_decode_bore(self):
        results = self.parser.parse("6205-ZZ")
        assert len(results) >= 1
        bearing = results[0]
        assert bearing.parsed.get("bore_mm") == 25  # 05 * 5

    def test_bearing_decode_seal(self):
        results = self.parser.parse("6204-2RS")
        assert len(results) >= 1
        assert "2RS" in results[0].parsed.get("seal", "")


class TestEntityExtractor:
    def setup_method(self):
        self.extractor = EntityExtractor()

    def test_extract_part_numbers(self):
        result = self.extractor.extract("I need bearing 6204-2RS")
        assert "6204-2RS" in result.part_numbers

    def test_extract_quantities(self):
        result = self.extractor.extract("I need 100 pcs of 6204-2RS")
        assert len(result.quantities) > 0

    def test_extract_order_number(self):
        result = self.extractor.extract("What's the status of ORD-12345?")
        assert "ORD-12345" in result.order_numbers

    def test_extract_po_number(self):
        result = self.extractor.extract("Please check PO-98765")
        assert any("98765" in o for o in result.order_numbers)

    def test_extract_empty(self):
        result = self.extractor.extract("Hello, how are you?")
        assert len(result.part_numbers) == 0
        assert len(result.order_numbers) == 0
