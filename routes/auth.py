"""Auth API routes — signup, login, refresh, me."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

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
