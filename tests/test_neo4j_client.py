import pytest
from unittest.mock import AsyncMock, patch
from services.graph.neo4j_client import Neo4jClient


def test_neo4j_client_init():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    assert client._uri == "bolt://localhost:7687"
    assert client._user == "neo4j"
    assert client._driver is None


@pytest.mark.asyncio
async def test_health_check_unhealthy():
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
    result = await client.health_check()
    assert result["status"] == "unhealthy"
