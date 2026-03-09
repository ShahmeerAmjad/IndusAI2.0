"""API key management — read masked keys, save to .env file."""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# Keys we allow managing through the UI
MANAGED_KEYS = ["ANTHROPIC_API_KEY", "FIRECRAWL_API_KEY", "VOYAGE_API_KEY"]

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _mask_key(value: str) -> str:
    """Show only last 4 chars: sk-ant-...XXXX"""
    if not value or len(value) < 8:
        return "****" if value else ""
    return value[:7] + "..." + value[-4:]


def _read_env() -> dict[str, str]:
    """Parse .env file into a dict."""
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def _write_env(env: dict[str, str]) -> None:
    """Write dict back to .env, preserving comments and order."""
    if not ENV_PATH.exists():
        # Just write the keys
        lines = [f"{k}={v}" for k, v in env.items()]
        ENV_PATH.write_text("\n".join(lines) + "\n")
        return

    original_lines = ENV_PATH.read_text().splitlines()
    written_keys: set[str] = set()
    new_lines: list[str] = []

    for line in original_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            if key in env:
                new_lines.append(f"{key}={env[key]}")
                written_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append any new keys not already in file
    for key, value in env.items():
        if key not in written_keys:
            new_lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n")


class KeysUpdateRequest(BaseModel):
    anthropic_api_key: Optional[str] = None
    firecrawl_api_key: Optional[str] = None
    voyage_api_key: Optional[str] = None


@router.get("/keys")
async def get_keys():
    """Return masked API keys and their configured status."""
    env = _read_env()
    keys = {}
    for key_name in MANAGED_KEYS:
        value = env.get(key_name, "")
        keys[key_name.lower()] = {
            "configured": bool(value),
            "preview": _mask_key(value) if value else "",
        }
    return {"keys": keys}


@router.put("/keys")
async def update_keys(body: KeysUpdateRequest):
    """Save API keys to .env file. Only updates keys that are provided (non-None)."""
    env = _read_env()
    updated: list[str] = []

    field_to_env = {
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "firecrawl_api_key": "FIRECRAWL_API_KEY",
        "voyage_api_key": "VOYAGE_API_KEY",
    }

    for field_name, env_key in field_to_env.items():
        value = getattr(body, field_name)
        if value is not None:
            env[env_key] = value
            # Also update os.environ so changes take effect without restart
            os.environ[env_key] = value
            updated.append(env_key)

    if updated:
        _write_env(env)
        logger.info("Updated API keys: %s", ", ".join(updated))

    return {"updated": updated, "message": f"Saved {len(updated)} key(s) to .env"}
