"""Test TDS/SDS document storage, OCR extraction, and structured field parsing."""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Create a fake pdfplumber module so tests can patch it without installing
_mock_pdfplumber = MagicMock()
sys.modules.setdefault("pdfplumber", _mock_pdfplumber)

@pytest.mark.asyncio
async def test_store_document():
    from services.document_service import DocumentService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={"id": "doc-1", "doc_type": "TDS", "file_path": "/docs/tds.pdf"})
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db)
    result = await svc.store_document(
        product_id="prod-1",
        doc_type="TDS",
        file_bytes=b"fake-pdf",
        file_name="tds.pdf",
    )
    assert result["doc_type"] == "TDS"

@pytest.mark.asyncio
async def test_extract_tds_fields():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    sample_text = """
    Product: Polyox WSR-301
    Appearance: White powder
    Density: 1.21 g/cm³
    Flash Point: N/A
    pH (2% solution): 5.0-8.0
    Viscosity: 1200-4500 cP
    Storage: Cool, dry place
    """
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "appearance": "White powder",
            "density": "1.21 g/cm³",
            "flash_point": "N/A",
            "pH": "5.0-8.0",
            "viscosity": "1200-4500 cP",
            "storage_conditions": "Cool, dry place",
        }
        fields = await svc.extract_tds_fields(sample_text)
        assert fields["appearance"] == "White powder"
        assert fields["density"] == "1.21 g/cm³"

@pytest.mark.asyncio
async def test_extract_sds_fields():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    sample_text = """
    GHS Classification: Not classified
    CAS Number: 25322-68-3
    UN Number: N/A
    First Aid - Inhalation: Move to fresh air
    PPE: Safety glasses, gloves
    """
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "ghs_classification": "Not classified",
            "cas_numbers": ["25322-68-3"],
            "un_number": "N/A",
            "first_aid": "Inhalation: Move to fresh air",
            "ppe_requirements": "Safety glasses, gloves",
        }
        fields = await svc.extract_sds_fields(sample_text)
        assert fields["cas_numbers"] == ["25322-68-3"]

@pytest.mark.asyncio
async def test_get_documents_for_product():
    from services.document_service import DocumentService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetch=AsyncMock(return_value=[
            {"id": "d1", "doc_type": "TDS", "file_name": "tds.pdf", "is_current": True},
            {"id": "d2", "doc_type": "SDS", "file_name": "sds.pdf", "is_current": True},
        ])
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db)
    docs = await svc.get_documents_for_product("prod-1")
    assert len(docs) == 2
    assert docs[0]["doc_type"] == "TDS"


@pytest.mark.asyncio
async def test_call_llm_no_ai_service():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock(), ai_service=None)
    with pytest.raises(RuntimeError, match="AI service not configured"):
        await svc._call_llm("some prompt")


@pytest.mark.asyncio
async def test_call_llm_malformed_json():
    import json
    from services.document_service import DocumentService
    ai = MagicMock()
    ai.chat = AsyncMock(return_value="not valid json {{{")
    svc = DocumentService(MagicMock(), ai_service=ai)
    with pytest.raises(json.JSONDecodeError):
        await svc._call_llm("some prompt")


@pytest.mark.asyncio
async def test_extract_text_from_pdf_valid():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())

    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Page 1 content"
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "Page 2 content"

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page1, mock_page2]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        result = await svc.extract_text_from_pdf(b"fake-pdf")
    assert result == "Page 1 content\nPage 2 content"


@pytest.mark.asyncio
async def test_extract_text_from_pdf_empty_pages():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())

    mock_page = MagicMock()
    mock_page.extract_text.return_value = None

    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page, mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("pdfplumber.open", return_value=mock_pdf):
        result = await svc.extract_text_from_pdf(b"fake-pdf")
    assert result == ""


@pytest.mark.asyncio
async def test_extract_text_from_pdf_corrupt():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())

    with patch("pdfplumber.open", side_effect=Exception("Invalid PDF")):
        with pytest.raises(Exception, match="Invalid PDF"):
            await svc.extract_text_from_pdf(b"corrupt-data")


@pytest.mark.asyncio
async def test_get_documents_for_product_empty():
    from services.document_service import DocumentService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetch=AsyncMock(return_value=[])
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db)
    docs = await svc.get_documents_for_product("nonexistent")
    assert docs == []


