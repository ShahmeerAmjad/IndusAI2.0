import pytest


def test_auth_schema_strings_exist():
    from services.platform.schema import PLATFORM_SCHEMA, PLATFORM_INDEXES
    assert "CREATE TABLE IF NOT EXISTS organizations" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS users" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS locations" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS refresh_tokens" in PLATFORM_SCHEMA
    assert "idx_users_email" in PLATFORM_INDEXES
