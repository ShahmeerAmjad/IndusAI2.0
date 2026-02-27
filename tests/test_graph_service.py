import pytest
from unittest.mock import AsyncMock
from services.graph.graph_service import GraphService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    return GraphService(mock_db)


class TestGraphServiceUpsertPart:
    @pytest.mark.asyncio
    async def test_upsert_part_basic(self, service, mock_db):
        mock_db.execute_write.return_value = [{"p": {"sku": "6204-2RS", "name": "Bearing"}}]

        result = await service.upsert_part(
            sku="6204-2RS", name="Bearing", description="Deep groove",
            category="Ball Bearings", manufacturer="SKF"
        )

        assert result["sku"] == "6204-2RS"
        mock_db.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_part_with_embedding(self, service, mock_db):
        mock_db.execute_write.return_value = [{"p": {"sku": "TEST"}}]

        await service.upsert_part(
            sku="TEST", name="Test", embedding=[0.1, 0.2, 0.3]
        )

        # Should call execute_write twice: once for MERGE, once for embedding
        assert mock_db.execute_write.call_count == 2

    @pytest.mark.asyncio
    async def test_upsert_part_with_specs(self, service, mock_db):
        mock_db.execute_write.return_value = [{"p": {"sku": "TEST"}}]

        await service.upsert_part(
            sku="TEST", name="Test", specs={"bore_mm": 20, "od_mm": 47}
        )

        # 1 for MERGE + 2 for specs
        assert mock_db.execute_write.call_count == 3


class TestGraphServiceGetPart:
    @pytest.mark.asyncio
    async def test_get_part_found(self, service, mock_db):
        mock_db.execute_read.return_value = [
            {"p": {"sku": "6204-2RS", "name": "Bearing", "specs": [], "cross_refs": []}}
        ]

        result = await service.get_part("6204-2RS")
        assert result["sku"] == "6204-2RS"

    @pytest.mark.asyncio
    async def test_get_part_not_found(self, service, mock_db):
        mock_db.execute_read.return_value = []

        result = await service.get_part("NONEXISTENT")
        assert result is None


class TestGraphServiceCrossReferences:
    @pytest.mark.asyncio
    async def test_add_cross_reference(self, service, mock_db):
        mock_db.execute_write.return_value = [
            {"from_sku": "SKF-6204", "to_sku": "NSK-6204", "type": "EQUIVALENT_TO"}
        ]

        result = await service.add_cross_reference("SKF-6204", "NSK-6204")
        assert result["type"] == "EQUIVALENT_TO"

    @pytest.mark.asyncio
    async def test_add_cross_reference_invalid_type(self, service):
        with pytest.raises(ValueError, match="ref_type must be one of"):
            await service.add_cross_reference("A", "B", ref_type="INVALID")

    @pytest.mark.asyncio
    async def test_resolve_part(self, service, mock_db):
        mock_db.execute_read.return_value = [
            {
                "part": {"sku": "6204-2RS", "name": "SKF Bearing"},
                "equivalents": [
                    {"sku": "6204DDU", "name": "NSK Bearing", "manufacturer": "NSK"},
                ],
            }
        ]

        parts = await service.resolve_part("6204-2RS")
        assert len(parts) == 2
        assert parts[0]["sku"] == "6204-2RS"
        assert parts[1]["sku"] == "6204DDU"


class TestGraphServiceSpecs:
    @pytest.mark.asyncio
    async def test_set_part_specs(self, service, mock_db):
        mock_db.execute_write.return_value = []

        await service.set_part_specs("6204-2RS", {"bore_mm": 20, "od_mm": 47})
        assert mock_db.execute_write.call_count == 2

    @pytest.mark.asyncio
    async def test_set_part_specs_with_units(self, service, mock_db):
        mock_db.execute_write.return_value = []

        await service.set_part_specs("6204-2RS", {
            "bore_mm": {"value": 20, "unit": "mm"},
        })
        call_args = mock_db.execute_write.call_args[0]
        params = mock_db.execute_write.call_args[1] if mock_db.execute_write.call_args[1] else call_args[1]
        assert params["value"] == 20
        assert params["unit"] == "mm"


class TestGraphServiceAssemblies:
    @pytest.mark.asyncio
    async def test_add_to_assembly(self, service, mock_db):
        mock_db.execute_write.return_value = [{"part": "6204-2RS", "assembly": "EM3558T"}]

        result = await service.add_to_assembly("6204-2RS", "EM3558T", position="DE", qty=1)
        assert result["assembly"] == "EM3558T"

    @pytest.mark.asyncio
    async def test_get_assembly_bom(self, service, mock_db):
        mock_db.execute_read.return_value = [
            {"p": {"sku": "6204-2RS", "position": "DE", "quantity": 1}},
            {"p": {"sku": "6205-2RS", "position": "NDE", "quantity": 1}},
        ]

        bom = await service.get_assembly_bom("EM3558T")
        assert len(bom) == 2


class TestGraphServiceSync:
    @pytest.mark.asyncio
    async def test_update_inventory_cache(self, service, mock_db):
        mock_db.execute_write.return_value = []
        await service.update_inventory_cache("6204-2RS", "WH-01", 150)
        mock_db.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_price_range(self, service, mock_db):
        mock_db.execute_write.return_value = []
        await service.update_price_range("6204-2RS", 5.50, 8.75)
        mock_db.execute_write.assert_called_once()
