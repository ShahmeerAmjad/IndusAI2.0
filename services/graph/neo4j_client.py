"""Async Neo4j client for knowledge graph operations."""

import logging
from contextlib import asynccontextmanager
from neo4j import AsyncGraphDatabase, AsyncDriver

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Manages Neo4j connection lifecycle and provides query execution."""

    def __init__(self, uri: str, user: str, password: str):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        await self._driver.verify_connectivity()
        logger.info("Connected to Neo4j at %s", self._uri)

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            logger.info("Neo4j connection closed")

    @asynccontextmanager
    async def session(self, database: str = "neo4j"):
        async with self._driver.session(database=database) as session:
            yield session

    async def execute_read(self, query: str, parameters: dict | None = None):
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]

    async def execute_write(self, query: str, parameters: dict | None = None):
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]

    async def health_check(self) -> dict:
        try:
            result = await self.execute_read("RETURN 1 AS ok")
            return {"status": "healthy", "connected": True}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
