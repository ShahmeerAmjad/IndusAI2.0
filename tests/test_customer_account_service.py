"""Test customer account CRUD and email-based lookup."""
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_create_customer_account():
    from services.customer_account_service import CustomerAccountService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={
            "id": "ca-1", "name": "John Doe", "email": "john@acme.com",
            "company": "Acme Corp", "pricing_tier": "premium"
        })
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = CustomerAccountService(db)
    result = await svc.create_account({
        "name": "John Doe", "email": "john@acme.com",
        "company": "Acme Corp", "pricing_tier": "premium"
    })
    assert result["company"] == "Acme Corp"

@pytest.mark.asyncio
async def test_lookup_by_email():
    from services.customer_account_service import CustomerAccountService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value={
            "id": "ca-1", "name": "John Doe", "email": "john@acme.com",
            "company": "Acme Corp", "pricing_tier": "premium"
        })
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = CustomerAccountService(db)
    result = await svc.lookup_by_email("john@acme.com")
    assert result["name"] == "John Doe"

@pytest.mark.asyncio
async def test_lookup_by_email_returns_none():
    from services.customer_account_service import CustomerAccountService
    db = MagicMock()
    db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
        fetchrow=AsyncMock(return_value=None)
    ))
    db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    svc = CustomerAccountService(db)
    result = await svc.lookup_by_email("unknown@example.com")
    assert result is None
