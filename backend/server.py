from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, EmailStr


# ---------- DB ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# ---------- App ----------
app = FastAPI(title="Kreeda Nation API")
api = APIRouter(prefix="/api")

JWT_ALGORITHM = "HS256"


# ---------- WebSocket connection manager ----------
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


# ---------- Auth utils ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str, company_id: Optional[str] = None) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "company_id": company_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        h = request.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            token = h[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user_optional(request: Request) -> Optional[dict]:
    """Like get_current_user but returns None instead of raising for anonymous users."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("admin", "platform_admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


async def require_platform_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("platform_admin", "admin"):
        raise HTTPException(status_code=403, detail="Platform admin only")
    return user


async def require_company_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("company_admin", "platform_admin", "admin"):
        raise HTTPException(status_code=403, detail="Company admin only")
    if user.get("role") == "company_admin" and not user.get("company_id"):
        raise HTTPException(status_code=403, detail="No company assigned")
    return user


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=12 * 3600,
        path="/",
    )


# ---------- Models ----------
class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class CompanySignupBody(BaseModel):
    company_name: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str
    contact_phone: Optional[str] = ""
    logo_url: Optional[str] = ""


class Company(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    slug: str
    logo_url: Optional[str] = ""
    contact_email: Optional[str] = ""
    contact_phone: Optional[str] = ""
    owner_user_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


SportType = Literal[
    "cricket", "football", "badminton", "tabletennis", "basketball",
    "volleyball", "chess", "quiz", "hackathon", "other"
]
FixtureFormat = Literal["round_robin", "knockout"]
EventStatus = Literal["upcoming", "ongoing", "completed"]
EventType = Literal["single_company", "inter_company", "playsphere_organized"]
MatchStatus = Literal["scheduled", "live", "completed"]


class Team(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    department: Optional[str] = ""
    captain: Optional[str] = ""
    captain_player_id: Optional[str] = None
    members: List[str] = Field(default_factory=list)
    color: Optional[str] = "#007AFF"
    logo_url: Optional[str] = ""
    event_id: Optional[str] = None
    company_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TeamCreate(BaseModel):
    name: str
    department: Optional[str] = ""
    captain: Optional[str] = ""
    color: Optional[str] = "#007AFF"
    logo_url: Optional[str] = ""
    event_id: Optional[str] = None
    company_id: Optional[str] = None


class Player(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    team_id: str
    role: Optional[str] = ""
    jersey_number: Optional[int] = None
    avatar_url: Optional[str] = ""
    bio: Optional[str] = ""
    stats: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PlayerCreate(BaseModel):
    name: str
    team_id: str
    role: Optional[str] = ""
    jersey_number: Optional[int] = None
    avatar_url: Optional[str] = ""
    bio: Optional[str] = ""


class Event(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    sport: SportType
    description: Optional[str] = ""
    format: FixtureFormat = "round_robin"
    event_type: EventType = "single_company"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    venue: Optional[str] = ""
    status: EventStatus = "upcoming"
    banner_url: Optional[str] = ""
    stream_url: Optional[str] = ""
    company_id: Optional[str] = None
    companies: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventCreate(BaseModel):
    name: str
    sport: SportType
    description: Optional[str] = ""
    format: FixtureFormat = "round_robin"
    event_type: EventType = "single_company"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    venue: Optional[str] = ""
    banner_url: Optional[str] = ""
    stream_url: Optional[str] = ""
    companies: List[str] = Field(default_factory=list)


class Fixture(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str
    round: int = 1
    match_number: int = 1
    team_a_id: Optional[str] = None
    team_b_id: Optional[str] = None
    scheduled_at: Optional[str] = None
    venue: Optional[str] = ""
    status: MatchStatus = "scheduled"
    score: dict = Field(default_factory=dict)
    winner_id: Optional[str] = None
    bracket_position: Optional[str] = None  # for knockout
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ScoreUpdate(BaseModel):
    score: dict
    status: Optional[MatchStatus] = None
    winner_id: Optional[str] = None


SponsorTier = Literal["title", "gold", "silver", "bronze"]


class Sponsor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    tier: SponsorTier = "bronze"
    logo_url: str
    website: Optional[str] = ""
    description: Optional[str] = ""
    show_in_banner: bool = True
    event_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SponsorCreate(BaseModel):
    name: str
    tier: SponsorTier = "bronze"
    logo_url: str
    website: Optional[str] = ""
    description: Optional[str] = ""
    show_in_banner: bool = True
    event_id: Optional[str] = None


# ---------- Services & Bookings ----------
ServiceCategory = Literal[
    "streaming", "apparel", "merchandise", "awards", "venue", "equipment", "training", "other"
]
BookingStatus = Literal["pending", "approved", "fulfilled", "cancelled"]


class ServiceField(BaseModel):
    key: str
    label: str
    type: Literal["number", "text", "textarea", "select"] = "number"
    options: Optional[List[str]] = None
    required: bool = False
    min: Optional[float] = None
    max: Optional[float] = None
    default: Optional[str] = None
    help_text: Optional[str] = ""


class ServiceVariant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    image_url: str
    extra_price: float = 0.0
    description: Optional[str] = ""


class Service(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: ServiceCategory
    description: str = ""
    images: List[str] = Field(default_factory=list)
    base_price: float = 0.0
    currency: str = "USD"
    price_unit: str = "per booking"  # e.g., "per day", "per match", "each"
    config_fields: List[ServiceField] = Field(default_factory=list)
    variants: List[ServiceVariant] = Field(default_factory=list)
    allow_custom_text: bool = False
    custom_text_label: Optional[str] = "Inscription / Custom text"
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ServiceCreate(BaseModel):
    name: str
    category: ServiceCategory
    description: Optional[str] = ""
    images: List[str] = Field(default_factory=list)
    base_price: float = 0.0
    currency: str = "USD"
    price_unit: Optional[str] = "per booking"
    config_fields: List[ServiceField] = Field(default_factory=list)
    variants: List[ServiceVariant] = Field(default_factory=list)
    allow_custom_text: bool = False
    custom_text_label: Optional[str] = "Inscription / Custom text"
    active: bool = True


class Booking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    company_name: str = ""
    service_id: str
    service_name: str = ""
    event_id: Optional[str] = None
    quantity: int = 1
    config: dict = Field(default_factory=dict)
    variant_id: Optional[str] = None
    variant_name: Optional[str] = None
    custom_text: Optional[str] = ""
    notes: Optional[str] = ""
    base_price: float = 0.0
    variant_price: float = 0.0
    total_price: float = 0.0
    currency: str = "USD"
    status: BookingStatus = "pending"
    created_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BookingCreate(BaseModel):
    service_id: str
    event_id: Optional[str] = None
    quantity: int = 1
    config: dict = Field(default_factory=dict)
    variant_id: Optional[str] = None
    custom_text: Optional[str] = ""
    notes: Optional[str] = ""


# ---------- Player profiles ----------
VendorType = Literal["ground", "court", "coach", "referee", "umpire", "trainer", "photographer", "videographer"]


class PlayerSignupBody(BaseModel):
    name: str
    mobile: str
    password: str
    company_id: Optional[str] = None
    email: Optional[EmailStr] = None


class PlayerLoginBody(BaseModel):
    mobile: str
    password: str


class PlayerProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    mobile: str
    email: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    photo_url: Optional[str] = ""
    dob: Optional[str] = None
    city: Optional[str] = ""
    role: Optional[str] = "any"
    batting_hand: Optional[str] = "right"
    bowling_style: Optional[str] = "none"
    jersey_number: Optional[int] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    bio: Optional[str] = ""
    cricheroes_url: Optional[str] = ""
    view_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------- Vendors ----------
class VendorSignupBody(BaseModel):
    business_name: str
    vendor_type: VendorType
    contact_name: str
    mobile: str
    email: EmailStr
    password: str
    city: str


class Vendor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    business_name: str
    vendor_type: VendorType
    contact_name: str
    mobile: str
    email: str
    city: str
    approved: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CancellationPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_refund_hours_before: int = 24  # ≥ this many hours before slot: 100% refund
    partial_refund_hours_before: int = 6  # ≥ this many hours: partial refund
    partial_refund_percent: int = 50  # what % to refund in partial window
    no_refund_window_hours: int = 2  # < this many hours: 0% refund


class ReschedulePolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    free_reschedule_hours_before: int = 24
    max_reschedules: int = 2
    fee_amount: float = 0


class HappyHour(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str = "Happy Hour"
    days: List[int] = Field(default_factory=list)  # 0=Mon..6=Sun. Empty = all days
    start: str = "00:00"
    end: str = "00:00"
    factor: float = 1.0  # e.g. 0.75 for 25% off


class VendorListing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    vendor_type: VendorType
    title: str
    description: str = ""
    images: List[str] = Field(default_factory=list)
    city: str
    sports: List[str] = Field(default_factory=list)
    price: float
    currency: str = "INR"
    price_unit: str = "per hour"
    capacity: Optional[int] = None
    facilities: List[str] = Field(default_factory=list)
    approved: bool = False
    active: bool = True
    cancellation_policy: Optional[CancellationPolicy] = None
    reschedule_policy: Optional[ReschedulePolicy] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorListingCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    images: List[str] = Field(default_factory=list)
    city: str
    vendor_type: Optional[VendorType] = None
    sports: List[str] = Field(default_factory=list)
    price: float
    currency: str = "INR"
    price_unit: Optional[str] = "per hour"
    capacity: Optional[int] = None
    facilities: List[str] = Field(default_factory=list)
    active: bool = True


class VendorBookingRequest(BaseModel):
    listing_id: str
    sub_unit_id: Optional[str] = None
    requested_date: str
    start_time: str
    end_time: Optional[str] = None
    hours: Optional[int] = None
    sport: Optional[str] = None
    notes: Optional[str] = ""


class VendorBooking(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    listing_id: str
    listing_title: str
    vendor_id: str
    vendor_type: str
    company_id: str
    company_name: str
    requested_date: str
    start_time: str
    end_time: str
    hours: int = 1
    sub_unit_id: Optional[str] = None
    sport: Optional[str] = None
    city: Optional[str] = None
    price: float
    currency: str
    total: float = 0
    notes: str = ""
    admin_notes: Optional[str] = ""
    status: str = "pending"
    notifications: List[dict] = Field(default_factory=list)
    created_by: str
    hr_email: Optional[str] = None
    reschedule_count: int = 0
    previous_slots: List[dict] = Field(default_factory=list)
    cancelled_at: Optional[str] = None
    refund_amount: Optional[float] = None
    refund_reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------- Site settings (singleton) ----------
class SiteSettings(BaseModel):
    facebook_url: Optional[str] = ""
    instagram_url: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    twitter_url: Optional[str] = ""
    youtube_url: Optional[str] = ""
    contact_email: Optional[str] = "contact@kreedanation.com"
    contact_phone: Optional[str] = ""
    contact_address: Optional[str] = ""
    contact_hours: Optional[str] = "Mon–Sat · 09:00 – 19:00 IST"
    contact_map_url: Optional[str] = ""


async def _user_with_company(user: dict) -> dict:
    """Attach company_name (if any) and strip password fields."""
    out = {k: user.get(k) for k in ["id", "email", "name", "role", "company_id"]}
    out["company_name"] = None
    if out.get("company_id"):
        c = await db.companies.find_one({"id": out["company_id"]}, {"_id": 0, "name": 1})
        if c:
            out["company_name"] = c["name"]
    return out


# ---------- Auth Endpoints ----------
@api.post("/auth/register", response_model=UserPublic)
async def register(body: RegisterBody, response: Response):
    email = body.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": body.name,
        "role": "viewer",
        "company_id": None,
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user)
    token = create_access_token(user["id"], user["email"], user["role"], None)
    set_auth_cookie(response, token)
    return UserPublic(**await _user_with_company(user))


@api.post("/auth/login", response_model=UserPublic)
async def login(body: LoginBody, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], user["email"], user["role"], user.get("company_id"))
    set_auth_cookie(response, token)
    return UserPublic(**await _user_with_company(user))


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return UserPublic(**await _user_with_company(user))


# ---------- Company Signup ----------
def _slugify(s: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out or "company"


@api.post("/companies/signup", response_model=UserPublic)
async def company_signup(body: CompanySignupBody, response: Response):
    email = body.admin_email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    base_slug = _slugify(body.company_name)
    slug = base_slug
    n = 1
    while await db.companies.find_one({"slug": slug}):
        n += 1
        slug = f"{base_slug}-{n}"
    company = Company(
        name=body.company_name,
        slug=slug,
        logo_url=body.logo_url or "",
        contact_email=email,
        contact_phone=body.contact_phone or "",
    )
    user_id = str(uuid.uuid4())
    company.owner_user_id = user_id
    await db.companies.insert_one(company.model_dump())
    user_doc = {
        "id": user_id,
        "email": email,
        "name": body.admin_name,
        "role": "company_admin",
        "company_id": company.id,
        "password_hash": hash_password(body.admin_password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)
    token = create_access_token(user_id, email, "company_admin", company.id)
    set_auth_cookie(response, token)
    return UserPublic(**await _user_with_company(user_doc))


@api.get("/companies/me")
async def get_my_company(user: dict = Depends(require_company_admin)):
    if not user.get("company_id"):
        raise HTTPException(404, "No company")
    c = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Company not found")
    return c


@api.patch("/companies/me")
async def update_my_company(body: dict, user: dict = Depends(require_company_admin)):
    body.pop("id", None)
    body.pop("slug", None)
    body.pop("owner_user_id", None)
    await db.companies.update_one({"id": user["company_id"]}, {"$set": body})
    return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})


@api.get("/companies")
async def list_companies(_: dict = Depends(require_platform_admin)):
    return await db.companies.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


# ---------- Helper for sport-specific default scores ----------
def default_score(sport: str) -> dict:
    if sport == "cricket":
        return {"team_a": {"runs": 0, "wickets": 0, "overs": 0.0},
                "team_b": {"runs": 0, "wickets": 0, "overs": 0.0}}
    if sport == "football":
        return {"team_a": {"goals": 0}, "team_b": {"goals": 0}}
    if sport == "basketball":
        return {"team_a": {"points": 0, "q": 1}, "team_b": {"points": 0, "q": 1}}
    if sport == "badminton" or sport == "tabletennis":
        return {"team_a": {"sets": [0, 0, 0]}, "team_b": {"sets": [0, 0, 0]}}
    if sport == "volleyball":
        return {"team_a": {"sets": [0, 0, 0]}, "team_b": {"sets": [0, 0, 0]}}
    if sport == "chess":
        return {"team_a": {"points": 0}, "team_b": {"points": 0}}
    if sport == "quiz":
        return {"team_a": {"points": 0}, "team_b": {"points": 0}}
    if sport == "hackathon":
        return {"team_a": {"score": 0}, "team_b": {"score": 0}}
    return {"team_a": {"score": 0}, "team_b": {"score": 0}}


# ---------- Events ----------
@api.get("/events", response_model=List[Event])
async def list_events(
    company_id: Optional[str] = None,
    scope: Optional[str] = None,
    user: Optional[dict] = Depends(get_current_user_optional),
):
    q: dict = {}
    if company_id:
        q["company_id"] = company_id
    if scope == "mine" and user and user.get("role") == "company_admin":
        cid = user.get("company_id")
        if cid:
            q = {"$or": [{"company_id": cid}, {"companies": cid}]}
    docs = await db.events.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [Event(**d) for d in docs]


@api.get("/my/teams", response_model=List[Team])
async def my_teams(user: dict = Depends(require_company_admin)):
    cid = user.get("company_id")
    if not cid:
        return []
    docs = await db.teams.find({"company_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [Team(**d) for d in docs]


@api.get("/venues/suggest")
async def venues_suggest(city: Optional[str] = None, q: Optional[str] = None):
    """Venue picker for event creation — approved venue listings filtered by city / name."""
    flt: dict = {"approved": True, "active": True, "vendor_type": {"$in": ["ground", "court"]}}
    if city:
        flt["city"] = {"$regex": f"^{city}$", "$options": "i"}
    if q:
        flt["title"] = {"$regex": q, "$options": "i"}
    docs = await db.vendor_listings.find(flt, {"_id": 0, "title": 1, "city": 1, "price": 1, "currency": 1, "id": 1, "sports": 1}).limit(40).to_list(40)
    return docs


@api.get("/events/{event_id}", response_model=Event)
async def get_event(event_id: str):
    doc = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Event not found")
    return Event(**doc)


@api.post("/events", response_model=Event)
async def create_event(body: EventCreate, user: dict = Depends(require_admin)):
    payload = body.model_dump()
    # company_admin events are stamped with their company_id
    if user.get("role") == "company_admin":
        payload["company_id"] = user.get("company_id")
    ev = Event(**payload)
    await db.events.insert_one(ev.model_dump())
    return ev


@api.patch("/events/{event_id}", response_model=Event)
async def update_event(event_id: str, body: dict, user: dict = Depends(require_admin)):
    body.pop("id", None)
    existing = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Event not found")
    if user.get("role") == "company_admin" and existing.get("company_id") != user.get("company_id"):
        raise HTTPException(403, "Not your event")
    await db.events.update_one({"id": event_id}, {"$set": body})
    doc = await db.events.find_one({"id": event_id}, {"_id": 0})
    return Event(**doc)


@api.delete("/events/{event_id}")
async def delete_event(event_id: str, user: dict = Depends(require_admin)):
    existing = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not existing:
        return {"ok": True}
    if user.get("role") == "company_admin" and existing.get("company_id") != user.get("company_id"):
        raise HTTPException(403, "Not your event")
    await db.events.delete_one({"id": event_id})
    await db.teams.update_many({"event_id": event_id}, {"$set": {"event_id": None}})
    await db.fixtures.delete_many({"event_id": event_id})
    return {"ok": True}


# ---------- Teams ----------
@api.get("/teams", response_model=List[Team])
async def list_teams(event_id: Optional[str] = None):
    q = {"event_id": event_id} if event_id else {}
    docs = await db.teams.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [Team(**d) for d in docs]


@api.get("/teams/{team_id}", response_model=Team)
async def get_team(team_id: str):
    doc = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Team not found")
    return Team(**doc)


@api.post("/teams", response_model=Team)
async def create_team(body: TeamCreate):
    # Open team registration (any authenticated user can register a team is overkill — allow public for engagement)
    t = Team(**body.model_dump())
    await db.teams.insert_one(t.model_dump())
    return t


@api.patch("/teams/{team_id}", response_model=Team)
async def update_team(team_id: str, body: dict, _: dict = Depends(require_admin)):
    body.pop("id", None)
    await db.teams.update_one({"id": team_id}, {"$set": body})
    doc = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Team not found")
    return Team(**doc)


@api.delete("/teams/{team_id}")
async def delete_team(team_id: str, _: dict = Depends(require_admin)):
    await db.teams.delete_one({"id": team_id})
    await db.players.delete_many({"team_id": team_id})
    return {"ok": True}


# ---------- Players (team roster — legacy, distinct from player accounts) ----------
@api.get("/team-players", response_model=List[Player])
async def list_players(team_id: Optional[str] = None):
    q = {"team_id": team_id} if team_id else {}
    docs = await db.players.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [Player(**d) for d in docs]


@api.get("/team-players/{player_id}", response_model=Player)
async def get_player(player_id: str):
    doc = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Player not found")
    return Player(**doc)


@api.post("/team-players", response_model=Player)
async def create_player(body: PlayerCreate):
    p = Player(**body.model_dump())
    await db.players.insert_one(p.model_dump())
    return p


@api.patch("/team-players/{player_id}", response_model=Player)
async def update_player(player_id: str, body: dict, _: dict = Depends(require_admin)):
    body.pop("id", None)
    await db.players.update_one({"id": player_id}, {"$set": body})
    doc = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Player not found")
    return Player(**doc)


@api.delete("/team-players/{player_id}")
async def delete_player(player_id: str, _: dict = Depends(require_admin)):
    await db.players.delete_one({"id": player_id})
    return {"ok": True}


# ---------- Event-scoped team & member management (Phase 1: CricHeroes-style setup chain) ----------
def _gen_temp_password(length: int = 10) -> str:
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _can_manage_event(user: dict, event: dict) -> bool:
    role = user.get("role")
    if role in ("platform_admin", "admin"):
        return True
    if role == "company_admin":
        cid = user.get("company_id")
        if not cid:
            return False
        if event.get("company_id") == cid:
            return True
        if cid in (event.get("companies") or []):
            return True
    return False


async def _can_manage_team(user: dict, event: dict, team: dict) -> bool:
    if await _can_manage_event(user, event):
        # company_admin can only manage their own company's teams in inter_company
        if user.get("role") == "company_admin" and event.get("event_type") == "inter_company":
            return team.get("company_id") == user.get("company_id")
        return True
    # captain?
    if user.get("role") == "player":
        prof = await db.player_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
        if prof and team.get("captain_player_id") == prof["id"]:
            return True
    return False


async def _get_event_or_404(event_id: str) -> dict:
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(404, "Event not found")
    return ev


async def _get_team_or_404(team_id: str, event_id: str) -> dict:
    t = await db.teams.find_one({"id": team_id, "event_id": event_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Team not found in this event")
    return t


@api.patch("/events/{event_id}/stream")
async def update_event_stream(event_id: str, body: dict, user: dict = Depends(get_current_user)):
    ev = await _get_event_or_404(event_id)
    if not await _can_manage_event(user, ev):
        raise HTTPException(403, "Not allowed")
    stream_url = (body or {}).get("stream_url", "")
    await db.events.update_one({"id": event_id}, {"$set": {"stream_url": stream_url}})
    return {"ok": True, "stream_url": stream_url}


@api.get("/events/{event_id}/companies")
async def list_event_companies(event_id: str):
    ev = await _get_event_or_404(event_id)
    ids = list({*(ev.get("companies") or []), *([ev["company_id"]] if ev.get("company_id") else [])})
    if not ids:
        return []
    docs = await db.companies.find({"id": {"$in": ids}}, {"_id": 0}).to_list(100)
    return docs


async def _unique_company_slug(base: str) -> str:
    slug = base.lower().strip().replace(" ", "-")[:40] or "company"
    candidate = slug
    n = 0
    while await db.companies.find_one({"slug": candidate}):
        n += 1
        candidate = f"{slug}-{n}"
    return candidate


async def _create_company_with_hr(name: str, hr_name: str, hr_email: str) -> tuple:
    """Create a Company + a company_admin HR user. Returns (company_id, hr_email, temp_password)."""
    if await db.users.find_one({"email": hr_email}):
        raise HTTPException(400, "HR email already in use")
    slug = await _unique_company_slug(name)
    comp = Company(name=name, slug=slug, contact_email=hr_email)
    await db.companies.insert_one(comp.model_dump())
    temp_password = _gen_temp_password()
    hr_user_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": hr_user_id,
        "email": hr_email,
        "name": hr_name or f"{name} HR",
        "role": "company_admin",
        "company_id": comp.id,
        "password_hash": hash_password(temp_password),
        "must_reset": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.companies.update_one({"id": comp.id}, {"$set": {"owner_user_id": hr_user_id}})
    logger.warning("HR auto-created for company %s: email=%s temp_password=%s", name, hr_email, temp_password)
    return comp.id, hr_email, temp_password


@api.post("/events/{event_id}/companies")
async def add_event_company(event_id: str, body: dict, _: dict = Depends(require_platform_admin)):
    await _get_event_or_404(event_id)
    body = body or {}
    company_id = body.get("company_id")
    new_company = body.get("new_company")
    temp_password = None
    hr_email = None
    if not company_id and new_company:
        cname = (new_company.get("name") or "").strip()
        hr_name = (new_company.get("hr_name") or "").strip()
        hr_email = (new_company.get("hr_email") or "").strip().lower()
        if not (cname and hr_email):
            raise HTTPException(400, "name and hr_email required")
        company_id, hr_email, temp_password = await _create_company_with_hr(cname, hr_name, hr_email)
    if not company_id:
        raise HTTPException(400, "company_id or new_company required")
    if not await db.companies.find_one({"id": company_id}):
        raise HTTPException(404, "Company not found")
    await db.events.update_one({"id": event_id}, {"$addToSet": {"companies": company_id}})
    return {"ok": True, "company_id": company_id, "hr_email": hr_email, "temp_password": temp_password}


@api.delete("/events/{event_id}/companies/{company_id}")
async def remove_event_company(event_id: str, company_id: str, _: dict = Depends(require_platform_admin)):
    await db.events.update_one({"id": event_id}, {"$pull": {"companies": company_id}})
    return {"ok": True}


@api.post("/events/{event_id}/teams", response_model=Team)
async def create_event_team(event_id: str, body: TeamCreate, user: dict = Depends(get_current_user)):
    ev = await _get_event_or_404(event_id)
    if not await _can_manage_event(user, ev):
        raise HTTPException(403, "Not allowed")
    payload = body.model_dump()
    payload["event_id"] = event_id
    # company scoping
    if user.get("role") == "company_admin":
        payload["company_id"] = user.get("company_id")
    elif not payload.get("company_id"):
        payload["company_id"] = ev.get("company_id")
    # inter_company: ensure company is in participating list
    if ev.get("event_type") == "inter_company" and payload["company_id"]:
        if payload["company_id"] not in (ev.get("companies") or []):
            await db.events.update_one({"id": event_id}, {"$addToSet": {"companies": payload["company_id"]}})
    t = Team(**payload)
    await db.teams.insert_one(t.model_dump())
    return t


@api.post("/events/{event_id}/teams/{team_id}/captain", response_model=Team)
async def set_team_captain(event_id: str, team_id: str, body: dict, user: dict = Depends(get_current_user)):
    ev = await _get_event_or_404(event_id)
    t = await _get_team_or_404(team_id, event_id)
    if not await _can_manage_event(user, ev):
        if user.get("role") == "company_admin" and t.get("company_id") != user.get("company_id"):
            raise HTTPException(403, "Not your team")
        if user.get("role") not in ("platform_admin", "admin", "company_admin"):
            raise HTTPException(403, "Not allowed")
    player_id = (body or {}).get("player_id")
    if not player_id:
        raise HTTPException(400, "player_id required")
    prof = await db.player_profiles.find_one({"id": player_id}, {"_id": 0})
    if not prof:
        raise HTTPException(404, "Player not found")
    members = list(t.get("members") or [])
    if player_id not in members:
        members.append(player_id)
    await db.teams.update_one(
        {"id": team_id},
        {"$set": {"captain_player_id": player_id, "captain": prof.get("name", ""), "members": members}},
    )
    doc = await db.teams.find_one({"id": team_id}, {"_id": 0})
    return Team(**doc)


@api.get("/events/{event_id}/teams/{team_id}/members")
async def list_team_members(event_id: str, team_id: str, user: dict = Depends(get_current_user)):
    await _get_event_or_404(event_id)
    t = await _get_team_or_404(team_id, event_id)
    ids = t.get("members") or []
    if not ids:
        return []
    docs = await db.player_profiles.find({"id": {"$in": ids}}, {"_id": 0}).to_list(200)
    # mask mobiles for non-self
    for d in docs:
        if user.get("id") != d.get("user_id"):
            m = d.get("mobile") or ""
            d["mobile_masked"] = "•••• " + m[-4:] if len(m) >= 4 else m
            d.pop("mobile", None)
    return docs


async def _quick_add_player(quick: dict, team: dict) -> tuple:
    """Quick-create a player profile. Returns (player_id, temp_password)."""
    name = (quick.get("name") or "").strip()
    mobile = (quick.get("mobile") or "").strip()
    email = (quick.get("email") or "").strip().lower() or None
    if not (name and mobile):
        raise HTTPException(400, "name and mobile required for quick add")
    existing = await db.player_profiles.find_one({"mobile": mobile}, {"_id": 0})
    if existing:
        return existing["id"], None
    login_email = email or f"player_{mobile}@players.playsphere.app"
    if await db.users.find_one({"email": login_email}):
        raise HTTPException(400, "Email already in use")
    temp_password = _gen_temp_password()
    user_id = str(uuid.uuid4())
    company_id = team.get("company_id")
    company_name = None
    if company_id:
        c = await db.companies.find_one({"id": company_id}, {"_id": 0, "name": 1})
        company_name = c["name"] if c else None
    await db.users.insert_one({
        "id": user_id, "email": login_email, "name": name, "role": "player",
        "company_id": company_id, "mobile": mobile,
        "password_hash": hash_password(temp_password), "must_reset": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    prof = PlayerProfile(
        user_id=user_id, name=name, mobile=mobile, email=login_email,
        company_id=company_id, company_name=company_name,
    )
    await db.player_profiles.insert_one(prof.model_dump())
    logger.warning("Quick-add player created: name=%s mobile=%s email=%s temp_password=%s",
                   name, mobile, login_email, temp_password)
    return prof.id, temp_password


@api.post("/events/{event_id}/teams/{team_id}/members")
async def add_team_member(event_id: str, team_id: str, body: dict, user: dict = Depends(get_current_user)):
    ev = await _get_event_or_404(event_id)
    t = await _get_team_or_404(team_id, event_id)
    if not await _can_manage_team(user, ev, t):
        raise HTTPException(403, "Not allowed")
    body = body or {}
    pid = body.get("player_id")
    quick = body.get("quick")
    temp_password = None
    if not pid and quick:
        pid, temp_password = await _quick_add_player(quick, t)
    if not pid:
        raise HTTPException(400, "player_id or quick payload required")
    if not await db.player_profiles.find_one({"id": pid}):
        raise HTTPException(404, "Player not found")
    await db.teams.update_one({"id": team_id}, {"$addToSet": {"members": pid}})
    return {"ok": True, "player_id": pid, "temp_password": temp_password}


@api.delete("/events/{event_id}/teams/{team_id}/members/{player_id}")
async def remove_team_member(event_id: str, team_id: str, player_id: str, user: dict = Depends(get_current_user)):
    ev = await _get_event_or_404(event_id)
    t = await _get_team_or_404(team_id, event_id)
    if not await _can_manage_team(user, ev, t):
        raise HTTPException(403, "Not allowed")
    update = {"$pull": {"members": player_id}}
    if t.get("captain_player_id") == player_id:
        update["$set"] = {"captain_player_id": None, "captain": ""}
    await db.teams.update_one({"id": team_id}, update)
    return {"ok": True}


# ---------- Forgot / reset password (all roles) ----------
@api.post("/players/forgot-password")
@api.post("/auth/forgot-password")
async def forgot_password(body: dict):
    email = ((body or {}).get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "email required")
    user = await db.users.find_one({"email": email})
    # Don't leak whether email exists; respond OK either way
    if user:
        import secrets as _secrets
        token = _secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        await db.password_resets.insert_one({
            "token": token, "user_id": user["id"], "email": email,
            "role": user.get("role", ""),
            "expires_at": expires_at, "used": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        frontend = os.environ.get("FRONTEND_URL", "")
        reset_url = f"{frontend}/reset-password?token={token}" if frontend else f"/reset-password?token={token}"
        logger.warning("PASSWORD RESET LINK for %s: %s", email, reset_url)
    return {"ok": True}


@api.post("/players/reset-password")
@api.post("/auth/reset-password")
async def reset_password(body: dict):
    token = ((body or {}).get("token") or "").strip()
    new_password = (body or {}).get("new_password") or ""
    if not (token and new_password):
        raise HTTPException(400, "token and new_password required")
    if len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    rec = await db.password_resets.find_one({"token": token, "used": False})
    if not rec:
        raise HTTPException(400, "Invalid or used token")
    if rec["expires_at"] < datetime.now(timezone.utc).isoformat():
        raise HTTPException(400, "Token expired")
    await db.users.update_one(
        {"id": rec["user_id"]},
        {"$set": {"password_hash": hash_password(new_password), "must_reset": False}},
    )
    await db.password_resets.update_one({"token": token}, {"$set": {"used": True}})
    return {"ok": True}


# ---------- Fixture generation ----------
def generate_round_robin(team_ids: List[str], event_id: str) -> List[dict]:
    teams = list(team_ids)
    if len(teams) % 2 == 1:
        teams.append(None)  # bye
    n = len(teams)
    fixtures = []
    half = n // 2
    arr = teams[:]
    match_num = 1
    for r in range(n - 1):
        for i in range(half):
            a, b = arr[i], arr[n - 1 - i]
            if a is not None and b is not None:
                fixtures.append({
                    "id": str(uuid.uuid4()),
                    "event_id": event_id,
                    "round": r + 1,
                    "match_number": match_num,
                    "team_a_id": a,
                    "team_b_id": b,
                    "scheduled_at": None,
                    "venue": "",
                    "status": "scheduled",
                    "score": {},
                    "winner_id": None,
                    "bracket_position": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                match_num += 1
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    return fixtures


def generate_knockout(team_ids: List[str], event_id: str) -> List[dict]:
    teams = list(team_ids)
    random.shuffle(teams)
    # next power of 2
    n = 1
    while n < len(teams):
        n *= 2
    while len(teams) < n:
        teams.append(None)  # bye
    fixtures = []
    match_num = 1

    # Round 1
    current_round_winners_slots = []
    for i in range(0, n, 2):
        a, b = teams[i], teams[i + 1]
        f_id = str(uuid.uuid4())
        fixtures.append({
            "id": f_id,
            "event_id": event_id,
            "round": 1,
            "match_number": match_num,
            "team_a_id": a,
            "team_b_id": b,
            "scheduled_at": None,
            "venue": "",
            "status": "scheduled",
            "score": {},
            "winner_id": None,
            "bracket_position": f"R1-M{match_num}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        current_round_winners_slots.append(f_id)
        match_num += 1

    # subsequent rounds (empty slots)
    rnd = 2
    prev = current_round_winners_slots
    while len(prev) > 1:
        new_slots = []
        for i in range(0, len(prev), 2):
            f_id = str(uuid.uuid4())
            fixtures.append({
                "id": f_id,
                "event_id": event_id,
                "round": rnd,
                "match_number": match_num,
                "team_a_id": None,
                "team_b_id": None,
                "scheduled_at": None,
                "venue": "",
                "status": "scheduled",
                "score": {},
                "winner_id": None,
                "bracket_position": f"R{rnd}-M{match_num}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            new_slots.append(f_id)
            match_num += 1
        prev = new_slots
        rnd += 1
    return fixtures


@api.post("/events/{event_id}/generate-fixtures")
async def generate_fixtures_endpoint(event_id: str, _: dict = Depends(require_admin)):
    ev = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not ev:
        raise HTTPException(404, "Event not found")
    teams = await db.teams.find({"event_id": event_id}, {"_id": 0, "id": 1}).to_list(500)
    team_ids = [t["id"] for t in teams]
    if len(team_ids) < 2:
        raise HTTPException(400, "Need at least 2 teams to generate fixtures")
    await db.fixtures.delete_many({"event_id": event_id})
    if ev["format"] == "knockout":
        fixtures = generate_knockout(team_ids, event_id)
    else:
        fixtures = generate_round_robin(team_ids, event_id)
    if fixtures:
        await db.fixtures.insert_many(fixtures)
    return {"ok": True, "count": len(fixtures)}


@api.get("/events/{event_id}/fixtures", response_model=List[Fixture])
async def list_fixtures(event_id: str):
    docs = await db.fixtures.find({"event_id": event_id}, {"_id": 0}).sort([("round", 1), ("match_number", 1)]).to_list(1000)
    return [Fixture(**d) for d in docs]


@api.get("/fixtures/{fixture_id}", response_model=Fixture)
async def get_fixture(fixture_id: str):
    doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Fixture not found")
    return Fixture(**doc)


# ---------- Public live scorecard (no auth) ----------
@api.get("/public/fixtures/{fixture_id}")
async def public_live_scorecard(fixture_id: str):
    """No-auth, shareable live scoreboard payload. Returns the fixture, parent event,
    both team summaries, and the current score blob. Safe for anonymous viewers."""
    fx = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
    if not fx:
        raise HTTPException(404, "Fixture not found")
    event = await db.events.find_one({"id": fx["event_id"]}, {"_id": 0}) or {}
    team_ids = [tid for tid in (fx.get("team_a_id"), fx.get("team_b_id")) if tid]
    teams = {}
    if team_ids:
        async for t in db.teams.find({"id": {"$in": team_ids}}, {"_id": 0}):
            teams[t["id"]] = {
                "id": t["id"],
                "name": t.get("name"),
                "short_name": t.get("short_name"),
                "color": t.get("color"),
                "logo_url": t.get("logo_url"),
            }
    # Strip private fields from event
    pub_event = {
        "id": event.get("id"),
        "name": event.get("name"),
        "sport": event.get("sport"),
        "format": event.get("format"),
        "location": event.get("location"),
        "company_id": event.get("company_id"),
    }
    return {
        "fixture": fx,
        "event": pub_event,
        "teams": teams,
    }


@api.patch("/fixtures/{fixture_id}", response_model=Fixture)
async def update_fixture_score(fixture_id: str, body: ScoreUpdate, _: dict = Depends(require_admin)):
    upd = {"score": body.score}
    if body.status:
        upd["status"] = body.status
    if body.winner_id:
        upd["winner_id"] = body.winner_id
    await db.fixtures.update_one({"id": fixture_id}, {"$set": upd})
    doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Fixture not found")
    # propagate winner in knockout
    if body.winner_id and doc.get("bracket_position"):
        await propagate_knockout_winner(doc)
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
    # Broadcast over WebSocket
    await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": doc})
    return Fixture(**doc)


async def propagate_knockout_winner(fixture: dict):
    event_id = fixture["event_id"]
    rnd = fixture["round"]
    # find next round fixture that should receive this winner
    next_round = rnd + 1
    next_fixtures = await db.fixtures.find(
        {"event_id": event_id, "round": next_round}, {"_id": 0}
    ).sort("match_number", 1).to_list(500)
    if not next_fixtures:
        return
    # round 1 has matches 1..N, round 2 gets pair (1,2)->slot 1, (3,4)->slot 2
    # find position in current round
    current_round_fixtures = await db.fixtures.find(
        {"event_id": event_id, "round": rnd}, {"_id": 0}
    ).sort("match_number", 1).to_list(500)
    try:
        idx = [f["id"] for f in current_round_fixtures].index(fixture["id"])
    except ValueError:
        return
    target = next_fixtures[idx // 2]
    field = "team_a_id" if idx % 2 == 0 else "team_b_id"
    await db.fixtures.update_one({"id": target["id"]}, {"$set": {field: fixture["winner_id"]}})


@api.post("/fixtures/{fixture_id}/init-score")
async def init_score(fixture_id: str, _: dict = Depends(require_admin)):
    doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Fixture not found")
    ev = await db.events.find_one({"id": doc["event_id"]}, {"_id": 0})
    score = default_score(ev["sport"])
    await db.fixtures.update_one({"id": fixture_id}, {"$set": {"score": score, "status": "live"}})
    updated = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
    await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": updated})
    return {"ok": True, "score": score}


# ---------- WebSocket ----------
@app.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # initial hello so clients can verify the channel
        await ws.send_json({"type": "hello", "ts": datetime.now(timezone.utc).isoformat()})
        while True:
            # we don't expect any inbound messages but keep the socket alive
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


# ---------- Standings ----------
@api.get("/events/{event_id}/standings")
async def get_standings(event_id: str):
    teams = await db.teams.find({"event_id": event_id}, {"_id": 0}).to_list(500)
    fixtures = await db.fixtures.find({"event_id": event_id, "status": "completed"}, {"_id": 0}).to_list(1000)
    table = {}
    for t in teams:
        table[t["id"]] = {
            "team_id": t["id"], "team_name": t["name"], "color": t.get("color", "#007AFF"),
            "played": 0, "won": 0, "lost": 0, "drawn": 0, "points": 0,
        }
    for f in fixtures:
        a, b = f.get("team_a_id"), f.get("team_b_id")
        if a and a in table:
            table[a]["played"] += 1
        if b and b in table:
            table[b]["played"] += 1
        w = f.get("winner_id")
        if w and w in table:
            table[w]["won"] += 1
            table[w]["points"] += 3
            loser = b if w == a else a
            if loser and loser in table:
                table[loser]["lost"] += 1
        elif not w and a and b:
            # draw
            if a in table:
                table[a]["drawn"] += 1
                table[a]["points"] += 1
            if b in table:
                table[b]["drawn"] += 1
                table[b]["points"] += 1
    return sorted(table.values(), key=lambda x: (-x["points"], -x["won"]))


# ---------- Sponsors ----------
@api.get("/sponsors", response_model=List[Sponsor])
async def list_sponsors(event_id: Optional[str] = None):
    flt = {"event_id": event_id} if event_id else {}
    docs = await db.sponsors.find(flt, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [Sponsor(**d) for d in docs]


@api.post("/sponsors", response_model=Sponsor)
async def create_sponsor(body: SponsorCreate, _: dict = Depends(require_admin)):
    s = Sponsor(**body.model_dump())
    await db.sponsors.insert_one(s.model_dump())
    return s


@api.patch("/sponsors/{sponsor_id}", response_model=Sponsor)
async def update_sponsor(sponsor_id: str, body: dict, _: dict = Depends(require_admin)):
    body.pop("id", None)
    await db.sponsors.update_one({"id": sponsor_id}, {"$set": body})
    doc = await db.sponsors.find_one({"id": sponsor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Sponsor not found")
    return Sponsor(**doc)


@api.delete("/sponsors/{sponsor_id}")
async def delete_sponsor(sponsor_id: str, _: dict = Depends(require_admin)):
    await db.sponsors.delete_one({"id": sponsor_id})
    return {"ok": True}


# ---------- Services (catalog) ----------
@api.get("/services", response_model=List[Service])
async def list_services(category: Optional[str] = None, include_inactive: bool = False):
    q = {}
    if category:
        q["category"] = category
    if not include_inactive:
        q["active"] = True
    docs = await db.services.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [Service(**d) for d in docs]


@api.get("/services/{service_id}", response_model=Service)
async def get_service(service_id: str):
    doc = await db.services.find_one({"id": service_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Service not found")
    return Service(**doc)


@api.post("/services", response_model=Service)
async def create_service(body: ServiceCreate, _: dict = Depends(require_platform_admin)):
    s = Service(**body.model_dump())
    await db.services.insert_one(s.model_dump())
    return s


@api.patch("/services/{service_id}", response_model=Service)
async def update_service(service_id: str, body: dict, _: dict = Depends(require_platform_admin)):
    body.pop("id", None)
    await db.services.update_one({"id": service_id}, {"$set": body})
    doc = await db.services.find_one({"id": service_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Service not found")
    return Service(**doc)


@api.delete("/services/{service_id}")
async def delete_service(service_id: str, _: dict = Depends(require_platform_admin)):
    await db.services.delete_one({"id": service_id})
    return {"ok": True}


# ---------- Bookings ----------
@api.get("/bookings", response_model=List[Booking])
async def list_bookings(user: dict = Depends(get_current_user)):
    if user.get("role") in ("platform_admin", "admin"):
        q = {}
    elif user.get("role") == "company_admin":
        q = {"company_id": user.get("company_id")}
    else:
        raise HTTPException(403, "Forbidden")
    docs = await db.bookings.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [Booking(**d) for d in docs]


@api.get("/bookings/{booking_id}", response_model=Booking)
async def get_booking(booking_id: str, user: dict = Depends(get_current_user)):
    doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    if user.get("role") == "company_admin" and doc["company_id"] != user.get("company_id"):
        raise HTTPException(403, "Forbidden")
    return Booking(**doc)


@api.post("/bookings", response_model=Booking)
async def create_booking(body: BookingCreate, user: dict = Depends(require_company_admin)):
    svc = await db.services.find_one({"id": body.service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Service not found")
    company = await db.companies.find_one({"id": user.get("company_id")}, {"_id": 0})
    if not company:
        raise HTTPException(400, "Company missing")

    variant_price = 0.0
    variant_name = None
    if body.variant_id:
        v = next((v for v in svc.get("variants", []) if v["id"] == body.variant_id), None)
        if v:
            variant_price = float(v.get("extra_price", 0))
            variant_name = v.get("name")

    qty = max(1, int(body.quantity or 1))
    base_price = float(svc.get("base_price", 0))
    total = (base_price + variant_price) * qty

    booking = Booking(
        company_id=user["company_id"],
        company_name=company.get("name", ""),
        service_id=svc["id"],
        service_name=svc["name"],
        event_id=body.event_id,
        quantity=qty,
        config=body.config or {},
        variant_id=body.variant_id,
        variant_name=variant_name,
        custom_text=body.custom_text or "",
        notes=body.notes or "",
        base_price=base_price,
        variant_price=variant_price,
        total_price=total,
        currency=svc.get("currency", "USD"),
        status="pending",
        created_by=user["id"],
    )
    await db.bookings.insert_one(booking.model_dump())
    return booking


@api.patch("/bookings/{booking_id}", response_model=Booking)
async def update_booking(booking_id: str, body: dict, user: dict = Depends(get_current_user)):
    doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    is_platform = user.get("role") in ("platform_admin", "admin")
    is_owner = user.get("role") == "company_admin" and doc["company_id"] == user.get("company_id")
    if not (is_platform or is_owner):
        raise HTTPException(403, "Forbidden")
    # company admin can only update non-platform fields & while pending
    if is_owner and not is_platform and doc.get("status") != "pending":
        raise HTTPException(400, "Booking already processed")
    if not is_platform:
        body.pop("status", None)
    body.pop("id", None)
    body.pop("company_id", None)
    body.pop("total_price", None)
    await db.bookings.update_one({"id": booking_id}, {"$set": body})
    updated = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    return Booking(**updated)


@api.delete("/bookings/{booking_id}")
async def delete_booking(booking_id: str, user: dict = Depends(get_current_user)):
    doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        return {"ok": True}
    if user.get("role") not in ("platform_admin", "admin"):
        if user.get("role") != "company_admin" or doc["company_id"] != user.get("company_id"):
            raise HTTPException(403, "Forbidden")
    await db.bookings.delete_one({"id": booking_id})
    return {"ok": True}


# ---------- Player accounts (mobile + password) ----------
@api.post("/players/register", response_model=UserPublic)
async def player_register(body: PlayerSignupBody, response: Response):
    if await db.player_profiles.find_one({"mobile": body.mobile}):
        raise HTTPException(400, "Mobile already registered")
    email = (body.email or f"player_{body.mobile}@players.playsphere.app").lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already in use")
    user_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": user_id,
        "email": email,
        "name": body.name,
        "role": "player",
        "company_id": body.company_id,
        "mobile": body.mobile,
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    company_name = None
    if body.company_id:
        c = await db.companies.find_one({"id": body.company_id}, {"_id": 0, "name": 1})
        company_name = c["name"] if c else None
    profile = PlayerProfile(
        user_id=user_id, name=body.name, mobile=body.mobile, email=email,
        company_id=body.company_id, company_name=company_name,
    )
    await db.player_profiles.insert_one(profile.model_dump())
    token = create_access_token(user_id, email, "player", body.company_id)
    set_auth_cookie(response, token)
    return UserPublic(id=user_id, email=email, name=body.name, role="player",
                      company_id=body.company_id, company_name=company_name)


@api.post("/players/login", response_model=UserPublic)
async def player_login(body: PlayerLoginBody, response: Response):
    user = await db.users.find_one({"mobile": body.mobile, "role": "player"})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid mobile or password")
    token = create_access_token(user["id"], user["email"], user["role"], user.get("company_id"))
    set_auth_cookie(response, token)
    return UserPublic(**await _user_with_company(user))


@api.get("/players/me")
async def get_my_player_profile(user: dict = Depends(get_current_user)):
    if user.get("role") != "player":
        raise HTTPException(403, "Player only")
    doc = await db.player_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Profile not found")
    return doc


@api.patch("/players/me")
async def update_my_profile(body: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "player":
        raise HTTPException(403, "Player only")
    body.pop("id", None)
    body.pop("user_id", None)
    body.pop("mobile", None)
    body.pop("view_count", None)
    if "company_id" in body:
        cid = body["company_id"]
        company_name = None
        if cid:
            c = await db.companies.find_one({"id": cid}, {"_id": 0, "name": 1})
            company_name = c["name"] if c else None
        body["company_name"] = company_name
        await db.users.update_one({"id": user["id"]}, {"$set": {"company_id": cid}})
    await db.player_profiles.update_one({"user_id": user["id"]}, {"$set": body})
    return await db.player_profiles.find_one({"user_id": user["id"]}, {"_id": 0})


@api.get("/players/profiles")
async def list_player_profiles(
    company_id: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 500,
    user: dict = Depends(get_current_user),
):
    flt = {}
    if company_id:
        flt["company_id"] = company_id
    if q:
        flt["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"city": {"$regex": q, "$options": "i"}},
            {"mobile": {"$regex": q, "$options": "i"}},
        ]
    # Sort newest-first so freshly-registered players surface immediately, then alphabetical fallback.
    limit = max(1, min(int(limit), 2000))
    docs = await db.player_profiles.find(flt, {"_id": 0}).sort([("created_at", -1), ("name", 1)]).to_list(limit)
    # Mask mobile for non-self viewers (keep last 4 digits)
    for d in docs:
        if user.get("id") != d.get("user_id"):
            m = d.get("mobile") or ""
            d["mobile_masked"] = "•••• " + m[-4:] if len(m) >= 4 else m
            d.pop("mobile", None)
    return docs


@api.get("/players/profiles/{profile_id}")
async def get_player_profile(profile_id: str, user: dict = Depends(get_current_user)):
    doc = await db.player_profiles.find_one({"id": profile_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Profile not found")
    if user.get("id") != doc.get("user_id"):
        await db.player_profiles.update_one({"id": profile_id}, {"$inc": {"view_count": 1}})
        doc["view_count"] = (doc.get("view_count", 0) or 0) + 1
        m = doc.get("mobile") or ""
        doc["mobile_masked"] = "•••• " + m[-4:] if len(m) >= 4 else m
        doc.pop("mobile", None)
    return doc


# ---------- Vendors ----------
@api.post("/vendors/signup", response_model=UserPublic)
async def vendor_signup(body: VendorSignupBody, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already in use")
    user_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": user_id, "email": email, "name": body.contact_name, "role": "vendor",
        "company_id": None, "mobile": body.mobile,
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    vendor = Vendor(
        user_id=user_id, business_name=body.business_name, vendor_type=body.vendor_type,
        contact_name=body.contact_name, mobile=body.mobile, email=email, city=body.city,
    )
    await db.vendors.insert_one(vendor.model_dump())
    token = create_access_token(user_id, email, "vendor", None)
    set_auth_cookie(response, token)
    return UserPublic(id=user_id, email=email, name=body.contact_name, role="vendor",
                      company_id=None, company_name=None)


@api.get("/vendors/me")
async def get_my_vendor(user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(403, "Vendor only")
    doc = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Vendor not found")
    return doc


@api.get("/vendors")
async def list_vendors(approved: Optional[bool] = None, _: dict = Depends(require_platform_admin)):
    flt = {}
    if approved is not None:
        flt["approved"] = approved
    return await db.vendors.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.patch("/vendors/{vendor_id}/approve")
async def approve_vendor(vendor_id: str, body: dict, _: dict = Depends(require_platform_admin)):
    approved = bool(body.get("approved", True))
    await db.vendors.update_one({"id": vendor_id}, {"$set": {"approved": approved}})
    return {"ok": True, "approved": approved}


@api.get("/vendor-listings")
async def list_public_listings(
    vendor_type: Optional[str] = None,
    city: Optional[str] = None,
    sport: Optional[str] = None,
):
    flt = {"approved": True, "active": True}
    if vendor_type:
        flt["vendor_type"] = vendor_type
    if city:
        flt["city"] = {"$regex": f"^{city}$", "$options": "i"}
    if sport:
        flt["sports"] = sport
    docs = await db.vendor_listings.find(flt, {"_id": 0, "vendor_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.get("/vendor-listings/cities")
async def list_listing_cities(sport: Optional[str] = None, vendor_type: Optional[str] = None):
    """Distinct cities for HR's location picker."""
    flt = {"approved": True, "active": True}
    if vendor_type:
        flt["vendor_type"] = vendor_type
    if sport:
        flt["sports"] = sport
    cities = await db.vendor_listings.distinct("city", flt)
    return sorted([c for c in cities if c])


