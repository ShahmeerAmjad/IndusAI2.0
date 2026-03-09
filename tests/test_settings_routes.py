"""Tests for routes.settings — API key management."""

import pytest
from unittest.mock import patch

from routes.settings import router, _mask_key, _read_env, _write_env, MANAGED_KEYS


@pytest.fixture()
def env_file(tmp_path):
    """Create a temporary .env file for testing."""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# IndusAI config\n"
        "ANTHROPIC_API_KEY=sk-ant-api03-realkey1234567890abcdef\n"
        "SOME_OTHER_VAR=hello\n"
    )
    return env_path


class TestMaskKey:
    def test_mask_normal_key(self):
        assert _mask_key("sk-ant-api03-realkey1234567890abcdef") == "sk-ant-...cdef"

    def test_mask_short_key(self):
        assert _mask_key("short") == "****"

    def test_mask_empty_key(self):
        assert _mask_key("") == ""

    def test_mask_none_key(self):
        assert _mask_key(None) == ""

    def test_mask_exactly_8_chars(self):
        assert _mask_key("12345678") == "1234567...5678"


class TestGetKeys:
    @pytest.mark.asyncio
    async def test_get_keys_empty(self):
        """When no .env exists, all keys show configured=False."""
        with patch("routes.settings._read_env", return_value={}):
            from routes.settings import get_keys
            result = await get_keys()

        assert "keys" in result
        for key_name in MANAGED_KEYS:
            entry = result["keys"][key_name.lower()]
            assert entry["configured"] is False
            assert entry["preview"] == ""

    @pytest.mark.asyncio
    async def test_get_keys_masked(self):
        """Configured keys are masked — only last 4 chars visible."""
        fake_env = {
            "ANTHROPIC_API_KEY": "sk-ant-api03-realkey1234567890abcdef",
            "VOYAGE_API_KEY": "voy-testkey9999",
        }
        with patch("routes.settings._read_env", return_value=fake_env):
            from routes.settings import get_keys
            result = await get_keys()

        anthropic = result["keys"]["anthropic_api_key"]
        assert anthropic["configured"] is True
        assert anthropic["preview"].endswith("cdef")
        assert "realkey" not in anthropic["preview"]

        voyage = result["keys"]["voyage_api_key"]
        assert voyage["configured"] is True
        assert voyage["preview"].endswith("9999")

        firecrawl = result["keys"]["firecrawl_api_key"]
        assert firecrawl["configured"] is False


class TestUpdateKeys:
    @pytest.mark.asyncio
    async def test_update_keys(self):
        """PUT saves keys, GET reflects them as configured."""
        store: dict[str, str] = {}

        with (
            patch("routes.settings._read_env", return_value=store),
            patch("routes.settings._write_env") as mock_write,
            patch.dict("os.environ", {}, clear=False),
        ):
            from routes.settings import update_keys, KeysUpdateRequest, get_keys

            body = KeysUpdateRequest(
                anthropic_api_key="sk-ant-new-key-abcdefghij",
                firecrawl_api_key="fc-live-xyz123456789",
            )
            result = await update_keys(body)

            assert len(result["updated"]) == 2
            assert "ANTHROPIC_API_KEY" in result["updated"]
            assert "FIRECRAWL_API_KEY" in result["updated"]
            mock_write.assert_called_once()

            # Verify the env dict was mutated correctly
            written = mock_write.call_args[0][0]
            assert written["ANTHROPIC_API_KEY"] == "sk-ant-new-key-abcdefghij"
            assert written["FIRECRAWL_API_KEY"] == "fc-live-xyz123456789"

    @pytest.mark.asyncio
    async def test_update_partial(self):
        """Only provided keys are updated, others unchanged."""
        existing = {
            "ANTHROPIC_API_KEY": "sk-ant-old-key",
            "FIRECRAWL_API_KEY": "fc-old-key",
        }

        with (
            patch("routes.settings._read_env", return_value=existing.copy()),
            patch("routes.settings._write_env") as mock_write,
            patch.dict("os.environ", {}, clear=False),
        ):
            from routes.settings import update_keys, KeysUpdateRequest

            body = KeysUpdateRequest(voyage_api_key="voy-brand-new-key")
            result = await update_keys(body)

            assert result["updated"] == ["VOYAGE_API_KEY"]
            written = mock_write.call_args[0][0]
            # Old keys should still be present
            assert written["ANTHROPIC_API_KEY"] == "sk-ant-old-key"
            assert written["FIRECRAWL_API_KEY"] == "fc-old-key"
            assert written["VOYAGE_API_KEY"] == "voy-brand-new-key"


class TestEnvFileIO:
    def test_read_env(self, env_file):
        """_read_env parses key=value lines, skips comments."""
        with patch("routes.settings.ENV_PATH", env_file):
            env = _read_env()
        assert env["ANTHROPIC_API_KEY"] == "sk-ant-api03-realkey1234567890abcdef"
        assert env["SOME_OTHER_VAR"] == "hello"

    def test_write_env_preserves_comments(self, env_file):
        """_write_env preserves comments and updates existing keys."""
        with patch("routes.settings.ENV_PATH", env_file):
            env = _read_env()
            env["ANTHROPIC_API_KEY"] = "sk-ant-updated"
            env["NEW_KEY"] = "new_value"
            _write_env(env)

            content = env_file.read_text()
            assert "# IndusAI config" in content
            assert "ANTHROPIC_API_KEY=sk-ant-updated" in content
            assert "SOME_OTHER_VAR=hello" in content
            assert "NEW_KEY=new_value" in content

    def test_write_env_creates_file(self, tmp_path):
        """_write_env creates .env if it doesn't exist."""
        new_path = tmp_path / ".env"
        with patch("routes.settings.ENV_PATH", new_path):
            _write_env({"MY_KEY": "my_value"})
            assert new_path.exists()
            assert "MY_KEY=my_value" in new_path.read_text()