@pytest.mark.asyncio
async def test_store_document_with_source_url():
    from services.document_service import DocumentService
    db = MagicMock()
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value={
        "id": "doc-1", "product_id": "prod-1", "doc_type": "TDS",
        "file_path": "/docs/TDS_tds.pdf", "file_name": "tds.pdf",
        "file_size_bytes": 8, "is_current": True, "created_at": "2026-01-01",
    })
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = DocumentService(db)

    with patch("services.document_service.Path.mkdir"), \
         patch("builtins.open", MagicMock()):
        result = await svc.store_document(
            product_id="prod-1", doc_type="TDS",
            file_bytes=b"fake-pdf", file_name="tds.pdf",
            source_url="https://example.com/tds.pdf",
        )
    # Verify source_url was passed as 6th arg
    call_args = mock_conn.fetchrow.call_args
    assert call_args[0][6] == "https://example.com/tds.pdf"


@pytest.mark.asyncio
async def test_extract_sds_fields_partial_response():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"ghs_classification": "Flammable"}
        fields = await svc.extract_sds_fields("some sds text")
        assert fields == {"ghs_classification": "Flammable"}
        assert "cas_numbers" not in fields


@pytest.mark.asyncio
async def test_extract_tds_fields_with_confidence():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "appearance": {"value": "White powder", "confidence": 0.95},
            "density": {"value": "1.21 g/cm³", "confidence": 0.92},
            "flash_point": {"value": "N/A", "confidence": 0.88},
            "viscosity": {"value": "1200-4500 cP", "confidence": 0.91},
            "pH": {"value": "5.0-8.0", "confidence": 0.85},
            "boiling_point": {"value": "100°C", "confidence": 0.70},
            "melting_point": {"value": "65°C", "confidence": 0.75},
            "solubility": {"value": "Soluble in water", "confidence": 0.93},
            "shelf_life": {"value": "24 months", "confidence": 0.60},
            "storage_conditions": {"value": "Cool, dry place", "confidence": 0.90},
            "recommended_uses": {"value": ["Adhesives", "Coatings"], "confidence": 0.87},
        }
        fields = await svc.extract_tds_fields_with_confidence("sample tds text")
        assert fields["appearance"]["confidence"] == 0.95
        assert fields["density"]["value"] == "1.21 g/cm³"
        assert fields["shelf_life"]["confidence"] < 0.7


@pytest.mark.asyncio
async def test_extract_sds_fields_with_confidence():
    from services.document_service import DocumentService
    svc = DocumentService(MagicMock())
    with patch.object(svc, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "ghs_classification": {"value": "Not classified", "confidence": 0.97},
            "cas_numbers": {"value": ["25322-68-3"], "confidence": 0.99},
            "un_number": {"value": "N/A", "confidence": 0.85},
            "hazard_statements": {"value": [], "confidence": 0.90},
            "precautionary_statements": {"value": ["P264"], "confidence": 0.82},
            "first_aid": {"value": "Move to fresh air", "confidence": 0.88},
            "ppe_requirements": {"value": "Safety glasses, gloves", "confidence": 0.91},
            "fire_fighting": {"value": "Use water spray", "confidence": 0.78},
            "environmental_hazards": {"value": "No known hazards", "confidence": 0.80},
            "transport_info": {"value": "Not regulated", "confidence": 0.93},
        }
        fields = await svc.extract_sds_fields_with_confidence("sample sds text")
        assert fields["cas_numbers"]["confidence"] == 0.99
        assert fields["ghs_classification"]["value"] == "Not classified"


@pytest.mark.asyncio
async def test_call_llm_strips_markdown_fences():
    """_call_llm should handle LLM responses wrapped in ```json fences."""
    from services.document_service import DocumentService
    svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
    svc._ai.chat = AsyncMock(return_value='```json\n{"density": "1.05 g/mL"}\n```')
    result = await svc._call_llm("Extract fields")
    assert result == {"density": "1.05 g/mL"}


@pytest.mark.asyncio
async def test_call_llm_strips_triple_backtick_only():
    """_call_llm should handle responses with ``` but no json tag."""
    from services.document_service import DocumentService
    svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
    svc._ai.chat = AsyncMock(return_value='```\n{"pH": "7.0"}\n```')
    result = await svc._call_llm("Extract fields")
    assert result == {"pH": "7.0"}


@pytest.mark.asyncio
async def test_extract_tds_fields_truncates_long_text():
    """Old extract_tds_fields should truncate text to 8000 chars."""
    from services.document_service import DocumentService
    svc = DocumentService(db_manager=MagicMock(), ai_service=MagicMock())
    captured_prompt = None
    async def capture_chat(prompt, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        return '{"density": "1.0"}'
    svc._ai.chat = capture_chat

    long_text = "A" * 20000
    await svc.extract_tds_fields(long_text)

    # The text portion of the prompt should be truncated
    assert len(captured_prompt) < 10000  # 8000 chars + prompt template