@api.get("/vendor-listings/{listing_id}")
async def get_public_listing(listing_id: str):
    doc = await db.vendor_listings.find_one({"id": listing_id, "approved": True, "active": True}, {"_id": 0, "vendor_id": 0})
    if not doc:
        raise HTTPException(404, "Listing not available")
    return doc


@api.get("/vendors/me/listings")
async def vendor_my_listings(user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(403, "Vendor only")
    vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
    if not vendor:
        raise HTTPException(404, "Vendor not registered")
    return await db.vendor_listings.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/vendors/me/listings", response_model=VendorListing)
async def create_listing(body: VendorListingCreate, user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(403, "Vendor only")
    vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
    if not vendor:
        raise HTTPException(404, "Vendor not registered")
    payload = body.model_dump()
    # Use body.vendor_type when provided, else fall back to vendor's primary registered type
    listing_type = payload.pop("vendor_type", None) or vendor["vendor_type"]
    listing = VendorListing(
        vendor_id=vendor["id"], vendor_type=listing_type,
        **payload, approved=False,
    )
    await db.vendor_listings.insert_one(listing.model_dump())
    return listing


@api.patch("/vendors/me/listings/{listing_id}")
async def update_vendor_listing(listing_id: str, body: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(403, "Vendor only")
    vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
    listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
    if not vendor or not listing or listing["vendor_id"] != vendor["id"]:
        raise HTTPException(404, "Not found")
    body.pop("id", None)
    body.pop("vendor_id", None)
    body.pop("approved", None)
    # Changing vendor_type requires re-approval
    if body.get("vendor_type") and body["vendor_type"] != listing.get("vendor_type"):
        body["approved"] = False
    await db.vendor_listings.update_one({"id": listing_id}, {"$set": body})
    return await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})


@api.delete("/vendors/me/listings/{listing_id}")
async def delete_vendor_listing(listing_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(403, "Vendor only")
    vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
    listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
    if vendor and listing and listing["vendor_id"] == vendor["id"]:
        await db.vendor_listings.delete_one({"id": listing_id})
    return {"ok": True}


@api.get("/admin/listings")
async def admin_list_listings(approved: Optional[bool] = None, _: dict = Depends(require_platform_admin)):
    flt = {}
    if approved is not None:
        flt["approved"] = approved
    return await db.vendor_listings.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.patch("/admin/listings/{listing_id}/approve")
async def approve_listing(listing_id: str, body: dict, _: dict = Depends(require_platform_admin)):
    approved = bool(body.get("approved", True))
    await db.vendor_listings.update_one({"id": listing_id}, {"$set": {"approved": approved}})
    return {"ok": True, "approved": approved}


# ---------- Vendor bookings ----------
def _hhmm_add(start: str, hours: int) -> str:
    """Add `hours` to a HH:MM time string, wrapping at 24h."""
    try:
        h, m = (int(x) for x in start.split(":")[:2])
        total = (h * 60 + m + hours * 60) % (24 * 60)
        return f"{total // 60:02d}:{total % 60:02d}"
    except Exception:
        return start


def _hours_between(start: str, end: str) -> int:
    """Whole hours between two HH:MM strings (assumes same day, end > start)."""
    try:
        sh, sm = (int(x) for x in start.split(":")[:2])
        eh, em = (int(x) for x in end.split(":")[:2])
        mins = max((eh * 60 + em) - (sh * 60 + sm), 60)
        return max(1, round(mins / 60))
    except Exception:
        return 1


def send_email(to: str, subject: str, body: str, kind: str = "generic") -> dict:
    """Mocked email dispatcher. Logs to stdout/supervisor log so we can verify the flow end-to-end.
    Swap-in point for Resend / SendGrid once an API key is available — preserve the (to, subject, body) signature."""
    logger.warning(
        "[MOCK EMAIL kind=%s] to=%s | subject=%s | %s",
        kind, to or "<unset>", subject, (body or "").strip()[:500],
    )
    return {"to": to, "subject": subject, "kind": kind, "delivered": True, "mock": True}


def _booking_notification(event: str, message: str, by: dict) -> dict:
    return {
        "event": event,
        "message": message,
        "by_role": by.get("role"),
        "by_name": by.get("name") or by.get("email"),
        "at": datetime.now(timezone.utc).isoformat(),
    }


async def _log_booking_change(booking: dict, event: str, message: str, by: dict, email_to: Optional[str] = None, email_subject: Optional[str] = None):
    """Append a notification entry and dispatch a (mocked) email for the booking change.
    email_to defaults to the booking's hr_email. Pass an override to notify the vendor instead."""
    note = _booking_notification(event, message, by)
    await db.vendor_bookings.update_one({"id": booking["id"]}, {"$push": {"notifications": note}})
    recipient = email_to or booking.get("hr_email")
    subject = email_subject or f"Booking #{booking['id'][:8]} — {event.replace('_', ' ').title()}"
    if recipient:
        send_email(recipient, subject, message, kind=f"booking_{event}")


def _normalize_booking_time(start: str, end_time: Optional[str], hours: Optional[int]) -> tuple:
    """Return (end_time, hours). Raises 400 if neither hours nor end_time is provided."""
    h = int(hours) if hours else None
    e = end_time
    if h and not e:
        return _hhmm_add(start, h), h
    if e and not h:
        return e, _hours_between(start, e)
    if not (h or e):
        raise HTTPException(400, "Either 'hours' or 'end_time' is required")
    return e, h


def _resolve_booking_sport(body_sport: Optional[str], listing_sports: list) -> Optional[str]:
    if body_sport and body_sport in listing_sports:
        return body_sport
    return listing_sports[0] if listing_sports else None


@api.post("/vendor-bookings", response_model=VendorBooking)
async def request_vendor_booking(body: VendorBookingRequest, user: dict = Depends(require_company_admin)):
    listing = await db.vendor_listings.find_one({"id": body.listing_id, "approved": True, "active": True}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not available")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})

    end_time, hours = _normalize_booking_time(body.start_time, body.end_time, body.hours)
    price = float(listing["price"])
    sport = _resolve_booking_sport(body.sport, listing.get("sports") or [])

    booking = VendorBooking(
        listing_id=listing["id"], listing_title=listing["title"],
        vendor_id=listing["vendor_id"], vendor_type=listing["vendor_type"],
        company_id=user["company_id"], company_name=(company or {}).get("name", ""),
        requested_date=body.requested_date, start_time=body.start_time, end_time=end_time,
        hours=hours, sport=sport, city=listing.get("city"), sub_unit_id=body.sub_unit_id,
        price=price, currency=listing.get("currency", "INR"), total=price * hours,
        notes=body.notes or "", created_by=user["id"], hr_email=user.get("email"),
    )
    payload = booking.model_dump()
    payload["notifications"] = [_booking_notification(
        "created",
        f"Request submitted for {listing['title']} on {body.requested_date} {body.start_time} ({hours}h).",
        user,
    )]
    await db.vendor_bookings.insert_one(payload)
    logger.warning(
        "BOOKING NOTIFICATION for %s | booking=%s | created — Request submitted for %s on %s %s (%sh).",
        user.get("email"), booking.id, listing["title"], body.requested_date, body.start_time, hours,
    )
    return VendorBooking(**payload)


@api.get("/vendor-bookings", response_model=List[VendorBooking])
async def list_vendor_bookings(user: dict = Depends(get_current_user)):
    role = user.get("role")
    if role == "vendor":
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        flt = {"vendor_id": vendor["id"]} if vendor else {"vendor_id": "__none__"}
    elif role == "company_admin":
        flt = {"company_id": user.get("company_id")}
    elif role in ("platform_admin", "admin"):
        flt = {}
    else:
        raise HTTPException(403, "Forbidden")
    docs = await db.vendor_bookings.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [VendorBooking(**d) for d in docs]


VENDOR_STATUSES = {"vendor_accepted", "vendor_declined"}
ADMIN_STATUSES = {"confirmed", "rejected"}
HR_STATUSES = {"cancelled"}
TERMINAL_STATUSES = {"confirmed", "rejected", "cancelled"}


async def _vendor_changes(doc: dict, user: dict, new_status: Optional[str]) -> dict:
    vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
    if not vendor or doc["vendor_id"] != vendor["id"]:
        raise HTTPException(403)
    if doc.get("status") in TERMINAL_STATUSES:
        raise HTTPException(409, f"Booking is already {doc['status']}; only Kreeda Nation admin can change it.")
    # Backward compat: legacy "confirmed"/"declined" → vendor_accepted/vendor_declined
    compat = {"confirmed": "vendor_accepted", "declined": "vendor_declined"}
    mapped = compat.get(new_status, new_status)
    return {"status": mapped} if mapped in VENDOR_STATUSES else {}


def _hr_changes(doc: dict, user: dict, new_status: Optional[str]) -> dict:
    if doc["company_id"] != user.get("company_id"):
        raise HTTPException(403)
    if new_status == "cancelled" and doc.get("status") not in ("cancelled", "rejected"):
        return {"status": "cancelled"}
    return {}


def _admin_changes(new_status: Optional[str], admin_notes) -> dict:
    out: dict = {}
    if new_status in (VENDOR_STATUSES | ADMIN_STATUSES | HR_STATUSES):
        out["status"] = new_status
    if admin_notes is not None:
        out["admin_notes"] = admin_notes
    return out


@api.patch("/vendor-bookings/{booking_id}", response_model=VendorBooking)
async def update_vendor_booking(booking_id: str, body: dict, user: dict = Depends(get_current_user)):
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    role = user.get("role")
    new_status = body.get("status")
    admin_notes = body.get("admin_notes")

    if role == "vendor":
        allowed = await _vendor_changes(doc, user, new_status)
    elif role == "company_admin":
        allowed = _hr_changes(doc, user, new_status)
    elif role in ("platform_admin", "admin"):
        allowed = _admin_changes(new_status, admin_notes)
    else:
        raise HTTPException(403)

    if not allowed:
        raise HTTPException(400, "No allowed changes")

    await db.vendor_bookings.update_one({"id": booking_id}, {"$set": allowed})
    if "status" in allowed and allowed["status"] != doc.get("status"):
        msg = f"Status changed from '{doc.get('status')}' to '{allowed['status']}'"
        if admin_notes:
            msg += f" — note: {admin_notes}"
        await _log_booking_change(doc, "status_change", msg, user)
    updated = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    return VendorBooking(**updated)


# ---------- Cancellation & Refund ----------
def _hours_until_slot(date: str, start_time: str) -> float:
    """Return float hours from now until the booking's slot starts. Negative = already past."""
    try:
        # Treat slot as IST naive then compare against UTC-now for now (mock-grade).
        slot_dt = datetime.fromisoformat(f"{date}T{start_time}:00")
    except Exception:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (slot_dt - now).total_seconds() / 3600


def _calc_refund(booking: dict, listing: dict) -> tuple:
    """Return (refund_amount, reason). Uses listing.cancellation_policy or defaults if unset."""
    pol = (listing or {}).get("cancellation_policy") or {}
    full_h = int(pol.get("full_refund_hours_before", 24))
    part_h = int(pol.get("partial_refund_hours_before", 6))
    part_pct = int(pol.get("partial_refund_percent", 50))
    no_h = int(pol.get("no_refund_window_hours", 2))
    hrs = _hours_until_slot(booking["requested_date"], booking["start_time"])
    total = float(booking.get("total") or booking.get("price") or 0)
    if hrs >= full_h:
        return total, f"Full refund — cancelled {round(hrs)}h before slot (policy: ≥{full_h}h)"
    if hrs >= part_h:
        return round(total * part_pct / 100, 2), f"Partial refund {part_pct}% — cancelled {round(hrs)}h before slot"
    if hrs >= no_h:
        return 0, f"No refund — cancelled inside the {no_h}h–{part_h}h window"
    return 0, "No refund — cancelled within the no-refund window or after slot start"


@api.post("/vendor-bookings/{booking_id}/cancel", response_model=VendorBooking)
async def cancel_vendor_booking(booking_id: str, body: dict, user: dict = Depends(get_current_user)):
    """HR / Platform Admin can cancel a booking. Refund is auto-calculated from the listing policy."""
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    role = user.get("role")
    # HR can cancel only their company's bookings; admins all
    if role == "company_admin" and doc.get("company_id") != user.get("company_id"):
        raise HTTPException(403, "Not your booking")
    if role not in ("company_admin", "platform_admin", "admin"):
        raise HTTPException(403, "Cancellation not allowed for this role")
    if doc.get("status") in ("cancelled", "declined"):
        raise HTTPException(400, "Already cancelled or declined")

    listing = await db.vendor_listings.find_one({"id": doc["listing_id"]}, {"_id": 0}) or {}
    refund, reason = _calc_refund(doc, listing)
    when = datetime.now(timezone.utc).isoformat()
    upd = {
        "status": "cancelled",
        "cancelled_at": when,
        "refund_amount": refund,
        "refund_reason": reason,
    }
    if body.get("notes"):
        upd["admin_notes"] = (doc.get("admin_notes") or "") + f"\n[Cancel] {body['notes']}"
    await db.vendor_bookings.update_one({"id": booking_id}, {"$set": upd})

    # Notify both sides (mocked email + history)
    summary = f"Booking on {doc['requested_date']} {doc['start_time']} cancelled. Refund: {doc.get('currency','INR')} {refund} — {reason}"
    await _log_booking_change({**doc, **upd}, "cancelled_hr", summary, user, email_to=doc.get("hr_email"))
    vendor_user = await db.users.find_one({"vendor_id": doc.get("vendor_id"), "role": "vendor"}, {"_id": 0, "email": 1}) or {}
    if vendor_user.get("email"):
        send_email(vendor_user["email"], f"Booking cancelled — {doc.get('listing_title')}", summary, kind="booking_cancelled_vendor")

    updated = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    return VendorBooking(**updated)


@api.post("/vendor-bookings/{booking_id}/reschedule", response_model=VendorBooking)
async def reschedule_vendor_booking(booking_id: str, body: dict, user: dict = Depends(get_current_user)):
    """HR / Platform Admin can request a reschedule. Validates against listing reschedule_policy."""
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    role = user.get("role")
    if role == "company_admin" and doc.get("company_id") != user.get("company_id"):
        raise HTTPException(403, "Not your booking")
    if role not in ("company_admin", "platform_admin", "admin"):
        raise HTTPException(403, "Reschedule not allowed for this role")
    if doc.get("status") in ("cancelled", "declined", "completed"):
        raise HTTPException(400, "Booking cannot be rescheduled in its current state")

    new_date = (body.get("requested_date") or "").strip()
    new_start = (body.get("start_time") or "").strip()
    hours_arg = body.get("hours") or doc.get("hours") or 1
    if not (new_date and new_start):
        raise HTTPException(400, "requested_date and start_time are required")

    listing = await db.vendor_listings.find_one({"id": doc["listing_id"]}, {"_id": 0}) or {}
    pol = listing.get("reschedule_policy") or {}
    max_resched = int(pol.get("max_reschedules", 2))
    free_hrs = int(pol.get("free_reschedule_hours_before", 24))
    fee = float(pol.get("fee_amount", 0))

    if doc.get("reschedule_count", 0) >= max_resched:
        raise HTTPException(400, f"Reschedule limit reached ({max_resched})")

    hrs_to_orig = _hours_until_slot(doc["requested_date"], doc["start_time"])
    applied_fee = 0.0 if hrs_to_orig >= free_hrs else fee

    new_end, new_h = _normalize_booking_time(new_start, body.get("end_time"), hours_arg)
    upd = {
        "requested_date": new_date,
        "start_time": new_start,
        "end_time": new_end,
        "hours": new_h,
        "reschedule_count": doc.get("reschedule_count", 0) + 1,
    }
    # Push previous slot to history and apply upd
    await db.vendor_bookings.update_one(
        {"id": booking_id},
        {"$set": upd, "$push": {"previous_slots": {
            "requested_date": doc["requested_date"],
            "start_time": doc["start_time"],
            "end_time": doc["end_time"],
            "rescheduled_at": datetime.now(timezone.utc).isoformat(),
            "rescheduled_by": user.get("email"),
            "fee_charged": applied_fee,
        }}},
    )

    summary = (
        f"Rescheduled from {doc['requested_date']} {doc['start_time']} to {new_date} {new_start} "
        f"({new_h}h). Reschedule fee: {doc.get('currency','INR')} {applied_fee}"
    )
    await _log_booking_change({**doc, **upd}, "rescheduled", summary, user, email_to=doc.get("hr_email"))
    vendor_user = await db.users.find_one({"vendor_id": doc.get("vendor_id"), "role": "vendor"}, {"_id": 0, "email": 1}) or {}
    if vendor_user.get("email"):
        send_email(vendor_user["email"], f"Booking rescheduled — {doc.get('listing_title')}", summary, kind="booking_rescheduled_vendor")

    updated = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    return VendorBooking(**updated)


# ---------- Stats ----------
@api.get("/stats")
async def get_stats():
    return {
        "events": await db.events.count_documents({}),
        "teams": await db.teams.count_documents({}),
        "players": await db.players.count_documents({}),
        "fixtures": await db.fixtures.count_documents({}),
        "live": await db.fixtures.count_documents({"status": "live"}),
        "sponsors": await db.sponsors.count_documents({}),
        "services": await db.services.count_documents({"active": True}),
        "companies": await db.companies.count_documents({}),
        "bookings": await db.bookings.count_documents({}),
    }


@api.get("/stats/company")
async def get_company_stats(user: dict = Depends(require_company_admin)):
    cid = user.get("company_id")
    event_ids = [d["id"] for d in await db.events.find({"company_id": cid}, {"_id": 0, "id": 1}).to_list(500)]
    team_ids = [d["id"] for d in await db.teams.find({"event_id": {"$in": event_ids}}, {"_id": 0, "id": 1}).to_list(500)]
    return {
        "events": len(event_ids),
        "teams": len(team_ids),
        "players": await db.players.count_documents({"team_id": {"$in": team_ids}}),
        "fixtures": await db.fixtures.count_documents({"event_id": {"$in": event_ids}}),
        "live": await db.fixtures.count_documents({"event_id": {"$in": event_ids}, "status": "live"}),
        "bookings": await db.bookings.count_documents({"company_id": cid}),
        "pending_bookings": await db.bookings.count_documents({"company_id": cid, "status": "pending"}),
    }


@api.get("/")
async def root():
    return {"name": "Kreeda Nation API", "tagline": "Where Teams Compete, Connect & Grow"}


# Uploads (define route + mount BEFORE including router)
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@api.post("/upload")
async def upload_image(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload an image; returns a public URL on /api/uploads/<filename>."""
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Only JPEG, PNG, WEBP or GIF images allowed")
    ext = (file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg").lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"
    name = f"{uuid.uuid4().hex}.{ext}"
    dest = UPLOAD_DIR / name
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 5 MB)")
    dest.write_bytes(contents)
    return {"url": f"/api/uploads/{name}", "filename": name, "size": len(contents)}


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("playsphere")


async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@kreedanation.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    # One-time migration: rename legacy @playsphere.com → @kreedanation.com when target is free
    legacy_admin = "admin@playsphere.com"
    if admin_email != legacy_admin:
        if await db.users.find_one({"email": legacy_admin}) and not await db.users.find_one({"email": admin_email}):
            await db.users.update_one({"email": legacy_admin}, {"$set": {"email": admin_email}})
            logger.info(f"Migrated platform admin email: {legacy_admin} -> {admin_email}")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "Kreeda Nation Admin",
            "role": "platform_admin",
            "company_id": None,
            "password_hash": hash_password(admin_password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Seeded platform admin: {admin_email}")
    else:
        # ensure role, password, name are all correct
        updates = {}
        if existing.get("role") not in ("platform_admin",):
            updates["role"] = "platform_admin"
        if not verify_password(admin_password, existing["password_hash"]):
            updates["password_hash"] = hash_password(admin_password)
        if existing.get("name") in ("PlaySphere Admin", "PLAYSPHERE Admin"):
            updates["name"] = "Kreeda Nation Admin"
        if updates:
            await db.users.update_one({"email": admin_email}, {"$set": updates})

    viewer_email = "viewer@kreedanation.com"
    # Migrate legacy viewer
    if await db.users.find_one({"email": "viewer@playsphere.com"}) and not await db.users.find_one({"email": viewer_email}):
        await db.users.update_one({"email": "viewer@playsphere.com"}, {"$set": {"email": viewer_email}})
        logger.info(f"Migrated viewer email: viewer@playsphere.com -> {viewer_email}")
    viewer = await db.users.find_one({"email": viewer_email})
    if not viewer:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": viewer_email,
            "name": "Viewer",
            "role": "viewer",
            "company_id": None,
            "password_hash": hash_password("viewer123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


async def _seed_demo_sponsors():
    """Top up the 4 demo banner sponsors if missing (idempotent)."""
    demo = [
        {"name": "Mercedes-Benz", "tier": "title", "website": "https://mercedes-benz.com", "description": "Driving excellence"},
        {"name": "Coca-Cola", "tier": "gold", "website": "https://coca-cola.com", "description": "Refreshing every game"},
        {"name": "Northwind Energy", "tier": "silver", "website": "#", "description": "Powering performance"},
        {"name": "Vertex Labs", "tier": "bronze", "website": "#", "description": "Tech accelerator"},
    ]
    for s in demo:
        if not await db.sponsors.find_one({"name": s["name"], "event_id": None}):
            await db.sponsors.insert_one({
                "id": str(uuid.uuid4()),
                "name": s["name"], "tier": s["tier"], "logo_url": "",
                "website": s["website"], "show_in_banner": True,
                "description": s["description"], "event_id": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })


async def seed_demo_data():
    await _seed_demo_sponsors()
    if await db.events.count_documents({}) > 0:
        return
    # Demo company (Acme Corp) with company_admin user
    acme_owner_id = str(uuid.uuid4())
    acme = Company(
        name="Acme Corp", slug="acme-corp",
        logo_url="",
        contact_email="acme@example.com",
        contact_phone="+1 415 555 0100",
        owner_user_id=acme_owner_id,
    )
    await db.companies.insert_one(acme.model_dump())
    if not await db.users.find_one({"email": "acme@example.com"}):
        await db.users.insert_one({
            "id": acme_owner_id,
            "email": "acme@example.com",
            "name": "Acme HR",
            "role": "company_admin",
            "company_id": acme.id,
            "password_hash": hash_password("acme123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Demo sponsors
    sponsors = [
        {"name": "Mercedes-Benz", "tier": "title", "logo_url": "https://images.unsplash.com/photo-1644166186783-35d911470ff0?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Nzd8MHwxfHNlYXJjaHwxfHxicmFuZCUyMGxvZ28lMjB3aGl0ZSUyMGJhY2tncm91bmR8ZW58MHx8fHwxNzgxMjU1NjE0fDA&ixlib=rb-4.1.0&q=85", "website": "https://mercedes-benz.com", "show_in_banner": True, "description": "Driving excellence"},
        {"name": "Coca-Cola", "tier": "gold", "logo_url": "https://images.unsplash.com/photo-1700887938966-01f0450aee8c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Nzd8MHwxfHNlYXJjaHwzfHxicmFuZCUyMGxvZ28lMjB3aGl0ZSUyMGJhY2tncm91bmR8ZW58MHx8fHwxNzgxMjU1NjE0fDA&ixlib=rb-4.1.0&q=85", "website": "https://coca-cola.com", "show_in_banner": True, "description": "Refreshing every game"},
        {"name": "Northwind Energy", "tier": "silver", "logo_url": "https://images.unsplash.com/photo-1644166186783-35d911470ff0?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Nzd8MHwxfHNlYXJjaHwxfHxicmFuZCUyMGxvZ28lMjB3aGl0ZSUyMGJhY2tncm91bmR8ZW58MHx8fHwxNzgxMjU1NjE0fDA&ixlib=rb-4.1.0&q=85", "website": "#", "show_in_banner": True, "description": "Powering performance"},
        {"name": "Vertex Labs", "tier": "bronze", "logo_url": "https://images.unsplash.com/photo-1700887938966-01f0450aee8c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Nzd8MHwxfHNlYXJjaHwzfHxicmFuZCUyMGxvZ28lMjB3aGl0ZSUyMGJhY2tncm91bmR8ZW58MHx8fHwxNzgxMjU1NjE0fDA&ixlib=rb-4.1.0&q=85", "website": "#", "show_in_banner": True, "description": "Tech accelerator"},
    ]
    for s in sponsors:
        sp = Sponsor(**s)
        await db.sponsors.insert_one(sp.model_dump())

    # Demo event
    ev = Event(
        name="Spring Championship 2026",
        sport="football",
        description="The flagship inter-department football tournament.",
        format="round_robin",
        venue="Central Sports Ground",
        status="ongoing",
        banner_url="https://images.pexels.com/photos/1657324/pexels-photo-1657324.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        company_id=acme.id,
    )
    await db.events.insert_one(ev.model_dump())

    team_data = [
        ("Engineering Eagles", "Engineering", "#007AFF"),
        ("Design Dragons", "Design", "#FF3B30"),
        ("Marketing Mavericks", "Marketing", "#10B981"),
        ("Sales Spartans", "Sales", "#F59E0B"),
    ]
    team_ids = []
    for name, dept, color in team_data:
        t = Team(name=name, department=dept, color=color, event_id=ev.id, captain=f"{dept} Lead")
        await db.teams.insert_one(t.model_dump())
        team_ids.append(t.id)

    players_per_team = [
        ["Alex Rivera", "Jordan Pak", "Sam Quinn", "Taylor Brooks"],
        ["Morgan Lee", "Casey Stone", "Riley Cruz", "Avery Ng"],
        ["Drew Mason", "Skylar Vega", "Reese Kim", "Hayden Cole"],
        ["Quinn Hart", "Logan Diaz", "Parker Yoo", "Emery Singh"],
    ]
    for tid, names in zip(team_ids, players_per_team):
        for i, n in enumerate(names):
            p = Player(name=n, team_id=tid, role=["Captain", "Striker", "Midfielder", "Defender"][i],
                       jersey_number=i + 7,
                       avatar_url="https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940")
            await db.players.insert_one(p.model_dump())

    # Generate round robin fixtures
    fixtures = generate_round_robin(team_ids, ev.id)
    # mark a few completed and one live
    if fixtures:
        fixtures[0]["status"] = "completed"
        fixtures[0]["winner_id"] = team_ids[0]
        fixtures[0]["score"] = {"team_a": {"goals": 3}, "team_b": {"goals": 1}}
        fixtures[1]["status"] = "completed"
        fixtures[1]["winner_id"] = team_ids[2]
        fixtures[1]["score"] = {"team_a": {"goals": 2}, "team_b": {"goals": 0}}
        if len(fixtures) > 2:
            fixtures[2]["status"] = "live"
            fixtures[2]["score"] = {"team_a": {"goals": 1}, "team_b": {"goals": 1}}
        await db.fixtures.insert_many(fixtures)

    # second event: cricket knockout
    ev2 = Event(
        name="T10 Corporate Cricket Cup",
        sport="cricket",
        description="Fast-paced T10 cricket knockout.",
        format="knockout",
        venue="Oval Ground",
        status="upcoming",
        banner_url="https://images.pexels.com/photos/15779126/pexels-photo-15779126.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        company_id=acme.id,
    )
    await db.events.insert_one(ev2.model_dump())

    # third event: non-sport
    ev3 = Event(
        name="Tech Quiz Bowl",
        sport="quiz",
        description="Battle of department brains across three rounds.",
        format="knockout",
        venue="Auditorium A",
        status="upcoming",
        banner_url="https://images.unsplash.com/photo-1774599661395-569eea1420e3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzNTl8MHwxfHNlYXJjaHwzfHxjb3Jwb3JhdGUlMjBzcG9ydHMlMjBldmVudHxlbnwwfHx8fDE3ODEyNTU2MTR8MA&ixlib=rb-4.1.0&q=85",
        company_id=acme.id,
    )
    await db.events.insert_one(ev3.model_dump())


async def seed_services():
    services = [
        {
            "name": "Live YouTube Streaming",
            "category": "streaming",
            "description": "Multi-camera live broadcast on YouTube with on-screen scoreboard, replays and commentary.",
            "images": ["https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?w=900"],
            "base_price": 499.0,
            "currency": "USD",
            "price_unit": "per match",
            "config_fields": [
                {"key": "cameras", "label": "Number of cameras", "type": "number", "min": 1, "max": 8, "default": "2", "required": True},
                {"key": "umpires_mic", "label": "Number of umpires (mic-up)", "type": "number", "min": 0, "max": 6, "default": "2"},
                {"key": "commentary", "label": "Commentary language", "type": "select", "options": ["English", "Hindi", "Spanish", "None"], "default": "English"},
                {"key": "match_duration_hours", "label": "Match duration (hours)", "type": "number", "min": 1, "max": 12, "default": "3"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "YouTube channel link / Stream title",
        },
        {
            "name": "Team Jerseys",
            "category": "apparel",
            "description": "Premium dry-fit team jerseys, fully customisable with team name, sponsor logos and player numbers.",
            "images": ["https://images.unsplash.com/photo-1556906781-9a412961c28c?w=900"],
            "base_price": 22.0,
            "currency": "USD",
            "price_unit": "per piece",
            "config_fields": [
                {"key": "size_mix", "label": "Size mix (e.g., 4S, 6M, 5L, 1XL)", "type": "text", "required": True},
                {"key": "fabric", "label": "Fabric", "type": "select", "options": ["Polyester Dri-Fit", "Cotton Blend", "Premium Mesh"], "default": "Polyester Dri-Fit"},
            ],
            "variants": [
                {"id": "jersey-v1", "name": "Classic Stripe", "image_url": "https://images.unsplash.com/photo-1521577352947-9bb58764b69a?w=600", "extra_price": 0.0},
                {"id": "jersey-v2", "name": "Modern Gradient", "image_url": "https://images.unsplash.com/photo-1517466787929-bc90951d0974?w=600", "extra_price": 4.0},
                {"id": "jersey-v3", "name": "Retro Block", "image_url": "https://images.unsplash.com/photo-1556906781-c9c0a0bea1aa?w=600", "extra_price": 2.5},
            ],
            "allow_custom_text": True, "custom_text_label": "Team name + sponsor text to print",
        },
        {
            "name": "Branded Caps",
            "category": "apparel",
            "description": "Embroidered team caps; available in snapback, baseball and bucket styles.",
            "images": ["https://images.unsplash.com/photo-1521369909029-2afed882baee?w=900"],
            "base_price": 9.0,
            "currency": "USD",
            "price_unit": "per piece",
            "config_fields": [
                {"key": "quantity_breakdown", "label": "Color split (e.g., 20 black / 10 white)", "type": "text"},
            ],
            "variants": [
                {"id": "cap-snap", "name": "Snapback", "image_url": "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?w=600", "extra_price": 0.0},
                {"id": "cap-base", "name": "Baseball", "image_url": "https://images.unsplash.com/photo-1521369909029-2afed882baee?w=600", "extra_price": 1.0},
                {"id": "cap-buck", "name": "Bucket", "image_url": "https://images.unsplash.com/photo-1572307480813-ceb0e59d8325?w=600", "extra_price": 1.5},
            ],
            "allow_custom_text": True, "custom_text_label": "Embroidery text (e.g., team initials)",
        },
        {
            "name": "Trophies & Awards",
            "category": "awards",
            "description": "Premium engraved trophies for tournament winners, runner-up and individual awards.",
            "images": ["https://images.unsplash.com/photo-1567427361984-0cbe7396fc6c?w=900"],
            "base_price": 35.0,
            "currency": "USD",
            "price_unit": "per trophy",
            "config_fields": [
                {"key": "height_inches", "label": "Height (inches)", "type": "number", "min": 6, "max": 24, "default": "10"},
            ],
            "variants": [
                {"id": "trophy-gold", "name": "Golden Cup", "image_url": "https://images.unsplash.com/photo-1564607220646-a0d8e988a2e1?w=600", "extra_price": 0.0},
                {"id": "trophy-crystal", "name": "Crystal Star", "image_url": "https://images.unsplash.com/photo-1606925797300-0b35e9d1794e?w=600", "extra_price": 18.0},
                {"id": "trophy-silver", "name": "Silver Shield", "image_url": "https://images.unsplash.com/photo-1567427361984-0cbe7396fc6c?w=600", "extra_price": 8.0},
                {"id": "trophy-medal", "name": "Medal & Ribbon", "image_url": "https://images.unsplash.com/photo-1518091093578-ca38ba0c9b8c?w=600", "extra_price": -20.0},
            ],
            "allow_custom_text": True, "custom_text_label": "Inscription (e.g., Best Batsman — Spring Cup 2026)",
        },
        {
            "name": "Ground Booking",
            "category": "venue",
            "description": "Reserve premium grounds and indoor arenas: cricket, football, badminton courts, basketball.",
            "images": ["https://images.unsplash.com/photo-1459865264687-595d652de67e?w=900"],
            "base_price": 250.0,
            "currency": "USD",
            "price_unit": "per hour",
            "config_fields": [
                {"key": "sport", "label": "Sport / surface", "type": "select", "options": ["Cricket", "Football", "Badminton", "Tennis", "Basketball", "Volleyball"], "required": True},
                {"key": "hours", "label": "Hours required", "type": "number", "min": 1, "max": 12, "default": "4", "required": True},
                {"key": "preferred_date", "label": "Preferred date (YYYY-MM-DD)", "type": "text"},
                {"key": "city", "label": "City / area", "type": "text"},
            ],
            "variants": [],
            "allow_custom_text": False,
        },
        {
            "name": "Match Instruments",
            "category": "equipment",
            "description": "Rental equipment kit: cricket bats, balls, footballs, badminton rackets, scoreboards, stumps.",
            "images": ["https://images.unsplash.com/photo-1531415074968-036ba1b575da?w=900"],
            "base_price": 80.0,
            "currency": "USD",
            "price_unit": "per kit / day",
            "config_fields": [
                {"key": "kit_for", "label": "Kit for", "type": "select", "options": ["Cricket", "Football", "Badminton", "Basketball", "Volleyball", "Mixed"], "required": True},
                {"key": "balls_count", "label": "Match balls required", "type": "number", "min": 0, "max": 50, "default": "6"},
                {"key": "scoreboard", "label": "Manual scoreboard", "type": "select", "options": ["Yes", "No"], "default": "Yes"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "Special items / notes",
        },
        {
            "name": "Training Kits",
            "category": "training",
            "description": "Pre-tournament conditioning & drills kits: cones, hurdles, agility ladders, coaches on rental.",
            "images": ["https://images.unsplash.com/photo-1517649763962-0c623066013b?w=900"],
            "base_price": 120.0,
            "currency": "USD",
            "price_unit": "per session",
            "config_fields": [
                {"key": "sessions", "label": "Number of sessions", "type": "number", "min": 1, "max": 30, "default": "4", "required": True},
                {"key": "with_coach", "label": "Include certified coach", "type": "select", "options": ["Yes", "No"], "default": "Yes"},
                {"key": "team_size", "label": "Approx team size", "type": "number", "default": "15"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "Focus areas (e.g., fitness, batting, bowling)",
        },
        # ---- New services (event lifecycle add-ons) ----
        {
            "name": "Professional Photography",
            "category": "other",
            "description": "DSLR match-day photography with edited gallery delivered within 48 hours.",
            "images": ["https://images.unsplash.com/photo-1542038784456-1ea8e935640e?w=900"],
            "base_price": 199.0,
            "currency": "USD",
            "price_unit": "per session",
            "config_fields": [
                {"key": "photographers", "label": "Number of photographers", "type": "number", "min": 1, "max": 6, "default": "1", "required": True},
                {"key": "hours", "label": "Coverage hours", "type": "number", "min": 1, "max": 12, "default": "4"},
                {"key": "deliverable", "label": "Deliverable", "type": "select", "options": ["Online gallery (200+ photos)", "Album + soft copies", "Printed photo book"], "default": "Online gallery (200+ photos)"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "Mood / shot list (e.g., team huddles, candids)",
        },
        {
            "name": "Videography & Highlights Reel",
            "category": "other",
            "description": "Edited cinematic highlights reel plus full match recording, broadcast-quality.",
            "images": ["https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?w=900"],
            "base_price": 349.0,
            "currency": "USD",
            "price_unit": "per match",
            "config_fields": [
                {"key": "cameras", "label": "Number of cameras", "type": "number", "min": 1, "max": 4, "default": "2"},
                {"key": "reel_length_minutes", "label": "Highlights length (minutes)", "type": "number", "min": 1, "max": 10, "default": "3"},
                {"key": "voiceover", "label": "Voice-over commentary", "type": "select", "options": ["Yes", "No"], "default": "Yes"},
                {"key": "turnaround", "label": "Turnaround", "type": "select", "options": ["48 hours", "1 week", "2 weeks"], "default": "1 week"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "Music preference / theme",
        },
        {
            "name": "Drone Aerial Coverage",
            "category": "other",
            "description": "Aerial cinematography with licensed pilots — opening visuals, action loops, sponsor reveals.",
            "images": ["https://images.unsplash.com/photo-1473968512647-3e447244af8f?w=900"],
            "base_price": 299.0,
            "currency": "USD",
            "price_unit": "per event",
            "config_fields": [
                {"key": "duration_hours", "label": "Flight time (hours)", "type": "number", "min": 1, "max": 8, "default": "2", "required": True},
                {"key": "footage_format", "label": "Footage", "type": "select", "options": ["4K", "1080p", "Both"], "default": "4K"},
                {"key": "venue_type", "label": "Venue type", "type": "select", "options": ["Open ground", "Stadium", "Indoor (NA)"], "default": "Open ground"},
            ],
            "variants": [],
            "allow_custom_text": False,
        },
        {
            "name": "Anchor / MC",
            "category": "other",
            "description": "Professional emcee to host opening, breaks and prize ceremony — energise the crowd.",
            "images": ["https://images.unsplash.com/photo-1531058020387-3be344556be6?w=900"],
            "base_price": 12000.0,
            "currency": "INR",
            "price_unit": "per event",
            "config_fields": [
                {"key": "language", "label": "Language", "type": "select", "options": ["English", "Hindi", "Bilingual", "Other"], "default": "Bilingual", "required": True},
                {"key": "hours", "label": "Hours required", "type": "number", "min": 1, "max": 10, "default": "4"},
                {"key": "experience_level", "label": "Experience level", "type": "select", "options": ["Junior", "Senior", "Celebrity"], "default": "Senior"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "Script highlights / sponsor mentions",
        },
        {
            "name": "DJ & Sound System",
            "category": "equipment",
            "description": "DJ + PA system + speakers + wireless mics for tournament announcements and player walk-outs.",
            "images": ["https://images.unsplash.com/photo-1571266028243-d220c6a89a36?w=900"],
            "base_price": 18000.0,
            "currency": "INR",
            "price_unit": "per day",
            "config_fields": [
                {"key": "venue_size", "label": "Venue size", "type": "select", "options": ["Small (<100 ppl)", "Medium (100-500)", "Large (500+)"], "default": "Medium (100-500)"},
                {"key": "wireless_mics", "label": "Wireless mics", "type": "number", "min": 1, "max": 10, "default": "2"},
                {"key": "dj_required", "label": "DJ included", "type": "select", "options": ["Yes", "No (sound only)"], "default": "Yes"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "Genre / playlist preferences",
        },
        {
            "name": "Catering & Refreshments",
            "category": "other",
            "description": "Match-day meals, snacks, hydration stations for players and audience.",
            "images": ["https://images.unsplash.com/photo-1555244162-803834f70033?w=900"],
            "base_price": 350.0,
            "currency": "INR",
            "price_unit": "per head",
            "config_fields": [
                {"key": "headcount", "label": "Total headcount", "type": "number", "min": 10, "max": 5000, "default": "50", "required": True},
                {"key": "meal_type", "label": "Meal type", "type": "select", "options": ["Snacks only", "Lunch", "Lunch + snacks", "Full day"], "default": "Lunch + snacks"},
                {"key": "preference", "label": "Cuisine", "type": "select", "options": ["Veg only", "Veg + Non-veg", "Vegan", "Indian", "Continental", "Mixed"], "default": "Veg + Non-veg"},
                {"key": "hydration", "label": "Hydration station", "type": "select", "options": ["Yes", "No"], "default": "Yes"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "Allergies / dietary notes",
        },
        {
            "name": "Custom Medals",
            "category": "awards",
            "description": "Gold / silver / bronze medals with custom ribbons and engraving — ideal for top 3 across categories.",
            "images": ["https://images.unsplash.com/photo-1564307713687-d0e1c9c9ef76?w=900"],
            "base_price": 8.0,
            "currency": "USD",
            "price_unit": "per medal",
            "config_fields": [
                {"key": "diameter_mm", "label": "Diameter (mm)", "type": "number", "min": 40, "max": 100, "default": "60"},
                {"key": "ribbon_color", "label": "Ribbon color", "type": "text", "default": "Blue"},
            ],
            "variants": [
                {"id": "medal-gold", "name": "Gold finish", "image_url": "https://images.unsplash.com/photo-1567427361984-0cbe7396fc6c?w=600", "extra_price": 0.0},
                {"id": "medal-silver", "name": "Silver finish", "image_url": "https://images.unsplash.com/photo-1503602642458-232111445657?w=600", "extra_price": -2.0},
                {"id": "medal-bronze", "name": "Bronze finish", "image_url": "https://images.unsplash.com/photo-1571388208497-71bedc66e932?w=600", "extra_price": -3.0},
            ],
            "allow_custom_text": True, "custom_text_label": "Engraving (e.g., '1st Place — Spring Cup 2026')",
        },
        {
            "name": "Banners & Venue Branding",
            "category": "merchandise",
            "description": "Flex banners, standees, sponsor backdrops, finish-line tapes — high-resolution print.",
            "images": ["https://images.unsplash.com/photo-1568288860824-b7c7c45ee83b?w=900"],
            "base_price": 1500.0,
            "currency": "INR",
            "price_unit": "per piece",
            "config_fields": [
                {"key": "size", "label": "Size (W × H ft)", "type": "text", "default": "8 × 4", "required": True},
                {"key": "material", "label": "Material", "type": "select", "options": ["Flex (outdoor)", "Vinyl (indoor)", "Fabric (premium)"], "default": "Flex (outdoor)"},
            ],
            "variants": [
                {"id": "banner-flex", "name": "Roll-up Standee", "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=600", "extra_price": 0.0},
                {"id": "banner-back", "name": "Backdrop", "image_url": "https://images.unsplash.com/photo-1607344645866-009c320b63e0?w=600", "extra_price": 800.0},
                {"id": "banner-flag", "name": "Feather Flag", "image_url": "https://images.unsplash.com/photo-1517649763962-0c623066013b?w=600", "extra_price": 300.0},
            ],
            "allow_custom_text": True, "custom_text_label": "Print text / sponsor list",
        },
        {
            "name": "First Aid & Paramedic Stand",
            "category": "other",
            "description": "On-ground first responder + stocked medical kit + ambulance on standby for tournament safety.",
            "images": ["https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=900"],
            "base_price": 150.0,
            "currency": "USD",
            "price_unit": "per day",
            "config_fields": [
                {"key": "paramedics", "label": "Paramedics required", "type": "number", "min": 1, "max": 6, "default": "1", "required": True},
                {"key": "ambulance_standby", "label": "Ambulance on standby", "type": "select", "options": ["Yes", "No"], "default": "Yes"},
                {"key": "hours", "label": "Hours required", "type": "number", "min": 2, "max": 12, "default": "6"},
            ],
            "variants": [],
            "allow_custom_text": False,
        },
        {
            "name": "Match Officials & Umpires",
            "category": "training",
            "description": "Certified umpires, referees and scorekeepers — hire neutral officials for fair play.",
            "images": ["https://images.unsplash.com/photo-1530549387789-4c1017266635?w=900"],
            "base_price": 4500.0,
            "currency": "INR",
            "price_unit": "per match",
            "config_fields": [
                {"key": "sport", "label": "Sport", "type": "select", "options": ["Cricket", "Football", "Badminton", "Basketball", "Volleyball", "Other"], "required": True},
                {"key": "officials_count", "label": "Number of officials", "type": "number", "min": 1, "max": 6, "default": "2", "required": True},
                {"key": "certification", "label": "Certification level", "type": "select", "options": ["State", "National", "International"], "default": "State"},
            ],
            "variants": [],
            "allow_custom_text": False,
        },
    ]
    inserted = 0
    for s in services:
        if not await db.services.find_one({"name": s["name"]}):
            await db.services.insert_one(Service(**s).model_dump())
            inserted += 1
    if inserted:
        logger.info(f"Seeded {inserted} new services (total {len(services)} defined)")


# ---------- Sports CRUD (dynamic list) ----------
DEFAULT_SPORTS = [
    {"value": "cricket", "label": "Cricket"},
    {"value": "football", "label": "Football"},
    {"value": "basketball", "label": "Basketball"},
    {"value": "badminton", "label": "Badminton"},
    {"value": "tabletennis", "label": "Table Tennis"},
    {"value": "volleyball", "label": "Volleyball"},
    {"value": "chess", "label": "Chess"},
    {"value": "quiz", "label": "Quiz"},
    {"value": "hackathon", "label": "Hackathon"},
    {"value": "other", "label": "Other"},
]


async def seed_sports():
    for idx, s in enumerate(DEFAULT_SPORTS):
        existing = await db.sports.find_one({"value": s["value"]})
        if not existing:
            await db.sports.insert_one({
                "id": str(uuid.uuid4()),
                "value": s["value"], "label": s["label"],
                "active": True, "sort_order": idx,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        elif not existing.get("active"):
            await db.sports.update_one({"value": s["value"]}, {"$set": {"active": True}})


@api.get("/sports")
async def list_sports(include_inactive: bool = False):
    flt = {} if include_inactive else {"active": True}
    docs = await db.sports.find(flt, {"_id": 0}).sort("sort_order", 1).to_list(200)
    return docs


@api.post("/sports")
async def create_sport(body: dict, _: dict = Depends(require_platform_admin)):
    value = (body.get("value") or "").strip().lower()
    label = (body.get("label") or "").strip()
    if not (value and label):
        raise HTTPException(400, "value and label required")
    if await db.sports.find_one({"value": value}):
        raise HTTPException(400, "Sport with this value already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "value": value, "label": label, "active": True,
        "sort_order": int(body.get("sort_order", 999)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sports.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.patch("/sports/{sport_id}")
async def update_sport(sport_id: str, body: dict, _: dict = Depends(require_platform_admin)):
    allowed = {k: v for k, v in body.items() if k in ("label", "active", "sort_order")}
    if not allowed:
        raise HTTPException(400, "No allowed fields")
    await db.sports.update_one({"id": sport_id}, {"$set": allowed})
    doc = await db.sports.find_one({"id": sport_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404)
    return doc


@api.delete("/sports/{sport_id}")
async def delete_sport(sport_id: str, _: dict = Depends(require_platform_admin)):
    res = await db.sports.delete_one({"id": sport_id})
    if not res.deleted_count:
        raise HTTPException(404)
    return {"ok": True}


# ---------- Dashboards ----------
@api.get("/dashboard/admin")
async def dashboard_admin(_: dict = Depends(require_platform_admin)):
    return {
        "events_total": await db.events.count_documents({}),
        "events_ongoing": await db.events.count_documents({"status": "ongoing"}),
        "events_upcoming": await db.events.count_documents({"status": "upcoming"}),
        "events_completed": await db.events.count_documents({"status": "completed"}),
        "companies": await db.companies.count_documents({}),
        "vendors_total": await db.vendors.count_documents({}),
        "vendors_pending": await db.vendors.count_documents({"approved": {"$ne": True}}),
        "listings_total": await db.vendor_listings.count_documents({}),
        "listings_pending": await db.vendor_listings.count_documents({"approved": {"$ne": True}}),
        "service_bookings": await db.bookings.count_documents({}),
        "vendor_bookings_total": await db.vendor_bookings.count_documents({}),
        "vendor_bookings_pending": await db.vendor_bookings.count_documents({"status": "pending"}),
        "vendor_bookings_confirmed": await db.vendor_bookings.count_documents({"status": "confirmed"}),
        "players": await db.player_profiles.count_documents({}),
        "teams": await db.teams.count_documents({}),
    }


@api.get("/dashboard/company")
async def dashboard_company(user: dict = Depends(require_company_admin)):
    cid = user.get("company_id")
    if not cid:
        raise HTTPException(400, "Not associated with a company")
    # Events the company owns OR is participating in (inter-company)
    event_filter = {"$or": [{"company_id": cid}, {"companies": cid}]}
    my_events = await db.events.count_documents(event_filter)
    my_event_ids = [d["id"] async for d in db.events.find(event_filter, {"id": 1})]
    return {
        "my_events": my_events,
        "my_events_ongoing": await db.events.count_documents({**event_filter, "status": "ongoing"}),
        "my_events_upcoming": await db.events.count_documents({**event_filter, "status": "upcoming"}),
        "my_events_completed": await db.events.count_documents({**event_filter, "status": "completed"}),
        "my_teams": await db.teams.count_documents({"company_id": cid}),
        "my_matches": await db.fixtures.count_documents({"event_id": {"$in": my_event_ids}}) if my_event_ids else 0,
        "matches_completed": await db.fixtures.count_documents({"event_id": {"$in": my_event_ids}, "status": "completed"}) if my_event_ids else 0,
        "service_bookings": await db.bookings.count_documents({"company_id": cid}),
        "ground_bookings": await db.vendor_bookings.count_documents({"company_id": cid}),
        "ground_bookings_confirmed": await db.vendor_bookings.count_documents({"company_id": cid, "status": "confirmed"}),
        "ground_bookings_pending": await db.vendor_bookings.count_documents({"company_id": cid, "status": "pending"}),
        "players_in_company": await db.player_profiles.count_documents({"company_id": cid}),
    }


@api.get("/dashboard/vendor")
async def dashboard_vendor(user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(403, "Vendors only")
    v = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Vendor profile not found")
    vid = v["id"]
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "listings_total": await db.vendor_listings.count_documents({"vendor_id": vid}),
        "listings_approved": await db.vendor_listings.count_documents({"vendor_id": vid, "approved": True}),
        "listings_pending": await db.vendor_listings.count_documents({"vendor_id": vid, "approved": {"$ne": True}}),
        "bookings_total": await db.vendor_bookings.count_documents({"vendor_id": vid}),
        "bookings_pending": await db.vendor_bookings.count_documents({"vendor_id": vid, "status": "pending"}),
        "bookings_vendor_accepted": await db.vendor_bookings.count_documents({"vendor_id": vid, "status": "vendor_accepted"}),
        "bookings_confirmed": await db.vendor_bookings.count_documents({"vendor_id": vid, "status": "confirmed"}),
        "bookings_completed": await db.vendor_bookings.count_documents({"vendor_id": vid, "status": "confirmed", "requested_date": {"$lt": today}}),
        "bookings_upcoming": await db.vendor_bookings.count_documents({"vendor_id": vid, "status": "confirmed", "requested_date": {"$gte": today}}),
        "bookings_rejected": await db.vendor_bookings.count_documents({"vendor_id": vid, "status": "rejected"}),
        "bookings_cancelled": await db.vendor_bookings.count_documents({"vendor_id": vid, "status": "cancelled"}),
    }


# ---------- Venue sub-units, schedule, blocks (Playo-style) ----------
@api.get("/vendor-listings/{listing_id}/sub-units")
async def list_sub_units(listing_id: str):
    docs = await db.venue_sub_units.find({"listing_id": listing_id}, {"_id": 0}).sort("name", 1).to_list(50)
    return docs


async def _require_vendor_owner(listing_id: str, user: dict) -> dict:
    listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not found")
    if user.get("role") in ("platform_admin", "admin"):
        return listing
    v = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
    if not v or v["id"] != listing.get("vendor_id"):
        raise HTTPException(403, "Not your listing")
    return listing


@api.post("/vendor-listings/{listing_id}/sub-units")
async def create_sub_unit(listing_id: str, body: dict, user: dict = Depends(get_current_user)):
    await _require_vendor_owner(listing_id, user)
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    doc = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "name": name,
        "capacity": int(body.get("capacity") or 0),
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.venue_sub_units.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/vendor-listings/{listing_id}/sub-units/{sub_id}")
async def delete_sub_unit(listing_id: str, sub_id: str, user: dict = Depends(get_current_user)):
    await _require_vendor_owner(listing_id, user)
    res = await db.venue_sub_units.delete_one({"id": sub_id, "listing_id": listing_id})
    if not res.deleted_count:
        raise HTTPException(404)
    return {"ok": True}


@api.get("/vendor-listings/{listing_id}/schedule")
async def get_schedule(listing_id: str):
    doc = await db.venue_schedules.find_one({"listing_id": listing_id}, {"_id": 0})
    if not doc:
        return {
            "listing_id": listing_id,
            "opening_time": "06:00", "closing_time": "22:00",
            "slot_minutes": 60,
            "peak_hours": ["18:00", "19:00", "20:00", "21:00"],
            "peak_price_factor": 1.25,
            "weekend_price_factor": 1.2,
            "happy_hours": [],
            "amenities": [],
        }
    doc.setdefault("happy_hours", [])
    return doc


@api.patch("/vendor-listings/{listing_id}/schedule")
async def update_schedule(listing_id: str, body: dict, user: dict = Depends(get_current_user)):
    await _require_vendor_owner(listing_id, user)
    allowed = {k: body[k] for k in ("opening_time", "closing_time", "slot_minutes", "peak_hours",
                                     "peak_price_factor", "weekend_price_factor", "happy_hours", "amenities") if k in body}
    if not allowed:
        raise HTTPException(400, "no allowed fields")
    # Sanitize happy_hours entries
    if "happy_hours" in allowed:
        cleaned = []
        for hh in allowed["happy_hours"] or []:
            if not isinstance(hh, dict):
                continue
            try:
                cleaned.append({
                    "label": str(hh.get("label") or "Happy Hour")[:40],
                    "days": [int(d) for d in (hh.get("days") or []) if 0 <= int(d) <= 6],
                    "start": str(hh.get("start") or "00:00"),
                    "end": str(hh.get("end") or "00:00"),
                    "factor": max(0.0, float(hh.get("factor") or 1.0)),
                })
            except (TypeError, ValueError):
                continue
        allowed["happy_hours"] = cleaned
    allowed["listing_id"] = listing_id
    await db.venue_schedules.update_one({"listing_id": listing_id}, {"$set": allowed}, upsert=True)
    return await db.venue_schedules.find_one({"listing_id": listing_id}, {"_id": 0})


@api.get("/vendor-listings/{listing_id}/blocks")
async def list_blocks(listing_id: str, date: Optional[str] = None):
    flt = {"listing_id": listing_id}
    if date:
        flt["date"] = date
    docs = await db.venue_blocks.find(flt, {"_id": 0}).sort("date", 1).to_list(200)
    return docs


@api.post("/vendor-listings/{listing_id}/blocks")
async def create_block(listing_id: str, body: dict, user: dict = Depends(get_current_user)):
    await _require_vendor_owner(listing_id, user)
    date = body.get("date") or ""
    start = body.get("start_time") or ""
    end = body.get("end_time") or ""
    if not (date and start and end):
        raise HTTPException(400, "date, start_time, end_time required")
    doc = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "sub_unit_id": body.get("sub_unit_id"),
        "date": date, "start_time": start, "end_time": end,
        "reason": (body.get("reason") or "").strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.venue_blocks.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/vendor-listings/{listing_id}/blocks/{block_id}")
async def delete_block(listing_id: str, block_id: str, user: dict = Depends(get_current_user)):
    await _require_vendor_owner(listing_id, user)
    res = await db.venue_blocks.delete_one({"id": block_id, "listing_id": listing_id})
    if not res.deleted_count:
        raise HTTPException(404)
    return {"ok": True}


def _slots_between(opening: str, closing: str, minutes: int) -> list:
    """Generate slot start times between opening and closing (exclusive end)."""
    try:
        sh, sm = (int(x) for x in opening.split(":")[:2])
        eh, em = (int(x) for x in closing.split(":")[:2])
    except Exception:
        return []
    start = sh * 60 + sm
    end = eh * 60 + em
    slots = []
    cur = start
    while cur + minutes <= end:
        slots.append(f"{cur // 60:02d}:{cur % 60:02d}")
        cur += minutes
    return slots


def _hhmm_to_min(t: str) -> int:
    h, m = (int(x) for x in t.split(":")[:2])
    return h * 60 + m


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return _hhmm_to_min(a_start) < _hhmm_to_min(b_end) and _hhmm_to_min(b_start) < _hhmm_to_min(a_end)


@api.get("/vendor-listings/{listing_id}/availability")
async def listing_availability(listing_id: str, date: str, sub_unit_id: Optional[str] = None):
    listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not found")
    sched = await db.venue_schedules.find_one({"listing_id": listing_id}, {"_id": 0}) or {}
    opening = sched.get("opening_time", "06:00")
    closing = sched.get("closing_time", "22:00")
    minutes = int(sched.get("slot_minutes", 60))
    peak = set(sched.get("peak_hours", []))
    peak_factor = float(sched.get("peak_price_factor", 1.0))
    weekend_factor = float(sched.get("weekend_price_factor", 1.0))
    happy_hours = sched.get("happy_hours", []) or []
    base_price = float(listing.get("price", 0))
    weekday = 0
    try:
        weekday = datetime.fromisoformat(date).weekday()  # 5,6 = Sat,Sun
    except Exception:
        raise HTTPException(400, "Invalid date")
    is_weekend = weekday >= 5

    def _happy_hour_factor_for(slot_hhmm: str) -> Optional[tuple]:
        slot_min = _hhmm_to_min(slot_hhmm)
        for hh in happy_hours:
            days = hh.get("days") or []
            if days and weekday not in days:
                continue
            try:
                if _hhmm_to_min(hh["start"]) <= slot_min < _hhmm_to_min(hh["end"]):
                    return (float(hh.get("factor") or 1.0), hh.get("label") or "Happy Hour")
            except (KeyError, ValueError):
                continue
        return None

    booked = await db.vendor_bookings.find({
        "listing_id": listing_id, "requested_date": date,
        "status": {"$in": ["pending", "vendor_accepted", "confirmed"]},
        **({"sub_unit_id": sub_unit_id} if sub_unit_id else {}),
    }, {"_id": 0, "start_time": 1, "end_time": 1}).to_list(200)
    blocks = await db.venue_blocks.find({
        "listing_id": listing_id, "date": date,
        **({"sub_unit_id": sub_unit_id} if sub_unit_id else {}),
    }, {"_id": 0, "start_time": 1, "end_time": 1, "reason": 1}).to_list(200)

    slots = []
    for s in _slots_between(opening, closing, minutes):
        s_end = _hhmm_add(s, max(1, minutes // 60))
        status = "available"
        for b in booked:
            if _overlaps(s, s_end, b["start_time"], b["end_time"]):
                status = "booked"
                break
        if status == "available":
            for bk in blocks:
                if _overlaps(s, s_end, bk["start_time"], bk["end_time"]):
                    status = "blocked"
                    break
        price = base_price
        hh_label = None
        hh = _happy_hour_factor_for(s)
        if hh is not None:
            # Happy hour wins over weekend/peak pricing
            price *= hh[0]
            hh_label = hh[1]
        elif is_weekend:
            price *= weekend_factor
        elif s in peak:
            price *= peak_factor
        slot = {"time": s, "status": status, "price": round(price, 2)}
        if hh_label:
            slot["happy_hour"] = hh_label
        slots.append(slot)
    return {
        "date": date, "weekday": weekday, "is_weekend": is_weekend,
        "opening_time": opening, "closing_time": closing,
        "slot_minutes": minutes, "currency": listing.get("currency", "INR"),
        "slots": slots,
    }


# Cricket — CricHeroes-style match flow (extracted into routes/cricket.py)
from routes import cricket as cricket_routes  # noqa: E402
cricket_routes.register(api, db, ws_manager, require_admin, propagate_knockout_winner)

# Site settings / About / Contact (extracted into routes/settings.py)
from routes import settings as settings_routes  # noqa: E402
settings_routes.register(api, db, SiteSettings, require_platform_admin)


# Register router + static mount AFTER all @api.x definitions above
app.include_router(api)
app.mount("/api/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.companies.create_index("slug", unique=True)
    await db.teams.create_index("event_id")
    await db.events.create_index("company_id")
    await db.fixtures.create_index("event_id")
    await db.players.create_index("team_id")
    await db.bookings.create_index("company_id")
    await db.player_profiles.create_index("mobile", unique=True)
    await db.player_profiles.create_index("user_id", unique=True)
    await db.player_profiles.create_index("company_id")
    await db.vendors.create_index("user_id", unique=True)
    await db.vendor_listings.create_index("vendor_id")
    await db.vendor_bookings.create_index("company_id")
    await db.vendor_bookings.create_index("vendor_id")
    await seed_admin()
    await seed_demo_data()
    await seed_services()
    await seed_sports()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
