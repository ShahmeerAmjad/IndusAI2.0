"""Tests for routes.customer_accounts — CRUD and email lookup."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from routes.customer_accounts import router, set_customer_account_services


SAMPLE_ACCOUNT = {
    "id": "acc-1", "name": "John Smith", "email": "john@acme.com",
    "phone": "555-1234", "company": "ACME Corp",
    "account_number": "A-100", "pricing_tier": "standard",
    "payment_terms": "net30", "created_at": "2026-03-05",
}


@pytest.fixture(autouse=True)
def setup_services():
    mock_svc = MagicMock()
    mock_svc.list_accounts = AsyncMock(return_value=[SAMPLE_ACCOUNT])
    mock_svc.create_account = AsyncMock(return_value=SAMPLE_ACCOUNT)
    mock_svc.get_account = AsyncMock(return_value=SAMPLE_ACCOUNT)
    mock_svc.update_account = AsyncMock(return_value={**SAMPLE_ACCOUNT, "name": "Jane Smith"})
    mock_svc.lookup_by_email = AsyncMock(return_value=SAMPLE_ACCOUNT)
    set_customer_account_services(account_service=mock_svc)
    yield mock_svc
    set_customer_account_services(None)


class TestListAccounts:
    @pytest.mark.asyncio
    async def test_list(self, setup_services):
        from routes.customer_accounts import list_accounts
        result = await list_accounts()
        assert len(result["accounts"]) == 1
        setup_services.list_accounts.assert_called_once()


class TestCreateAccount:
    @pytest.mark.asyncio
    async def test_create(self, setup_services):
        from routes.customer_accounts import create_account, CreateAccountRequest
        body = CreateAccountRequest(name="John Smith", email="john@acme.com", company="ACME Corp")
        result = await create_account(body)
        assert result["id"] == "acc-1"
        setup_services.create_account.assert_called_once()


class TestGetAccount:
    @pytest.mark.asyncio
    async def test_get_found(self, setup_services):
        from routes.customer_accounts import get_account
        result = await get_account("acc-1")
        assert result["name"] == "John Smith"

    @pytest.mark.asyncio
    async def test_get_not_found(self, setup_services):
        setup_services.get_account.return_value = None
        from routes.customer_accounts import get_account
        with pytest.raises(Exception) as exc_info:
            await get_account("nonexistent")
        assert exc_info.value.status_code == 404


class TestUpdateAccount:
    @pytest.mark.asyncio
    async def test_update(self, setup_services):
        from routes.customer_accounts import update_account, UpdateAccountRequest
        body = UpdateAccountRequest(name="Jane Smith")
        result = await update_account("acc-1", body)
        assert result["name"] == "Jane Smith"

    @pytest.mark.asyncio
    async def test_update_not_found(self, setup_services):
        setup_services.update_account.return_value = None
        from routes.customer_accounts import update_account, UpdateAccountRequest
        body = UpdateAccountRequest(name="X")
        with pytest.raises(Exception) as exc_info:
            await update_account("nonexistent", body)
        assert exc_info.value.status_code == 404


class TestLookupByEmail:
    @pytest.mark.asyncio
    async def test_lookup_found(self, setup_services):
        from routes.customer_accounts import lookup_by_email
        result = await lookup_by_email("john@acme.com")
        assert result["email"] == "john@acme.com"

    @pytest.mark.asyncio
    async def test_lookup_not_found(self, setup_services):
        setup_services.lookup_by_email.return_value = None
        from routes.customer_accounts import lookup_by_email
        with pytest.raises(Exception) as exc_info:
            await lookup_by_email("nobody@test.com")
        assert exc_info.value.status_code == 404
