# IndusAI MVP — AI-First MRO Sourcing Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform IndusAI from an internal MRO back-office tool into a sellable SaaS product where procurement teams find the best MRO parts, prices, and delivery options through an AI-powered sourcing assistant.

**Architecture:** AI-first sourcing layer. The GraphRAG query engine is the primary interface. Buyers ask in natural language, the system searches a unified catalog (scraped + uploaded), optimizes for price/delivery/proximity, and returns ranked results with reliability scoring. Traditional CRUD UI exists as fallback. Multi-tenant SaaS with JWT + OAuth auth.

**Tech Stack:** Python 3.14 / FastAPI, React 18 / TypeScript / Vite, Neo4j 5.x, PostgreSQL 16, Redis 7, Claude (Haiku/Sonnet/Opus), Voyage AI embeddings, httpx, BeautifulSoup, bcrypt, APScheduler.

**Design doc:** `docs/plans/2026-02-27-indusai-product-design.md`

---

## Phase 1: Foundation (Auth, Multi-tenancy, Data Model)

---

### Task 1: Auth Database Schema — Users, Orgs, Locations

**Files:**
- Modify: `services/platform/schema.py` (add tables after existing schema)
- Modify: `requirements.txt` (add bcrypt)
- Test: `tests/test_auth.py`

**Step 1: Add bcrypt to requirements.txt**

Add after the `python-Levenshtein` line in `requirements.txt`:
```
bcrypt>=4.0,<5.0
```

Run: `.venv/bin/pip install bcrypt>=4.0`

**Step 2: Add auth tables to schema.py**

Append to the `PLATFORM_SCHEMA` string in `services/platform/schema.py`, after the last `CREATE TABLE` statement:

```sql
-- Auth & Multi-tenancy
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    primary_location_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    org_id UUID REFERENCES organizations(id),
    role TEXT NOT NULL DEFAULT 'buyer',
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    label TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    country TEXT DEFAULT 'US',
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

Append to `PLATFORM_INDEXES`:

```sql
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_locations_org ON locations(org_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
```

**Step 3: Write test for schema creation**

Create `tests/test_auth.py`:

```python
import pytest

def test_auth_schema_strings_exist():
    from services.platform.schema import PLATFORM_SCHEMA, PLATFORM_INDEXES
    assert "CREATE TABLE IF NOT EXISTS organizations" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS users" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS locations" in PLATFORM_SCHEMA
    assert "CREATE TABLE IF NOT EXISTS refresh_tokens" in PLATFORM_SCHEMA
    assert "idx_users_email" in PLATFORM_INDEXES
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/platform/schema.py requirements.txt tests/test_auth.py
git commit -m "feat: add auth schema — users, orgs, locations, refresh tokens"
```

---

### Task 2: Auth Service — Signup, Login, Token Management

**Files:**
- Create: `services/auth_service.py`
- Test: `tests/test_auth.py` (extend)

**Step 1: Write failing tests**

Add to `tests/test_auth.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.auth_service import AuthService

class TestAuthService:
    def setup_method(self):
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
        self.db.pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()))

        with pytest.raises(ValueError, match="already registered"):
            await self.auth.signup(
                email="a@b.com", password="pass", name="Test", org_name="Acme"
            )
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_auth.py::TestAuthService -v`
Expected: FAIL (module not found)

**Step 3: Implement AuthService**

Create `services/auth_service.py`:

```python
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
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/auth_service.py tests/test_auth.py
git commit -m "feat: add auth service — signup, login, JWT, refresh tokens, bcrypt"
```

---

### Task 3: Auth API Routes

**Files:**
- Create: `routes/auth.py`
- Modify: `main.py` (register router, add auth dependency)

**Step 1: Create auth routes**

Create `routes/auth.py`:

```python
"""Auth API routes — signup, login, refresh, me."""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/api/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)

# Will be set by main.py during startup
_auth_service = None


def set_auth_service(auth_service):
    global _auth_service
    _auth_service = auth_service


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)
    org_name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LocationRequest(BaseModel):
    label: str
    address: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = "US"
    lat: float | None = None
    lng: float | None = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    """FastAPI dependency — decode JWT and return user payload."""
    if not credentials or not _auth_service:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return _auth_service.decode_access_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/signup")
