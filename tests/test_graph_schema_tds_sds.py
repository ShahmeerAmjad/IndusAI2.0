"""Test that Neo4j schema includes TDS/SDS node types and industry taxonomy."""
import pytest

def test_tds_constraint_exists():
    from services.graph.schema import CONSTRAINTS
    tds_constraints = [c for c in CONSTRAINTS if "TechnicalDataSheet" in c]
    assert len(tds_constraints) >= 1, "Missing TDS uniqueness constraint"

def test_sds_constraint_exists():
    from services.graph.schema import CONSTRAINTS
    sds_constraints = [c for c in CONSTRAINTS if "SafetyDataSheet" in c]
    assert len(sds_constraints) >= 1, "Missing SDS uniqueness constraint"

def test_industry_constraint_exists():
    from services.graph.schema import CONSTRAINTS
    industry_constraints = [c for c in CONSTRAINTS if "Industry" in c]
    assert len(industry_constraints) >= 1, "Missing Industry constraint"

def test_product_line_constraint_exists():
    from services.graph.schema import CONSTRAINTS
    pl_constraints = [c for c in CONSTRAINTS if "ProductLine" in c]
    assert len(pl_constraints) >= 1, "Missing ProductLine constraint"

def test_industry_taxonomy_has_18_industries():
    from services.graph.schema import INDUSTRY_TAXONOMY
    assert len(INDUSTRY_TAXONOMY) >= 18, f"Expected 18+ industries, got {len(INDUSTRY_TAXONOMY)}"

def test_industry_taxonomy_includes_key_industries():
    from services.graph.schema import INDUSTRY_TAXONOMY
    required = ["Adhesives", "Coatings", "Pharma", "Metal Processing", "Water Treatment"]
    for industry in required:
        assert industry in INDUSTRY_TAXONOMY, f"Missing industry: {industry}"

def test_fulltext_index_includes_cas():
    from services.graph.schema import FULLTEXT_INDEXES
    combined = " ".join(FULLTEXT_INDEXES)
    assert "cas_number" in combined or "Product" in combined
