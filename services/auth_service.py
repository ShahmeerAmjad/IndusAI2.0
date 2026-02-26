"""Authentication service — signup, login, token management."""

import hashlib
import logging
import secrets
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt as pyjwt

logger = logging.getLogger(__name__)


class AuthService:
    """Handles user authentication, token creation, and password hashing."""

    ACCESS_TOKEN_TTL = timedelta(hours=24)
    REFRESH_TOKEN_TTL = timedelta(days=30)

    def __init__(self, db_manager, settings):
        self._db = db_manager
        self._secret = settings.secret_key

    # ------------------------------------------------------------------
    # Password hashing
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    # ------------------------------------------------------------------
    # JWT tokens
    # ------------------------------------------------------------------

    def create_access_token(self, user_id: str, org_id: str, role: str) -> str:
        payload = {
            "user_id": user_id,
            "org_id": org_id,
            "role": role,
            "exp": datetime.now(timezone.utc) + self.ACCESS_TOKEN_TTL,
        }
        return pyjwt.encode(payload, self._secret, algorithm="HS256")

    def decode_access_token(self, token: str) -> dict:
        try:
            return pyjwt.decode(token, self._secret, algorithms=["HS256"])
        except pyjwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except pyjwt.PyJWTError:
            raise ValueError("Invalid token")

    def create_refresh_token(self) -> tuple[str, str]:
        """Returns (raw_token, token_hash) — store the hash, give raw to client."""
        raw = secrets.token_urlsafe(64)
        hashed = hashlib.sha256(raw.encode()).hexdigest()
        return raw, hashed

    # ------------------------------------------------------------------
    # Signup / Login
    # ------------------------------------------------------------------

    async def signup(self, email: str, password: str, name: str,
                     org_name: str) -> dict[str, Any]:
        """Create organization + admin user. Returns tokens + user."""
        email = email.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-")

        async with self._db.pool.acquire() as conn:
            # Check duplicate email
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE email = $1", email
            )
            if existing:
                raise ValueError("Email already registered")

            # Create org
            org = await conn.fetchrow(
                """INSERT INTO organizations (name, slug)
                   VALUES ($1, $2) RETURNING id, name, slug""",
                org_name, slug,
            )

            # Create user
            pw_hash = self.hash_password(password)
            user = await conn.fetchrow(
                """INSERT INTO users (email, password_hash, name, org_id, role)
                   VALUES ($1, $2, $3, $4, 'admin')
                   RETURNING id, email, name, role, org_id""",
                email, pw_hash, name, str(org["id"]),
            )

        access_token = self.create_access_token(
            str(user["id"]), str(user["org_id"]), user["role"]
        )
        refresh_raw, refresh_hash = self.create_refresh_token()
        await self._store_refresh_token(str(user["id"]), refresh_hash)

        return {
            "user": dict(user),
            "org": dict(org),
            "access_token": access_token,
            "refresh_token": refresh_raw,
        }

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate user, return tokens."""
        email = email.lower().strip()

        async with self._db.pool.acquire() as conn:
            user = await conn.fetchrow(
                """SELECT id, email, password_hash, name, role, org_id, is_active
                   FROM users WHERE email = $1""",
                email,
            )

        if not user:
            raise ValueError("Invalid email or password")
        if not user["is_active"]:
            raise ValueError("Account disabled")
        if not self.verify_password(password, user["password_hash"]):
            raise ValueError("Invalid email or password")

        # Update last login
        async with self._db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login_at = now() WHERE id = $1",
                user["id"],
            )

        access_token = self.create_access_token(
            str(user["id"]), str(user["org_id"]), user["role"]
        )
        refresh_raw, refresh_hash = self.create_refresh_token()
        await self._store_refresh_token(str(user["id"]), refresh_hash)

        return {
            "user": {
                "id": str(user["id"]),
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
                "org_id": str(user["org_id"]),
            },
            "access_token": access_token,
            "refresh_token": refresh_raw,
        }

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        """Exchange a refresh token for a new access token."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT rt.user_id, u.org_id, u.role, u.is_active
                   FROM refresh_tokens rt
                   JOIN users u ON u.id = rt.user_id
                   WHERE rt.token_hash = $1
                     AND rt.revoked = false
                     AND rt.expires_at > now()""",
                token_hash,
            )

        if not row or not row["is_active"]:
            raise ValueError("Invalid or expired refresh token")

        # Rotate: revoke old, issue new
        async with self._db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE refresh_tokens SET revoked = true WHERE token_hash = $1",
                token_hash,
            )

        access_token = self.create_access_token(
            str(row["user_id"]), str(row["org_id"]), row["role"]
        )
        new_raw, new_hash = self.create_refresh_token()
        await self._store_refresh_token(str(row["user_id"]), new_hash)

        return {
            "access_token": access_token,
            "refresh_token": new_raw,
        }

    async def _store_refresh_token(self, user_id: str, token_hash: str):
        expires = datetime.now(timezone.utc) + self.REFRESH_TOKEN_TTL
        async with self._db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                   VALUES ($1, $2, $3)""",
                user_id, token_hash, expires,
            )