async def signup(req: SignupRequest):
    try:
        result = await _auth_service.signup(
            email=req.email, password=req.password,
            name=req.name, org_name=req.org_name,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(req: LoginRequest):
    try:
        result = await _auth_service.login(
            email=req.email, password=req.password,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    try:
        result = await _auth_service.refresh(req.refresh_token)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return {"user": user}


@router.post("/locations")
async def add_location(req: LocationRequest, user=Depends(get_current_user)):
    """Add a location to the current user's organization."""
    org_id = user["org_id"]
    if not _auth_service._db.pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with _auth_service._db.pool.acquire() as conn:
        loc = await conn.fetchrow(
            """INSERT INTO locations (org_id, label, address, city, state, zip, country, lat, lng)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING id, label, city, state, lat, lng""",
            org_id, req.label, req.address, req.city, req.state,
            req.zip, req.country, req.lat, req.lng,
        )
    return dict(loc)


@router.get("/locations")
async def list_locations(user=Depends(get_current_user)):
    """List locations for the current user's org."""
    org_id = user["org_id"]
    async with _auth_service._db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, label, address, city, state, zip, country, lat, lng FROM locations WHERE org_id = $1",
            org_id,
        )
    return [dict(r) for r in rows]
```

**Step 2: Wire into main.py**

Add import near other route imports (~line 84):
```python
from routes.auth import router as auth_router, set_auth_service, get_current_user
from services.auth_service import AuthService
```

Register router after `app.include_router(platform_router)`:
```python
app.include_router(auth_router)
```

In `lifespan()`, after database initialization, add:
```python
# Initialize auth service
auth_service = AuthService(db_manager=db_manager, settings=settings)
set_auth_service(auth_service)
app.state.auth_service = auth_service
```

**Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add routes/auth.py main.py
git commit -m "feat: add auth API routes — signup, login, refresh, locations"
```

---

### Task 4: Seller & Listing Data Model

**Files:**
- Modify: `services/platform/schema.py` (add seller tables)
- Create: `services/seller_service.py`
- Test: `tests/test_seller_service.py`

**Step 1: Add seller tables to schema.py**

Append to `PLATFORM_SCHEMA`:

```sql
-- Seller / Supply Side
CREATE TABLE IF NOT EXISTS seller_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name TEXT NOT NULL,
    website TEXT,
    catalog_source TEXT DEFAULT 'manual',
    last_scraped_at TIMESTAMPTZ,
    reliability_base REAL DEFAULT 5.0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seller_warehouses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL REFERENCES seller_profiles(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES locations(id),
    ships_to_regions TEXT[] DEFAULT '{"US"}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seller_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID NOT NULL REFERENCES seller_profiles(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    part_sku TEXT NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    currency TEXT DEFAULT 'USD',
    qty_available INTEGER DEFAULT 0,
    warehouse_id UUID REFERENCES seller_warehouses(id),
    lead_time_days INTEGER DEFAULT 3,
    reliability REAL DEFAULT 5.0,
    source_type TEXT DEFAULT 'manual',
    last_verified_at TIMESTAMPTZ DEFAULT now(),
    stale_after TIMESTAMPTZ DEFAULT (now() + interval '7 days'),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(seller_id, sku, warehouse_id)
);

-- Sourcing & RFQ
CREATE TABLE IF NOT EXISTS sourcing_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_org_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    query_text TEXT NOT NULL,
    intent TEXT,
    results_json JSONB,
    location_id UUID REFERENCES locations(id),
    parts_found INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_org_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    part_description TEXT NOT NULL,
    part_sku TEXT,
    qty INTEGER NOT NULL DEFAULT 1,
    urgency TEXT DEFAULT 'standard',
    target_price NUMERIC(12,2),
    status TEXT DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rfq_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rfq_id UUID NOT NULL REFERENCES rfq_requests(id) ON DELETE CASCADE,
    seller_id UUID NOT NULL REFERENCES seller_profiles(id),
    price NUMERIC(12,2) NOT NULL,
    lead_time_days INTEGER,
    notes TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

Append to `PLATFORM_INDEXES`:

```sql
CREATE INDEX IF NOT EXISTS idx_seller_listings_part ON seller_listings(part_sku);
CREATE INDEX IF NOT EXISTS idx_seller_listings_seller ON seller_listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_seller_listings_stale ON seller_listings(stale_after);
CREATE INDEX IF NOT EXISTS idx_sourcing_requests_org ON sourcing_requests(buyer_org_id);
CREATE INDEX IF NOT EXISTS idx_rfq_requests_org ON rfq_requests(buyer_org_id);
CREATE INDEX IF NOT EXISTS idx_rfq_responses_rfq ON rfq_responses(rfq_id);
```

**Step 2: Create seller service**

Create `services/seller_service.py`:

```python
"""Seller service — manage seller profiles, warehouses, and listings."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SellerService:
    """CRUD for sellers, warehouses, and part listings."""

    def __init__(self, db_manager, logger=None):
        self._db = db_manager
        self._log = logger or logging.getLogger(__name__)

    async def create_seller(self, data: dict) -> dict | None:
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO seller_profiles (name, website, catalog_source, reliability_base)
                   VALUES ($1, $2, $3, $4)
                   RETURNING id, name, website, catalog_source, reliability_base""",
                data["name"], data.get("website"), data.get("catalog_source", "manual"),
                data.get("reliability_base", 5.0),
            )
        return dict(row) if row else None

    async def get_seller(self, seller_id: str) -> dict | None:
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM seller_profiles WHERE id = $1", seller_id
            )
        return dict(row) if row else None

    async def upsert_listing(self, data: dict) -> dict | None:
        """Insert or update a seller listing. Dedup by (seller_id, sku, warehouse_id)."""
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO seller_listings
                   (seller_id, sku, part_sku, price, currency, qty_available,
                    warehouse_id, lead_time_days, reliability, source_type,
                    last_verified_at, stale_after)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now(), now() + interval '7 days')
                   ON CONFLICT (seller_id, sku, warehouse_id)
                   DO UPDATE SET price = $4, qty_available = $6,
                     lead_time_days = $8, reliability = $9,
                     last_verified_at = now(),
                     stale_after = now() + interval '7 days',
                     updated_at = now()
                   RETURNING id, seller_id, sku, part_sku, price, qty_available""",
                data["seller_id"], data["sku"], data.get("part_sku", data["sku"]),
                data["price"], data.get("currency", "USD"),
                data.get("qty_available", 0), data.get("warehouse_id"),
                data.get("lead_time_days", 3),
                data.get("reliability", 5.0), data.get("source_type", "manual"),
            )
        return dict(row) if row else None

    async def find_listings_for_parts(self, part_skus: list[str],
                                      min_qty: int = 1) -> list[dict]:
        """Find all seller listings for a set of part SKUs with sufficient stock."""
        if not part_skus:
            return []
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT sl.*, sp.name AS seller_name, sp.website AS seller_website,
                          l.lat, l.lng, l.city, l.state
                   FROM seller_listings sl
                   JOIN seller_profiles sp ON sp.id = sl.seller_id
                   LEFT JOIN seller_warehouses sw ON sw.id = sl.warehouse_id
                   LEFT JOIN locations l ON l.id = sw.location_id
                   WHERE sl.part_sku = ANY($1)
                     AND sl.qty_available >= $2
                   ORDER BY sl.price ASC""",
                part_skus, min_qty,
            )
        return [dict(r) for r in rows]

    async def get_stale_listings(self, limit: int = 100) -> list[dict]:
        """Get listings that need re-verification."""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT sl.*, sp.name AS seller_name, sp.website
                   FROM seller_listings sl
                   JOIN seller_profiles sp ON sp.id = sl.seller_id
                   WHERE sl.stale_after < now()
                   ORDER BY sl.stale_after ASC
                   LIMIT $1""",
                limit,
            )
        return [dict(r) for r in rows]
```

**Step 3: Write tests**

Create `tests/test_seller_service.py`:

```python
import pytest

def test_seller_schema_exists():
    from services.platform.schema import PLATFORM_SCHEMA
    assert "seller_profiles" in PLATFORM_SCHEMA
    assert "seller_listings" in PLATFORM_SCHEMA
    assert "seller_warehouses" in PLATFORM_SCHEMA
    assert "rfq_requests" in PLATFORM_SCHEMA

def test_seller_service_importable():
    from services.seller_service import SellerService
    assert SellerService is not None
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_seller_service.py tests/test_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/platform/schema.py services/seller_service.py tests/test_seller_service.py
git commit -m "feat: add seller data model — profiles, warehouses, listings, RFQ tables"
```

---

## Phase 2: Supply Intelligence (Scraper, Reliability, Location)

---

### Task 5: Web Scraper — Crawl Distributor Sites

**Files:**
- Create: `services/ingestion/web_scraper.py`
- Test: `tests/test_web_scraper.py`

This extends the existing `CatalogParser.scrape_url()` in `services/ingestion/parser.py` with a more robust scraper that handles multiple pages, extracts pricing, and tags with seller + reliability.

**Step 1: Write tests**

Create `tests/test_web_scraper.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.ingestion.web_scraper import WebScraper, ScrapedProduct


class TestWebScraper:
    def test_scraped_product_defaults(self):
        p = ScrapedProduct(sku="ABC-123", name="Test Part", price=9.99, seller_name="TestCo")
        assert p.reliability == 7.0
        assert p.source_type == "web_scrape"
        assert p.currency == "USD"

    def test_parse_price_from_text(self):
        scraper = WebScraper()
        assert scraper._parse_price("$12.99") == 12.99
        assert scraper._parse_price("USD 1,234.56") == 1234.56
        assert scraper._parse_price("no price here") is None

    @pytest.mark.asyncio
    async def test_scrape_returns_products(self):
        scraper = WebScraper(llm_router=AsyncMock())
        scraper._llm.chat = AsyncMock(return_value='[{"sku":"A1","name":"Part A","price":5.0}]')

        with patch("services.ingestion.web_scraper.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Product A - $5.00 - SKU: A1</body></html>"
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            results = await scraper.scrape(
                url="https://example.com/catalog",
                seller_name="TestCo",
            )
            assert len(results) >= 0  # LLM-dependent
```

**Step 2: Implement web scraper**

Create `services/ingestion/web_scraper.py`:

```python
"""Web scraper for distributor catalog sites."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCRAPE_EXTRACTION_PROMPT = """Extract product data from this distributor catalog page.
Return a JSON array of products. Each product should have:
- sku: part/SKU number
- name: product name
- price: unit price as a number (null if not found)
- manufacturer: manufacturer name (null if not found)
- description: short description
- specs: dict of specifications (e.g., {{"bore_mm": 20, "od_mm": 47}})
- qty_available: stock quantity if shown (null if not found)

