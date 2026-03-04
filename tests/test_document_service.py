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
