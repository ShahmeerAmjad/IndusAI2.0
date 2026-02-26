import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_auth_schema_strings_exist():
    from services.platform.schema import PLATFORM_SCHEMA, PLATFORM_INDEXES
    assert "CREATE TABLE IF NOT EXISTS organizations" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS users" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS locations" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS refresh_tokens" in PLATFORM_SCHEMA
    assert "idx_users_email" in PLATFORM_INDEXES


class TestAuthService:
    def setup_method(self):
        from services.auth_service import AuthService
        self.db = MagicMock()
        self.db.pool = MagicMock()
        self.settings = MagicMock()
        self.settings.secret_key = "a" * 32
        self.auth = AuthService(db_manager=self.db, settings=self.settings)

    def test_hash_password(self):
        hashed = self.auth.hash_password("mypassword123")
        assert hashed != "mypassword123"
        assert self.auth.verify_password("mypassword123", hashed)

    def test_verify_password_wrong(self):
        hashed = self.auth.hash_password("correct")
        assert not self.auth.verify_password("wrong", hashed)

    def test_create_access_token(self):
        token = self.auth.create_access_token(
            user_id="u1", org_id="o1", role="buyer"
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        token = self.auth.create_access_token(
            user_id="u1", org_id="o1", role="buyer"
        )
        payload = self.auth.decode_access_token(token)
        assert payload["user_id"] == "u1"
        assert payload["org_id"] == "o1"
        assert payload["role"] == "buyer"

    def test_decode_expired_token_raises(self):
        import jwt as pyjwt
        from datetime import datetime, timezone, timedelta
        payload = {
            "user_id": "u1", "org_id": "o1", "role": "buyer",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = pyjwt.encode(payload, self.settings.secret_key, algorithm="HS256")
        with pytest.raises(ValueError, match="expired"):
            self.auth.decode_access_token(token)

    @pytest.mark.asyncio
    async def test_signup_creates_org_and_user(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=[
            None,  # email check: not found
            {"id": "org-1", "name": "Acme", "slug": "acme"},  # org insert
            {"id": "user-1", "email": "a@b.com", "name": "Test", "role": "admin", "org_id": "org-1"},  # user insert
        ])
        self.db.pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()))

        result = await self.auth.signup(
            email="a@b.com", password="pass1234", name="Test", org_name="Acme"
        )
        assert result["user"]["email"] == "a@b.com"
        assert "access_token" in result

    @pytest.mark.asyncio
    async def test_signup_duplicate_email_raises(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": "exists"})  # email exists
        self.db.pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock(return_value=False)))

        with pytest.raises(ValueError, match="already registered"):
            await self.auth.signup(
                email="a@b.com", password="pass", name="Test", org_name="Acme"
            )