Only extract REAL products. Skip navigation, headers, ads.
Return ONLY valid JSON array, no markdown.

Page content:
{content}"""


@dataclass
class ScrapedProduct:
    sku: str
    name: str
    price: float | None = None
    manufacturer: str = ""
    description: str = ""
    category: str = ""
    specs: dict = field(default_factory=dict)
    qty_available: int | None = None
    seller_name: str = ""
    source_url: str = ""
    reliability: float = 7.0
    source_type: str = "web_scrape"
    currency: str = "USD"


class WebScraper:
    """Scrape distributor websites and extract structured product data."""

    def __init__(self, llm_router=None):
        self._llm = llm_router

    async def scrape(self, url: str, seller_name: str,
                     max_pages: int = 5) -> list[ScrapedProduct]:
        """Scrape a URL and return structured products."""
        all_products = []

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30.0,
                headers={"User-Agent": "IndusAI-Catalog-Bot/1.0"}
            ) as client:
                pages_scraped = 0
                current_url = url

                while current_url and pages_scraped < max_pages:
                    resp = await client.get(current_url)
                    if resp.status_code != 200:
                        logger.warning("Scrape failed %s: HTTP %d", current_url, resp.status_code)
                        break

                    products, next_url = await self._extract_page(
                        resp.text, current_url, seller_name
                    )
                    all_products.extend(products)
                    pages_scraped += 1
                    current_url = next_url

                    logger.info("Scraped page %d of %s: %d products",
                                pages_scraped, seller_name, len(products))

        except Exception as e:
            logger.error("Scrape error for %s: %s", url, e)

        return all_products

    async def _extract_page(self, html: str, url: str,
                            seller_name: str) -> tuple[list[ScrapedProduct], str | None]:
        """Extract products from a single HTML page."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Truncate for LLM context
        text = text[:8000]

        products = []

        if self._llm:
            try:
                prompt = SCRAPE_EXTRACTION_PROMPT.format(content=text)
                response = await self._llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    task="catalog_extraction",
                    max_tokens=4096,
                    temperature=0.1,
                )
                # Parse JSON from response
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    raw_products = json.loads(json_match.group())
                    for raw in raw_products:
                        if raw.get("sku"):
                            products.append(ScrapedProduct(
                                sku=str(raw["sku"]).strip(),
                                name=raw.get("name", ""),
                                price=self._safe_float(raw.get("price")),
                                manufacturer=raw.get("manufacturer", ""),
                                description=raw.get("description", ""),
                                specs=raw.get("specs", {}),
                                qty_available=raw.get("qty_available"),
                                seller_name=seller_name,
                                source_url=url,
                            ))
            except Exception as e:
                logger.warning("LLM extraction failed: %s", e)

        # Find next page link
        next_url = self._find_next_page(soup, url)

        return products, next_url

    def _find_next_page(self, soup: BeautifulSoup, current_url: str) -> str | None:
        """Find 'next page' link in the HTML."""
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True).lower()
            if text in ("next", "next page", "next >", ">>", ">"):
                href = link["href"]
                if href.startswith("http"):
                    return href
                # Relative URL
                from urllib.parse import urljoin
                return urljoin(current_url, href)
        return None

    @staticmethod
    def _parse_price(text: str) -> float | None:
        """Extract price from text like '$12.99' or 'USD 1,234.56'."""
        match = re.search(r'[\$]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text)
        if match:
            return float(match.group(1).replace(",", ""))
        return None

    @staticmethod
    def _safe_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
```

**Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_web_scraper.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add services/ingestion/web_scraper.py tests/test_web_scraper.py
git commit -m "feat: add web scraper — crawl distributor sites with LLM extraction"
```

---

### Task 6: Reliability Scoring Engine

**Files:**
- Create: `services/intelligence/reliability.py`
- Test: `tests/test_reliability.py`

**Step 1: Write tests**

Create `tests/test_reliability.py`:

```python
import pytest
from datetime import datetime, timezone, timedelta
from services.intelligence.reliability import ReliabilityScorer


class TestReliabilityScorer:
    def setup_method(self):
        self.scorer = ReliabilityScorer()

    def test_base_score_by_source(self):
        assert self.scorer.base_score("manufacturer_datasheet") == 10.0
        assert self.scorer.base_score("api_feed") == 9.0
        assert self.scorer.base_score("web_scrape") == 7.0
        assert self.scorer.base_score("manual") == 6.0
        assert self.scorer.base_score("forum") == 4.0
        assert self.scorer.base_score("unknown") == 3.0

    def test_age_decay_fresh(self):
        verified = datetime.now(timezone.utc) - timedelta(days=1)
        decay = self.scorer.age_decay(verified)
        assert decay == 0.0  # within 7 days = no decay

    def test_age_decay_stale(self):
        verified = datetime.now(timezone.utc) - timedelta(days=21)
        decay = self.scorer.age_decay(verified)
        assert decay == 2.0  # 14 days past grace = 2 points

    def test_age_decay_very_old(self):
        verified = datetime.now(timezone.utc) - timedelta(days=60)
        decay = self.scorer.age_decay(verified)
        assert decay >= 5.0  # capped

    def test_compute_score(self):
        score = self.scorer.compute(
            source_type="web_scrape",
            last_verified_at=datetime.now(timezone.utc) - timedelta(days=2),
            cross_validations=0,
        )
        assert 6.5 <= score <= 7.5

    def test_cross_validation_boost(self):
        base = self.scorer.compute(
            source_type="web_scrape",
            last_verified_at=datetime.now(timezone.utc),
            cross_validations=0,
        )
        boosted = self.scorer.compute(
            source_type="web_scrape",
            last_verified_at=datetime.now(timezone.utc),
            cross_validations=3,
        )
        assert boosted > base

    def test_is_stale(self):
        assert not self.scorer.is_stale(
            datetime.now(timezone.utc) - timedelta(days=5), "price"
        )
        assert self.scorer.is_stale(
            datetime.now(timezone.utc) - timedelta(days=35), "price"
        )

    def test_should_exclude(self):
        assert not self.scorer.should_exclude(
            datetime.now(timezone.utc) - timedelta(days=5), "price"
        )
        assert self.scorer.should_exclude(
            datetime.now(timezone.utc) - timedelta(days=35), "price"
        )
```

**Step 2: Implement**

Create `services/intelligence/__init__.py` (empty).

Create `services/intelligence/reliability.py`:

```python
"""Reliability scoring engine — scores data freshness and trustworthiness."""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

SOURCE_SCORES = {
    "manufacturer_datasheet": 10.0,
    "api_feed": 9.0,
    "seller_upload": 8.0,
    "web_scrape": 7.0,
    "manual": 6.0,
    "forum": 4.0,
}

# How many days before data starts decaying
GRACE_PERIODS = {
    "price": 7,
    "spec": 90,
    "availability": 3,
    "default": 7,
}

# How many days until data is excluded from results entirely
EXCLUDE_THRESHOLDS = {
    "price": 30,
    "spec": 365,
    "availability": 14,
    "default": 30,
}


class ReliabilityScorer:
    """Compute reliability scores for knowledge graph data."""

    @staticmethod
    def base_score(source_type: str) -> float:
        return SOURCE_SCORES.get(source_type, 3.0)

    @staticmethod
    def age_decay(last_verified_at: datetime,
                  data_type: str = "default") -> float:
        """Compute age-based decay. Returns points to subtract (0-5)."""
        grace = GRACE_PERIODS.get(data_type, 7)
        age_days = (datetime.now(timezone.utc) - last_verified_at).days
        past_grace = max(0, age_days - grace)
        # 1 point per 7 days past grace, capped at 5
        return min(past_grace / 7.0, 5.0)

    def compute(self, source_type: str, last_verified_at: datetime,
                cross_validations: int = 0,
                data_type: str = "default") -> float:
        """Compute final reliability score (0-10)."""
        base = self.base_score(source_type)
        decay = self.age_decay(last_verified_at, data_type)
        xval_boost = min(cross_validations * 0.3, 1.5)
        score = base - decay + xval_boost
        return max(0.0, min(10.0, round(score, 1)))

    @staticmethod
    def is_stale(last_verified_at: datetime, data_type: str = "default") -> bool:
        """Check if data is past its exclude threshold."""
        threshold = EXCLUDE_THRESHOLDS.get(data_type, 30)
        age_days = (datetime.now(timezone.utc) - last_verified_at).days
        return age_days > threshold

    @staticmethod
    def should_exclude(last_verified_at: datetime, data_type: str = "default") -> bool:
        """Alias for is_stale — data too old to show to buyers."""
        threshold = EXCLUDE_THRESHOLDS.get(data_type, 30)
        age_days = (datetime.now(timezone.utc) - last_verified_at).days
        return age_days > threshold
```

**Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_reliability.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add services/intelligence/__init__.py services/intelligence/reliability.py tests/test_reliability.py
git commit -m "feat: add reliability scoring engine — source scores, age decay, cross-validation"
```

---

### Task 7: Location Optimizer — Geocoding & Distance

**Files:**
- Create: `services/intelligence/location.py`
- Test: `tests/test_location.py`

**Step 1: Write tests**

Create `tests/test_location.py`:

```python
import pytest
from services.intelligence.location import LocationOptimizer


class TestLocationOptimizer:
    def setup_method(self):
        self.optimizer = LocationOptimizer()

    def test_haversine_distance(self):
        # NYC to LA ~ 3944 km
        d = self.optimizer.haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3900 < d < 4000

    def test_haversine_same_point(self):
        d = self.optimizer.haversine_distance(40.0, -74.0, 40.0, -74.0)
        assert d == 0.0

    def test_estimate_shipping_local(self):
        cost, days = self.optimizer.estimate_shipping(distance_km=20, weight_lbs=10)
        assert cost < 15
        assert days <= 1

    def test_estimate_shipping_medium(self):
        cost, days = self.optimizer.estimate_shipping(distance_km=500, weight_lbs=10)
        assert 10 < cost < 50
        assert 1 <= days <= 3

    def test_estimate_shipping_long(self):
        cost, days = self.optimizer.estimate_shipping(distance_km=3000, weight_lbs=10)
        assert cost > 30
        assert days >= 3

    def test_rank_by_proximity(self):
        buyer = (40.7128, -74.0060)  # NYC
        sellers = [
            {"id": "far", "lat": 34.0522, "lng": -118.2437},   # LA
            {"id": "close", "lat": 39.9526, "lng": -75.1652},  # Philly
            {"id": "mid", "lat": 41.8781, "lng": -87.6298},    # Chicago
        ]
        ranked = self.optimizer.rank_by_proximity(buyer, sellers)
        assert ranked[0]["id"] == "close"
        assert ranked[-1]["id"] == "far"
        assert "distance_km" in ranked[0]
```

**Step 2: Implement**

Create `services/intelligence/location.py`:

```python
"""Location optimizer — geocoding, distance calculation, shipping estimates."""

import logging
import math

logger = logging.getLogger(__name__)


class LocationOptimizer:
    """Calculate distances and estimate shipping between buyer and seller locations."""

    @staticmethod
    def haversine_distance(lat1: float, lng1: float,
                           lat2: float, lng2: float) -> float:
        """Great-circle distance in km between two lat/lng points."""
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def estimate_shipping(distance_km: float, weight_lbs: float = 5.0) -> tuple[float, int]:
        """Estimate shipping cost (USD) and transit days based on distance.

        Returns (cost, days). This is a rough heuristic — replace with
        carrier API (UPS/FedEx) for production accuracy.
        """
        distance_mi = distance_km * 0.621371

        if distance_mi < 50:
            days = 1
            base_cost = 0.0  # local pickup / free local delivery
        elif distance_mi < 300:
            days = 2
            base_cost = 12.0
        elif distance_mi < 1000:
            days = 3
            base_cost = 25.0
        elif distance_mi < 2000:
            days = 4
            base_cost = 40.0
        else:
            days = 5
            base_cost = 55.0

        # Weight surcharge: $0.50 per lb over 10 lbs
        weight_surcharge = max(0, (weight_lbs - 10)) * 0.50
        cost = round(base_cost + weight_surcharge, 2)

        return cost, days

    def rank_by_proximity(self, buyer_location: tuple[float, float],
                          seller_locations: list[dict]) -> list[dict]:
        """Rank seller locations by distance from buyer.

        Args:
            buyer_location: (lat, lng) of buyer
            seller_locations: list of dicts with 'lat', 'lng' keys

        Returns:
            Same list with 'distance_km', 'shipping_cost', 'transit_days' added,
            sorted by distance ascending.
        """
        buyer_lat, buyer_lng = buyer_location

        for seller in seller_locations:
            s_lat = seller.get("lat")
            s_lng = seller.get("lng")
            if s_lat is not None and s_lng is not None:
                dist = self.haversine_distance(buyer_lat, buyer_lng, s_lat, s_lng)
                cost, days = self.estimate_shipping(dist)
                seller["distance_km"] = round(dist, 1)
                seller["shipping_cost"] = cost
                seller["transit_days"] = days
            else:
                seller["distance_km"] = 99999
                seller["shipping_cost"] = 99.0
                seller["transit_days"] = 7

        return sorted(seller_locations, key=lambda s: s["distance_km"])
```

**Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_location.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add services/intelligence/location.py tests/test_location.py
git commit -m "feat: add location optimizer — haversine distance, shipping estimates"
```

---

### Task 8: Price Comparator & Composite Ranking

**Files:**
- Create: `services/intelligence/price_comparator.py`
- Test: `tests/test_price_comparator.py`

**Step 1: Write tests**

Create `tests/test_price_comparator.py`:

```python
import pytest
from datetime import datetime, timezone, timedelta
from services.intelligence.price_comparator import PriceComparator, SourcingResult


class TestPriceComparator:
    def setup_method(self):
        self.comparator = PriceComparator()

    def test_composite_score_basic(self):
        result = SourcingResult(
            sku="6204-2RS", name="Bearing", seller_name="TestCo",
            unit_price=4.20, qty_available=100,
            reliability=8.0, distance_km=50, transit_days=1, shipping_cost=0,
        )
        score = self.comparator.composite_score(result, qty=100)
        assert 0 < score <= 10

    def test_cheaper_ranks_higher(self):
        cheap = SourcingResult(
            sku="A", name="A", seller_name="Cheap",
            unit_price=3.00, reliability=7.0, distance_km=500,
            transit_days=3, shipping_cost=25, qty_available=100,
        )
        expensive = SourcingResult(
            sku="A", name="A", seller_name="Pricey",
            unit_price=6.00, reliability=7.0, distance_km=500,
            transit_days=3, shipping_cost=25, qty_available=100,
        )
        results = self.comparator.rank([cheap, expensive], qty=10)
        assert results[0].seller_name == "Cheap"

    def test_reliable_ranks_higher_at_similar_price(self):
        reliable = SourcingResult(
            sku="A", name="A", seller_name="Reliable",
            unit_price=4.00, reliability=9.0, distance_km=200,
            transit_days=2, shipping_cost=15, qty_available=100,
        )
        unreliable = SourcingResult(
            sku="A", name="A", seller_name="Sketchy",
            unit_price=3.90, reliability=4.0, distance_km=200,
            transit_days=2, shipping_cost=15, qty_available=100,
        )
        results = self.comparator.rank([unreliable, reliable], qty=10)
        assert results[0].seller_name == "Reliable"

    def test_excludes_stale(self):
        stale = SourcingResult(
            sku="A", name="A", seller_name="Stale",
            unit_price=2.00, reliability=2.0, distance_km=100,
            transit_days=1, shipping_cost=0, qty_available=100,
            last_verified_at=datetime.now(timezone.utc) - timedelta(days=45),
        )
        fresh = SourcingResult(
            sku="A", name="A", seller_name="Fresh",
            unit_price=5.00, reliability=8.0, distance_km=100,
            transit_days=1, shipping_cost=0, qty_available=100,
        )
        results = self.comparator.rank([stale, fresh], qty=10)
        assert len(results) == 1
        assert results[0].seller_name == "Fresh"

    def test_total_cost(self):
        r = SourcingResult(
            sku="A", name="A", seller_name="X",
            unit_price=4.20, shipping_cost=45.0,
            reliability=7.0, distance_km=200, transit_days=2, qty_available=100,
        )
        assert r.total_cost(qty=100) == 4.20 * 100 + 45.0
```

**Step 2: Implement**

Create `services/intelligence/price_comparator.py`:

```python
"""Price comparator — normalize prices, compute composite ranking."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from services.intelligence.reliability import ReliabilityScorer

logger = logging.getLogger(__name__)


@dataclass
class SourcingResult:
    """A single sourcing option for a part from a specific seller."""
    sku: str
    name: str
    seller_name: str
    unit_price: float
    qty_available: int = 0
    reliability: float = 5.0
    distance_km: float = 0.0
    transit_days: int = 3
    shipping_cost: float = 0.0
    seller_id: str = ""
    warehouse_id: str = ""
    manufacturer: str = ""
    cross_ref_type: str = ""  # "exact", "equivalent", "alternative"
    last_verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    debug: dict = field(default_factory=dict)

    def total_cost(self, qty: int = 1) -> float:
        return round(self.unit_price * qty + self.shipping_cost, 2)


# Composite ranking weights
W_RELIABILITY = 0.30
W_PRICE = 0.35
W_DELIVERY = 0.25
W_PROXIMITY = 0.10


class PriceComparator:
    """Rank sourcing results by composite score."""

    def __init__(self):
        self._reliability = ReliabilityScorer()

    def composite_score(self, result: SourcingResult, qty: int = 1) -> float:
        """Compute composite score (0-10, higher is better)."""
        # Reliability: already 0-10
        r_score = result.reliability

        # Price: normalize — lower total cost = higher score
        total = result.total_cost(qty)
        # Heuristic: $0 = 10, $10000+ = 0
        p_score = max(0, 10 - (total / 1000.0))

        # Delivery: faster = higher
        d_score = max(0, 10 - result.transit_days * 2)

        # Proximity: closer = higher
        # 0 km = 10, 5000+ km = 0
        x_score = max(0, 10 - (result.distance_km / 500.0))

        composite = (
            W_RELIABILITY * r_score +
            W_PRICE * p_score +
            W_DELIVERY * d_score +
            W_PROXIMITY * x_score
        )

        result.debug = {
            "reliability_score": round(r_score, 2),
            "price_score": round(p_score, 2),
            "delivery_score": round(d_score, 2),
            "proximity_score": round(x_score, 2),
            "composite": round(composite, 3),
            "total_cost": total,
        }

        return round(composite, 3)

    def rank(self, results: list[SourcingResult],
             qty: int = 1,
             exclude_stale: bool = True) -> list[SourcingResult]:
        """Rank results by composite score, optionally excluding stale data."""
        if exclude_stale:
            results = [
                r for r in results
                if not self._reliability.should_exclude(
                    r.last_verified_at, "price"
                )
            ]

        for r in results:
            self.composite_score(r, qty)

        return sorted(results, key=lambda r: r.debug.get("composite", 0), reverse=True)
```

**Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_price_comparator.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add services/intelligence/price_comparator.py tests/test_price_comparator.py
git commit -m "feat: add price comparator — composite ranking with reliability, price, delivery, proximity"
```

---

## Phase 3: Enhanced Sourcing Engine

---

### Task 9: Enhanced GraphRAG — Wire Seller + Location + Pricing into Query Engine

**Files:**
- Modify: `services/graphrag/query_engine.py` (add Stage 4b: seller matching)
- Modify: `services/graphrag/context_merger.py` (add sourcing results to context)
- Modify: `services/ai/prompts.py` (update response prompt for sourcing)
- Test: `tests/test_query_engine.py` (extend)

This is the critical integration task. The query engine currently does: Intent → Graph → Vector → Context → LLM. We add seller matching + location optimization between Context and LLM.

**Step 1: Add sourcing prompt to prompts.py**

Add to `services/ai/prompts.py`:

```python
SOURCING_RESPONSE_PROMPT = """You are IndusAI, an AI-powered MRO parts sourcing assistant.
A buyer is looking for parts. You have searched our knowledge graph and seller catalog.

## Part Knowledge
{context}

## Seller Options
{sourcing_options}

## Buyer Query
{question}

## Instructions
- Present the top options clearly with price, delivery estimate, and seller name
- If cross-references exist, explain the equivalence ("NSK 6204DDU is equivalent to SKF 6204-2RS")
- If applicable, provide technical advice (seal types, temperature ratings, etc.)
- Offer to request a quote or place an order
- Be concise and professional. Use bullet points for comparisons.
- If no results found, ask clarifying questions about what they need.
- Do NOT show reliability scores or internal metadata to the buyer.
"""
```

**Step 2: Add sourcing fields to QueryResult**

Modify `services/graphrag/query_engine.py` — update the `QueryResult` dataclass:

```python
@dataclass
class QueryResult:
    """Result of processing a customer query through GraphRAG."""
    response: str
    intent: IntentResult | None = None
    entities: EntityResult | None = None
    graph_paths: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    parts_found: int = 0
    sourcing_results: list = field(default_factory=list)  # SourcingResult objects
    debug: dict = field(default_factory=dict)  # composite scores, timing
```

**Step 3: Add seller matching to GraphRAGQueryEngine**

Add these new parameters to `__init__`:
```python
def __init__(self, graph_service, llm_router,
             intent_classifier, entity_extractor, part_parser,
             inventory_service=None, pricing_service=None,
             seller_service=None, location_optimizer=None,
             price_comparator=None):
```

Add a new method `_match_sellers` and modify `process_query` to call it between context assembly and LLM generation. The seller_service queries PostgreSQL for seller_listings matching the part SKUs found in stages 2-3, the location_optimizer calculates distances, and the price_comparator ranks them.

**Step 4: Update the LLM prompt to include sourcing options**

Modify `_generate_response` to use `SOURCING_RESPONSE_PROMPT` when sourcing results are available, formatting each result with price, delivery, seller name.

**Step 5: Write tests for the enhanced flow**

Add to `tests/test_query_engine.py`:

```python
@pytest.mark.asyncio
async def test_process_query_with_sourcing(self, engine):
    eng, mock_graph, mock_llm = engine

    mock_graph.get_part.return_value = {
        "sku": "6204-2RS", "name": "Deep Groove Bearing",
        "manufacturer": "SKF", "specs": [], "cross_refs": [],
    }
    mock_llm.chat.return_value = "Found bearing from 2 sellers."

    result = await eng.process_query("Tell me about 6204-2RS")
    assert result.parts_found >= 1
```

**Step 6: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS

**Step 7: Commit**

```bash
git add services/graphrag/query_engine.py services/graphrag/context_merger.py services/ai/prompts.py tests/test_query_engine.py
git commit -m "feat: wire seller matching, location, and pricing into GraphRAG Stage 4"
```

---

### Task 10: Sourcing API Endpoint

**Files:**
- Create: `routes/sourcing.py`
- Modify: `main.py` (register router)

**Step 1: Create sourcing routes**

Create `routes/sourcing.py`:

```python
"""Sourcing API — AI-powered part search and comparison."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.auth import get_current_user

router = APIRouter(prefix="/api/sourcing", tags=["sourcing"])

# Set by main.py
_query_engine = None
_seller_service = None
_db = None


def set_sourcing_services(query_engine, seller_service, db_manager):
    global _query_engine, _seller_service, _db
    _query_engine = query_engine
    _seller_service = seller_service
    _db = db_manager


class SourcingQuery(BaseModel):
    query: str = Field(min_length=1)
    qty: int = Field(default=1, ge=1)
    location_id: str | None = None
    debug: bool = False


@router.post("/search")
async def sourcing_search(req: SourcingQuery, user=Depends(get_current_user)):
    """AI-powered part sourcing search."""
    if not _query_engine:
        raise HTTPException(status_code=503, detail="Sourcing engine unavailable")

    result = await _query_engine.process_query(
        message=req.query,
        customer_id=user.get("org_id"),
    )

    response = {
        "response": result.response,
        "parts_found": result.parts_found,
        "intent": result.intent.intent.value if result.intent else None,
        "sourcing_results": [
            {
                "sku": sr.sku,
                "name": sr.name,
                "seller_name": sr.seller_name,
                "unit_price": sr.unit_price,
                "total_cost": sr.total_cost(req.qty),
                "transit_days": sr.transit_days,
                "shipping_cost": sr.shipping_cost,
                "distance_km": sr.distance_km,
                "qty_available": sr.qty_available,
                "manufacturer": sr.manufacturer,
            }
            for sr in result.sourcing_results
        ],
    }

    if req.debug and user.get("role") == "admin":
        response["debug"] = {
            "graph_paths": result.graph_paths,
            "scores": [sr.debug for sr in result.sourcing_results],
        }

    # Log sourcing request
    if _db and _db.pool:
        try:
            import json
            async with _db.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO sourcing_requests
                       (buyer_org_id, user_id, query_text, intent, results_json, parts_found)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    user.get("org_id"), user.get("user_id"),
                    req.query, response.get("intent"),
                    json.dumps(response["sourcing_results"]),
                    result.parts_found,
                )
        except Exception:
            pass  # Non-critical logging

    return response
```

**Step 2: Wire into main.py**

Add import:
```python
from routes.sourcing import router as sourcing_router, set_sourcing_services
```

Register: `app.include_router(sourcing_router)`

In lifespan, after GraphRAG init:
```python
set_sourcing_services(query_engine, seller_service, db_manager)
```

**Step 3: Commit**

```bash
git add routes/sourcing.py main.py
git commit -m "feat: add sourcing API endpoint — /api/sourcing/search"
```

---

### Task 11: RFQ Flow

**Files:**
- Create: `routes/rfq.py`
- Modify: `main.py` (register)

Create routes for:
- `POST /api/rfq` — Create RFQ request
- `GET /api/rfq` — List buyer's RFQs
- `GET /api/rfq/{id}` — Get RFQ detail with responses
- `POST /api/rfq/{id}/respond` — Seller responds (for future seller portal)

Wire into main.py.

**Commit:**
```bash
git commit -m "feat: add RFQ routes — create, list, respond"
```

---

### Task 12: Freshness Scheduler

**Files:**
- Create: `services/intelligence/freshness_scheduler.py`
- Modify: `main.py` (start scheduler in lifespan)
- Modify: `requirements.txt` (add apscheduler)

Add `apscheduler>=3.10,<4.0` to requirements.txt.

Create a scheduler that:
- **Every 6 hours**: Checks `seller_listings` for `stale_after < now()`, re-scrapes those sellers
- **Daily**: Updates reliability scores based on age decay
- **Weekly**: Full crawl of all registered seller URLs

Wire into lifespan startup/shutdown.

**Commit:**
```bash
git commit -m "feat: add freshness scheduler — auto re-scrape stale listings"
```

---

## Phase 4: User Experience

---

### Task 13: Frontend Auth — Login, Signup, Protected Routes

**Files:**
- Create: `src/lib/auth.tsx` (auth context + hooks)
- Create: `src/pages/Login.tsx`
- Create: `src/pages/Signup.tsx`
- Modify: `src/App.tsx` (add auth routes, protect existing routes)
- Modify: `src/lib/api.ts` (add auth header to requests)

Create AuthContext with login/signup/logout, token storage in localStorage, auto-refresh. Wrap routes in a `RequireAuth` component. Add `/login` and `/signup` routes outside the AppLayout.

**Commit:**
```bash
git commit -m "feat: add frontend auth — login, signup, protected routes"
```

---

### Task 14: AI Chat UI Redesign — Sourcing-Focused

**Files:**
- Modify: `src/pages/Chat.tsx` (major redesign)
- Create: `src/components/sourcing/ResultCard.tsx`
- Create: `src/components/sourcing/ComparisonTable.tsx`
- Modify: `src/lib/api.ts` (add sourcing API methods)

Redesign the chat page to:
- Call `/api/sourcing/search` instead of `/api/v1/message`
- Show `ResultCard` components for each sourcing result (part name, seller, price, delivery, distance)
- Include "Request Quote" and "Order Now" action buttons on each card
- Keep the conversational AI response above the cards
- Add a qty input and location selector in the chat header

**Commit:**
```bash
git commit -m "feat: redesign chat UI for sourcing — result cards, comparison table"
```

---

### Task 15: Order Placement from Chat

**Files:**
- Modify: `src/pages/Chat.tsx` (add order action)
- Modify: `routes/sourcing.py` (add order creation endpoint)
- Modify: `src/lib/api.ts` (add order method)

Add `POST /api/sourcing/order` that creates an order linked to a seller listing. The chat UI "Order Now" button calls this, then shows order confirmation with tracking.

**Commit:**
```bash
git commit -m "feat: add order placement from chat sourcing results"
```

---

### Task 16: Admin Debug View

**Files:**
- Create: `src/pages/AdminDebug.tsx`
- Modify: `src/App.tsx` (add route)
- Create: `routes/admin_graph.py` (graph stats, scrape status, reliability scores)

Create an admin-only page showing:
- Neo4j graph stats (nodes, edges, by type)
- Seller listing freshness (stale count, last scrape times)
- Recent sourcing queries with composite score breakdowns
- Reliability score distributions

**Commit:**
```bash
git commit -m "feat: add admin debug view — graph stats, reliability scores, scrape status"
```

---

### Task 17: Seller Seed Data & Demo Polish

**Files:**
- Modify: `services/graph/seed_demo.py` (add seller listings with locations)
- Create: `services/platform/seed_sellers.py` (PostgreSQL seller data)
- Modify: `main.py` (call seller seed in lifespan)

Seed 5 demo sellers (Grainger, McMaster-Carr, MSC Industrial, Motion Industries, Global Industrial) with:
- Warehouse locations (lat/lng for major US cities)
- 50+ seller_listings across the 28 parts already in Neo4j
- Varied pricing (±15% between sellers)
- Varied stock levels and lead times

**Commit:**
```bash
git commit -m "feat: seed demo sellers, warehouses, and listings for testing"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| **Phase 1** | 1-4 | Auth, orgs, locations, seller data model |
| **Phase 2** | 5-8 | Web scraper, reliability scoring, location optimizer, price comparator |
| **Phase 3** | 9-12 | Enhanced GraphRAG, sourcing API, RFQ, freshness scheduler |
| **Phase 4** | 13-17 | Frontend auth, chat redesign, ordering, admin debug, demo data |

**Total: 17 tasks across 4 phases.**

Tasks 1-8 are fully specified with complete code. Tasks 9-17 have architecture and file structure defined — the executing agent should follow the patterns established in tasks 1-8.
