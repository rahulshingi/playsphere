from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Dict, Any

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
    if user.get("role") not in ("admin", "platform_admin", "company_admin", "organiser"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


async def require_platform_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("platform_admin", "admin"):
        raise HTTPException(status_code=403, detail="Platform admin only")
    return user


# ---------- Granular admin permissions ----------
ALL_PERMISSIONS = [
    "manage_events",
    "manage_vendors",
    "manage_listings",
    "manage_bookings",
    "manage_reviews",
    "manage_settings",
    "manage_companies",
]


def is_super_admin(user: dict) -> bool:
    return bool(user.get("role") in ("platform_admin", "admin") and user.get("is_super_admin"))


def has_permission(user: dict, perm: str) -> bool:
    if user.get("role") not in ("platform_admin", "admin"):
        return False
    if user.get("is_super_admin"):
        return True
    return perm in (user.get("permissions") or [])


def require_permission(perm: str):
    """Dependency factory: returns a dep that requires `perm` on the platform admin."""
    async def _dep(user: dict = Depends(require_platform_admin)) -> dict:
        if not has_permission(user, perm):
            raise HTTPException(status_code=403, detail=f"Missing permission: {perm}")
        return user
    return _dep


async def require_super_admin(user: dict = Depends(require_platform_admin)) -> dict:
    if not is_super_admin(user):
        raise HTTPException(status_code=403, detail="Super admin only")
    return user


async def require_company_admin(user: dict = Depends(get_current_user)) -> dict:
    """Accept company_admin OR organiser — they share the same powers (events, bookings)."""
    if user.get("role") not in ("company_admin", "organiser", "platform_admin", "admin"):
        raise HTTPException(status_code=403, detail="Company admin only")
    if user.get("role") in ("company_admin", "organiser") and not user.get("company_id"):
        raise HTTPException(status_code=403, detail="No company assigned")
    return user


def is_company_scoped(user: dict) -> bool:
    """True for HR (company_admin) and Organisers — both are scoped to a single `company_id`."""
    return user.get("role") in ("company_admin", "organiser")


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
    is_super_admin: Optional[bool] = False
    permissions: Optional[List[str]] = None
    # HR / Organiser opt-in to also act as a player. When true they get a
    # PlayerProfile (auto-created below) and can host local matches, be
    # rostered onto teams, and accrue player stats — all under the same login.
    also_player: Optional[bool] = False
    player_profile_id: Optional[str] = None


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginBody(BaseModel):
    # Accept either an email or a mobile number in the same field. The route
    # detects which and looks up the user accordingly. Kept the name `email`
    # for wire-format backwards compatibility; the FE now labels it
    # "Email or mobile number".
    email: str
    password: str


class CompanySignupBody(BaseModel):
    company_name: str
    admin_name: str
    admin_email: EmailStr
    admin_password: str
    contact_phone: Optional[str] = ""
    logo_url: Optional[str] = ""
    otp: Optional[str] = ""  # 6-digit code from /companies/signup/request-otp
    # Detailed address — used to auto-suggest nearby venues during event creation.
    address_line: Optional[str] = ""
    area: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    pincode: Optional[str] = ""


class Company(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    slug: str
    logo_url: Optional[str] = ""
    contact_email: Optional[str] = ""
    contact_phone: Optional[str] = ""
    owner_user_id: Optional[str] = None
    # Detailed address (used to localise venue suggestions during event creation).
    address_line: Optional[str] = ""
    area: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    pincode: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


SportType = Literal[
    "cricket", "football", "badminton", "tabletennis", "basketball",
    "volleyball", "chess", "quiz", "hackathon", "other"
]
# Legacy hardcoded whitelist above is kept for other schemas that need to
# validate incoming payloads strictly. Events (which the platform admin can
# extend at runtime with `/api/sports`) now accept ANY lower-case sport slug —
# validated at the router level against `db.sports`.
SportSlug = str
FixtureFormat = Literal["round_robin", "knockout", "swiss", "double_elimination"]
EventStatus = Literal["upcoming", "ongoing", "completed", "cancelled"]
EventType = Literal["single_company", "inter_company", "playsphere_organized"]
MatchStatus = Literal["scheduled", "live", "completed"]


class Team(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    department: Optional[str] = ""
    captain: Optional[str] = ""
    captain_player_id: Optional[str] = None
    # ---- Phase 3 (Feb 2026) — richer team roles ----
    # Vice-captain mirrors the captain pattern: a linked player-profile id +
    # the resolved display name (kept in sync on set).
    vice_captain: Optional[str] = ""
    vice_captain_player_id: Optional[str] = None
    # Free-text staff names — no linked account required. Handy for local
    # matches and sports like cricket / football where coach/manager are
    # part of the team card but don't need a login.
    coach_name: Optional[str] = ""
    manager_name: Optional[str] = ""
    # Distinct from `color` (used as the team brand chip). Jersey colour
    # is the on-field kit colour so referees can distinguish sides.
    jersey_color: Optional[str] = ""
    members: List[str] = Field(default_factory=list)
    color: Optional[str] = "#007AFF"
    logo_url: Optional[str] = ""
    event_id: Optional[str] = None
    company_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TeamCreate(BaseModel):
    name: str
    department: Optional[str] = ""
    captain: Optional[str] = ""
    color: Optional[str] = "#007AFF"
    jersey_color: Optional[str] = ""
    coach_name: Optional[str] = ""
    manager_name: Optional[str] = ""
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
    sport: SportSlug  # any admin-configured sport value
    # Populated automatically at create-time from db.sports lookup. Falls back
    # to `_SPORT_DEFAULTS` for well-known sports. Read by the frontend scorer +
    # `renderScore()` — drives which scoreboard UI to render for this event.
    scoring_pattern: Optional[str] = None  # cricket|football|basketball|racket|chess|quiz|hackathon|generic
    # Racket sports (badminton/tennis/pickleball/…) support both singles and
    # doubles. The creator picks one at event-creation time. `null` for team
    # sports where the concept doesn't apply.
    player_format: Optional[str] = None  # singles|doubles|team|individual|None
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
    # ---- Organiser contact — public on the event page so interested teams
    # can reach out to participate. Optional; falls back to created_by user's
    # email if none provided.
    contact_name: Optional[str] = ""
    contact_email: Optional[str] = ""
    contact_phone: Optional[str] = ""
    # ---- Player-hosted local matches ----
    # `is_local_match=True` means a regular player created this informal
    # neighborhood tournament. `listed_publicly=False` keeps it hidden from
    # the public /events list — accessible only via direct link + on the
    # creator's PlayerProfile. Owner/admin always see it regardless.
    is_local_match: bool = False
    listed_publicly: bool = True
    # Post-tournament photo gallery. Creator uploads via
    # POST /api/events/{id}/photos.
    photos: List[str] = Field(default_factory=list)
    # ---- Sponsorship marketplace ----
    accept_sponsorships: bool = False
    sponsorship_requirements: Dict[str, Any] = Field(default_factory=dict)
    # opportunities: [{id, name, type, price, currency, quantity_available, benefits, status, awarded_to_sponsor_id, awarded_to_name}]
    sponsorship_opportunities: List[Dict[str, Any]] = Field(default_factory=list)
    data_share_agreement: bool = False
    # ---- Organiser approval workflow ----
    # Lifecycle for events created by `organiser` role users:
    #   created -> pending_organiser_ack -> pending_admin_approval -> approved | rejected
    # HR/admin/platform_admin events skip the workflow and are created as "approved".
    approval_status: str = "approved"
    rejection_reason: Optional[str] = ""
    submitted_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    # ---- Cancellation (soft-delete) — preserves fixtures/teams/photos ----
    cancellation_reason: Optional[str] = ""
    cancelled_at: Optional[str] = None
    cancelled_by: Optional[str] = None
    # Organiser event-fee payment record. Populated at acknowledge-instructions:
    # `{fee, currency, status: not_required|pending_offline|paid_offline|paid_online, method, paid_at, provider}`.
    payment: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None  # user_id who created the event
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventCreate(BaseModel):
    name: str
    sport: SportSlug
    scoring_pattern: Optional[str] = None
    player_format: Optional[str] = None
    description: Optional[str] = ""
    format: FixtureFormat = "round_robin"
    event_type: EventType = "single_company"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    venue: Optional[str] = ""
    banner_url: Optional[str] = ""
    stream_url: Optional[str] = ""
    contact_name: Optional[str] = ""
    contact_email: Optional[str] = ""
    contact_phone: Optional[str] = ""
    # Player-created tournaments are tagged as informal "local matches" so the
    # UI can render a distinct badge and keep public marketplace surfaces
    # curated to organiser/HR/admin events.
    is_local_match: bool = False
    # Player controls whether the local match appears on the public /events
    # listing. Even when hidden, the event remains reachable via direct link
    # and the creator's PlayerProfile.
    listed_publicly: bool = True
    # Post-tournament gallery — creator uploads photos after wrap-up. Rendered
    # in a lightbox on the public event page.
    photos: List[str] = Field(default_factory=list)
    companies: List[str] = Field(default_factory=list)


# ============================================================================
#  SPONSORSHIP MARKETPLACE
# ============================================================================
class SponsorProfile(BaseModel):
    """Sponsor profile. user_id may belong to a 'sponsor' OR 'company_admin' role —
    company admins can both run sponsored events AND sponsor other organisers' events."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    company_name: str
    contact_person: Optional[str] = ""
    industry: Optional[str] = ""
    location: Optional[str] = ""
    target_locations: List[str] = Field(default_factory=list)
    target_event_types: List[str] = Field(default_factory=list)  # e.g. corporate-sports, family-day, sports-day
    target_audience: Optional[str] = ""
    budget_range: Optional[str] = ""  # free text like "₹10,000 – ₹50,000"
    website: Optional[str] = ""
    logo_url: Optional[str] = ""
    sponsor_interests: List[str] = Field(default_factory=list)  # sport slugs + corporate-sports/employee-engagement etc.
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SponsorSignupBody(BaseModel):
    email: str
    password: str
    company_name: str
    contact_person: Optional[str] = ""
    mobile: Optional[str] = ""


class SponsorshipInterest(BaseModel):
    """Sponsor-side expression of interest in an opportunity. Organiser approves/rejects."""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str
    event_name: Optional[str] = ""
    opportunity_id: str
    opportunity_name: Optional[str] = ""
    opportunity_price: Optional[float] = 0
    sponsor_id: str
    sponsor_user_id: str
    sponsor_company_name: Optional[str] = ""
    sponsor_industry: Optional[str] = ""
    sponsor_budget_range: Optional[str] = ""
    sponsor_website: Optional[str] = ""
    proposal_message: Optional[str] = ""
    status: Literal["pending", "accepted", "rejected"] = "pending"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decided_at: Optional[str] = None


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
    bracket_position: Optional[str] = None  # for knockout / double_elimination (WB/LB/GF prefixes)
    # ---- Phase 3 (Feb 2026) — Match metadata for diverse sports ----
    # Court / table / lane number (racket sports, snooker, etc.). Free-text
    # so organisers can say "Court 1" or "Table 3" or "Rink A".
    court_number: Optional[str] = ""
    # Officials on this match. Each: {role: "umpire"|"referee"|"scorer"|... , name: str}.
    officials: List[Dict[str, Any]] = Field(default_factory=list)
    # Toss result (cricket + racket sports with a serve toss). Shape:
    # {winner_team_id, decision: "bat"|"field"|"serve"|"receive", note?}
    toss: Optional[Dict[str, Any]] = None
    # Post-match visuals + auto-computed awards. Populated by the scorer /
    # score-update route when a match transitions to "completed"; also
    # manually editable by the event creator.
    hero_image_url: Optional[str] = ""
    awards: Optional[Dict[str, Any]] = None  # {mom, best_batter, best_bowler, top_scorer, …}
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
    created_by: Optional[str] = None
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
VendorType = Literal["ground", "court", "coach", "referee", "umpire", "trainer", "photographer", "videographer", "gym", "studio"]

# Category → activity list. Powers the adaptive "Sports / Activities" picker in
# the listing form. Grounds / courts / coaches all share the sport list; gyms
# and studios swap to wellness activities.
VENDOR_CATEGORY_SPORTS: dict = {
    "ground": ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"],
    "court": ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"],
    "coach": ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"],
    "referee": ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"],
    "umpire": ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"],
    "trainer": ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"],
    "photographer": [],
    "videographer": [],
    "gym": ["gym", "yoga", "zumba", "crossfit", "pilates", "cardio", "strength"],
    "studio": ["yoga", "zumba", "pilates", "dance", "aerobics"],
}


class PlayerSignupBody(BaseModel):
    name: str
    mobile: str
    password: str
    email: EmailStr  # required — used for OTP verification before account creation
    company_id: Optional[str] = None
    otp: Optional[str] = ""  # 6-digit code from /players/signup/request-otp
    # Business-model bridge: when a vendor's offline customer signs up through
    # the vendor's WhatsApp invite link (`?ref_vendor=<vendor_id>`), we stamp
    # this field on the resulting player so future marketplace bookings to that
    # vendor skip platform commission (they were already the vendor's customer
    # before the platform existed).
    ref_vendor: Optional[str] = None


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
    # Pretty share slug. Generated on first save from `name` — e.g. rahul-shingi.
    # Uniqueness enforced; players can share `/p/rahul-shingi` publicly.
    slug: Optional[str] = None
    # Multi-sport: list of sport slugs the player is interested in (e.g. ["cricket", "football"]).
    # When empty, legacy cricket fields below are used.
    interested_sports: List[str] = Field(default_factory=list)
    # Per-sport details keyed by sport slug. Each value is a free-form dict matching the
    # frontend SPORT_SCHEMAS (e.g. {"cricket": {"role": "batsman", "batting_hand": "right"}}).
    sport_profiles: Dict[str, Any] = Field(default_factory=dict)
    # ---- Legacy cricket-specific fields (kept for backwards compat with existing data) ----
    role: Optional[str] = "any"
    batting_hand: Optional[str] = "right"
    bowling_style: Optional[str] = "none"
    jersey_number: Optional[int] = None
    cricheroes_url: Optional[str] = ""
    # Per-sport career stats. Auto-computed where data is available (cricket from fixtures);
    # manual entry for other sports. Shape: { "cricket": {"matches": 12, "runs": 250, ...}, ... }
    lifetime_stats: Dict[str, Any] = Field(default_factory=dict)
    # ---- Common physical attributes ----
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    bio: Optional[str] = ""
    view_count: int = 0
    # Offline-source vendor — set when the player was invited by a vendor whose
    # offline books they already frequent. Marketplace bookings to this vendor
    # skip the platform commission (see request_vendor_booking).
    offline_source_vendor_id: Optional[str] = None
    # ---- Corporate email verification (Jul 2026) ----
    # A player signs up with their PERSONAL email (login identity). Once they
    # want to be discovered by their employer's HR, they add + verify a
    # separate `corporate_email`. Once verified, if a company already exists
    # with a matching domain we auto-link `company_id`; otherwise we still
    # store the verified corporate email so a later HR signup can pick them up.
    corporate_email: Optional[str] = None
    corporate_email_verified: bool = False
    corporate_email_verified_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------- Vendors ----------
class VendorSignupBody(BaseModel):
    business_name: str
    vendor_type: VendorType
    vendor_types: List[str] = Field(default_factory=list)  # multi-select; if empty falls back to [vendor_type]
    contact_name: str
    mobile: str
    email: EmailStr
    password: str
    city: str
    otp: Optional[str] = ""  # 6-digit code from /vendors/signup/request-otp


class Vendor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    business_name: str
    vendor_type: VendorType
    vendor_types: List[str] = Field(default_factory=list)  # multi-select; vendor_type kept as primary
    contact_name: str
    mobile: str
    email: str
    city: str
    approved: bool = False
    # ---- Phase 5C: paid "offline mode" unlock ----
    offline_mode: bool = False
    offline_subscription_expires_at: Optional[str] = None
    # ---- Phase 5D: invoice settings (only used when vendor generates invoices) ----
    gstin: Optional[str] = ""
    invoice_business_name: Optional[str] = ""
    invoice_address: Optional[str] = ""
    invoice_phone: Optional[str] = ""
    invoice_email: Optional[str] = ""
    invoice_tax_percent: Optional[float] = 18.0
    invoice_logo_url: Optional[str] = ""
    invoice_footer_note: Optional[str] = ""
    # ---- Task 44 (Feb 2026) — Per-vendor commission (set by platform admin) ----
    # Effective platform commission = max(gross * commission_percent / 100,
    # commission_min_flat). Both defaults may be tuned per vendor at approval
    # time. commission_min_flat is in the same currency as the listing.
    commission_percent: float = 10.0
    commission_min_flat: float = 100.0
    # ---- Overtime configuration (Jul 2026) ----
    # Vendor-configurable rate multiplier applied to the listing's hourly price
    # for time played beyond the booked slot. 1.0 = same rate, 1.5 = 1.5×, etc.
    overtime_charge_multiplier: float = 1.0
    # Rounding block for overtime billing (billed in blocks of N minutes, ceil).
    overtime_block_minutes: int = 15
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


class Review(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    listing_id: str
    vendor_id: str
    booking_id: Optional[str] = None
    author_user_id: str
    author_name: str
    author_role: str
    rating: int  # 1-5
    text: str = ""
    status: str = "pending_vendor"  # pending_vendor -> approved -> visible | rejected
    vendor_response: Optional[str] = None
    moderation_note: Optional[str] = None
    moderated_by_role: Optional[str] = None
    moderated_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorListing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    vendor_type: VendorType
    title: str
    description: str = ""
    images: List[str] = Field(default_factory=list)
    city: str
    # ---- Phase 5A: detailed address (used to match company / player / event locations) ----
    street: Optional[str] = ""
    locality: Optional[str] = ""
    state: Optional[str] = ""
    pincode: Optional[str] = ""
    maps_url: Optional[str] = ""
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
    street: Optional[str] = ""
    locality: Optional[str] = ""
    state: Optional[str] = ""
    pincode: Optional[str] = ""
    maps_url: Optional[str] = ""
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
    apply_membership_id: Optional[str] = None  # buyer wants to use this active membership
    # ---- Optional weekly recurrence (Phase 6) --------------------------------
    # When set, the server EXPANDS this single request into one booking row per
    # matching date from `requested_date` .. `recurrence_until` inclusive, so the
    # buyer can cancel / reschedule each occurrence independently.
    recurrence: Optional[str] = None  # None | "weekly"
    recurrence_until: Optional[str] = None  # YYYY-MM-DD (inclusive)
    recurrence_days_of_week: List[int] = Field(default_factory=list)  # 0=Mon..6=Sun


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
    applied_membership_id: Optional[str] = None  # if set, slot was paid via membership
    # Recurrence linkage — populated when this booking is one occurrence of a
    # weekly-recurring booking. All occurrences share the same group id so the
    # /bookings tab can show them as a series.
    recurrence_group_id: Optional[str] = None
    # Business-model fields:
    #   offline_source=True when the buyer is a player whose offline_source_vendor_id
    #   matches this listing's vendor. Commission is then skipped.
    offline_source: bool = False
    commission_percent: float = 0
    commission_amount: float = 0  # rupees the platform will collect from the vendor
    commission_min_flat: float = 0  # snapshot of vendor's flat floor at time of booking
    # ---- Show-up tracking (Task 44 Feb 2026) ----
    checked_in_at: Optional[str] = None   # ISO — vendor confirmed customer arrived
    checked_in_by: Optional[str] = None   # user id of vendor who marked arrival
    no_show_at: Optional[str] = None       # explicit "no-show" mark (manual or auto)
    completed_at: Optional[str] = None     # completion timestamp (arrival OR endtime)
    # ---- Overtime tracking (Jul 2026) ----
    arrived_at: Optional[str] = None
    actual_end_time: Optional[str] = None  # HH:MM captured at completion
    overtime_minutes: int = 0
    overtime_amount: float = 0             # billed to buyer for extra time
    overtime_commission_amount: float = 0  # platform share of overtime (same pct)
    overtime_note: Optional[str] = ""
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
    # ---- Organiser approval workflow ----
    # Free-form instructions shown to organisers in the acknowledgement modal
    # before their event is submitted to the platform admin for approval.
    # Supports plain text or basic HTML; rendered via dangerouslySetInnerHTML
    # so the admin can include bullet lists, bold, etc.
    organiser_event_instructions: Optional[str] = (
        "Please read these guidelines carefully before submitting your event:\n\n"
        "1. Tournament name, dates, and venue must be accurate.\n"
        "2. Sponsorship terms, prize money and entry fees must comply with Kreeda Nation policies.\n"
        "3. All participants must be over 18 unless an explicit junior tournament is declared.\n"
        "4. Fair-play rules apply — match results, scoring and conduct are subject to platform audit.\n"
        "5. By submitting, you authorise Kreeda Nation to list your event publicly once approved."
    )
    # Non-refundable fee the organiser pays per event before it goes to admin
    # approval. 0 = free (skip payment step). Admin edits this in /platform-admin.
    organiser_event_fee: float = 0.0
    organiser_event_fee_currency: str = "INR"
    # ---- Phase 5C: business model ----
    booking_commission_percent: float = 10.0
    membership_commission_percent: float = 5.0
    offline_subscription_monthly_price: float = 99.0
    offline_subscription_yearly_price: float = 999.0
    offline_subscription_currency: str = "INR"
    # Business-model toggle — when True, an existing vendor renewing their
    # offline subscription pays the SAME price they paid last time (the last
    # activated subscription's `amount`). New vendors always pay the current
    # monthly/yearly price. Default True to keep long-term vendors happy.
    offline_subscription_locks_existing_price: bool = True
    # ---- Mobile app store links ----
    # When a URL is set, the footer badge becomes a live external link.
    # When empty (default), the footer shows a disabled "Stay tuned — launching soon" badge
    # so users know the mobile apps are on the roadmap.
    ios_app_url: Optional[str] = ""
    android_app_url: Optional[str] = ""


@api.post("/auth/also-player")
async def toggle_also_player(body: dict, user: dict = Depends(get_current_user)):
    """HR / organiser opts in (or out) of being a player too. On opt-in,
    creates a PlayerProfile keyed to their user_id if one doesn't exist yet
    (idempotent). On opt-out, keeps the profile but sets `also_player=False`
    so the top-nav player links disappear — no data loss."""
    if user.get("role") not in ("company_admin", "organiser", "platform_admin", "admin"):
        raise HTTPException(403, "Only HR, organiser, or admin accounts can opt-in as a player")
    enabled = bool((body or {}).get("enabled", True))
    await db.users.update_one({"id": user["id"]}, {"$set": {"also_player": enabled}})
    if enabled:
        existing = await db.player_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
        if not existing:
            prof = PlayerProfile(
                user_id=user["id"],
                name=user.get("name") or user.get("email", "").split("@")[0],
                mobile=user.get("mobile") or "",
                email=user.get("email"),
                company_id=user.get("company_id"),
                slug=await _unique_player_slug(user.get("name") or "player"),
            )
            await db.player_profiles.insert_one(prof.model_dump())
    return {"ok": True, "also_player": enabled}


async def _user_with_company(user: dict) -> dict:
    """Attach company_name (if any) and strip password fields."""
    out = {k: user.get(k) for k in ["id", "email", "name", "role", "company_id"]}
    out["company_name"] = None
    if out.get("company_id"):
        c = await db.companies.find_one({"id": out["company_id"]}, {"_id": 0, "name": 1})
        if c:
            out["company_name"] = c["name"]
    # Surface platform-admin RBAC flags for the frontend
    if user.get("role") in ("platform_admin", "admin"):
        super_flag = bool(user.get("is_super_admin"))
        out["is_super_admin"] = super_flag
        if super_flag:
            out["permissions"] = list(ALL_PERMISSIONS)
        else:
            out["permissions"] = list(user.get("permissions") or [])
    # `also_player` opt-in — surfaces PlayerProfile.id so the frontend can
    # jump straight to /players/me (and enable "Host match" for HR/organiser).
    if user.get("also_player"):
        out["also_player"] = True
        prof = await db.player_profiles.find_one({"user_id": user.get("id")}, {"_id": 0, "id": 1})
        if prof:
            out["player_profile_id"] = prof["id"]
    return out


# ---------- Auth / Company / Password reset routes are wired via routes/auth.py at bottom ----------

# ---------- Helper for sport-specific default scores ----------
def default_score(sport: str) -> dict:
    if sport == "cricket":
        return {"team_a": {"runs": 0, "wickets": 0, "overs": 0.0},
                "team_b": {"runs": 0, "wickets": 0, "overs": 0.0}}
    if sport == "football":
        return {"team_a": {"goals": 0}, "team_b": {"goals": 0}}
    if sport == "basketball":
        return {"team_a": {"points": 0, "q": 1}, "team_b": {"points": 0, "q": 1}}
    if sport in ("badminton", "pickleball"):
        return {"team_a": {"sets": [0, 0, 0]}, "team_b": {"sets": [0, 0, 0]}}
    if sport == "tabletennis":
        return {"team_a": {"sets": [0, 0, 0, 0, 0]}, "team_b": {"sets": [0, 0, 0, 0, 0]}}
    if sport in ("tennis", "lawntennis", "squash"):
        return {"team_a": {"sets": [0, 0, 0]}, "team_b": {"sets": [0, 0, 0]}}
    if sport == "volleyball":
        return {"team_a": {"sets": [0, 0, 0, 0, 0]}, "team_b": {"sets": [0, 0, 0, 0, 0]}}
    if sport in ("snooker", "pool"):
        return {"team_a": {"frames_won": 0}, "team_b": {"frames_won": 0}}
    if sport == "chess":
        return {"team_a": {"points": 0}, "team_b": {"points": 0}, "result": None}
    if sport == "quiz":
        return {"team_a": {"points": 0}, "team_b": {"points": 0}}
    if sport == "hackathon":
        return {"team_a": {"score": 0}, "team_b": {"score": 0}}
    return {"team_a": {"score": 0}, "team_b": {"score": 0}}


# ---------- Events / Teams / Team-roster players are wired via routes/events.py at bottom ----------


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
    # Creator always manages their own event. Enables player-hosted local
    # matches without granting a broader role escalation.
    if event.get("created_by") and event.get("created_by") == user.get("id"):
        return True
    if role in ("company_admin", "organiser"):
        cid = user.get("company_id")
        if not cid:
            return False
        if event.get("company_id") == cid:
            return True
        if cid in (event.get("companies") or []):
            return True
    return False


async def _fixtures_locked(event_id: str) -> bool:
    """True if any fixture for this event has moved past 'scheduled' (live or completed).
    Once the first match is underway, regenerating fixtures would invalidate scores."""
    doc = await db.fixtures.find_one(
        {"event_id": event_id, "status": {"$in": ["live", "completed"]}},
        {"_id": 0, "id": 1},
    )
    return doc is not None


async def _can_score_fixture(user: dict, fixture: dict, event: dict) -> bool:
    """Allowed if (a) the user can manage the event, or
    (b) the user has an event_scorers assignment for this event with either
    no fixture restriction or this specific fixture in their scope.
    The role check is intentionally lenient — invites are explicit per-event grants,
    so any user (scorer/player/etc.) explicitly assigned should be able to score."""
    if await _can_manage_event(user, event):
        return True
    scorer = await db.event_scorers.find_one(
        {"event_id": event["id"], "user_id": user["id"]}, {"_id": 0}
    )
    if not scorer:
        return False
    fids = scorer.get("fixture_ids") or []
    return (not fids) or (fixture["id"] in fids)


async def _can_manage_team(user: dict, event: dict, team: dict) -> bool:
    if await _can_manage_event(user, event):
        # company_admin can only manage their own company's teams in inter_company
        if is_company_scoped(user) and event.get("event_type") == "inter_company":
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


async def _unique_player_slug(name: str) -> str:
    """Generate a URL-safe, unique slug for the /p/{slug} share URL. Falls
    back to `player-<random>` if the name yields an empty slug."""
    base = "".join(c.lower() if c.isalnum() else "-" for c in (name or "")).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    base = base[:40] or f"player-{uuid.uuid4().hex[:6]}"
    candidate = base
    n = 1
    while await db.player_profiles.find_one({"slug": candidate}):
        n += 1
        candidate = f"{base}-{n}"
    return candidate


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
    if is_company_scoped(user):
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
        if is_company_scoped(user) and t.get("company_id") != user.get("company_id"):
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


# ---------- Phase 3: team-role updates (vice-captain, coach, manager, jersey_color, etc.) ----------
_TEAM_META_ALLOWED = {
    "name", "department", "color", "jersey_color", "coach_name", "manager_name",
    "logo_url", "vice_captain_player_id",
}


@api.patch("/events/{event_id}/teams/{team_id}", response_model=Team)
async def update_event_team(event_id: str, team_id: str, body: dict, user: dict = Depends(get_current_user)):
    """Update team metadata for Phase 3 team roles.

    Fields (all optional): name, department, color, jersey_color, coach_name,
    manager_name, logo_url, vice_captain_player_id. When vice_captain_player_id
    is set, the linked player's name is auto-resolved and stored in
    `vice_captain`; passing null / empty clears both.
    """
    ev = await _get_event_or_404(event_id)
    t = await _get_team_or_404(team_id, event_id)
    if not await _can_manage_team(user, ev, t):
        raise HTTPException(403, "Not allowed")
    upd: dict = {}
    body = body or {}
    for k in _TEAM_META_ALLOWED:
        if k in body:
            upd[k] = body[k]
    # Auto-resolve vice-captain name
    if "vice_captain_player_id" in body:
        vc_id = body.get("vice_captain_player_id") or None
        if vc_id:
            prof = await db.player_profiles.find_one({"id": vc_id}, {"_id": 0, "name": 1})
            if not prof:
                raise HTTPException(404, "Vice-captain player not found")
            upd["vice_captain_player_id"] = vc_id
            upd["vice_captain"] = prof.get("name") or ""
            # Auto-add to roster if not already there
            members = list(t.get("members") or [])
            if vc_id not in members:
                members.append(vc_id)
                upd["members"] = members
        else:
            upd["vice_captain_player_id"] = None
            upd["vice_captain"] = ""
    if not upd:
        raise HTTPException(400, "No valid fields provided")
    await db.teams.update_one({"id": team_id}, {"$set": upd})
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
        slug=await _unique_player_slug(name),
    )
    await db.player_profiles.insert_one(prof.model_dump())
    logger.warning("Quick-add player created: name=%s mobile=%s email=%s temp_password=%s",
                   name, mobile, login_email, temp_password)
    # Best-effort email — only sent when a real email was provided (not the
    # synthetic `player_<mobile>@players.playsphere.app`). SendGrid failures
    # are swallowed here so the caller still succeeds; the API response
    # returns `temp_password` for the organiser to share manually.
    if email:
        try:
            from email_service import send_welcome_email  # type: ignore
            send_welcome_email(to=email, name=name, temp_password=temp_password,
                               login_url=(os.environ.get("FRONTEND_URL", "") + "/login"))
        except Exception as exc:  # pragma: no cover — best-effort
            logger.info("Welcome email skipped for %s: %s", email, exc)
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
    # Auto-tag the sport onto the player's interested_sports so their profile
    # starts showing stats for sports they've actually played. The player can
    # still remove it manually from profile settings.
    sport = (ev.get("sport") or "").strip().lower()
    if sport:
        await db.player_profiles.update_one({"id": pid}, {"$addToSet": {"interested_sports": sport}})
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


# ---------- Forgot / reset password routes wired via routes/auth.py ----------

# ---------- Fixture generation, scoring and WebSocket are wired via routes/fixtures.py ----------
async def propagate_knockout_winner(fixture: dict):
    """Shared knockout winner propagation — used by routes/fixtures.py and routes/cricket.py."""
    event_id = fixture["event_id"]
    rnd = fixture["round"]
    next_round = rnd + 1
    next_fixtures = await db.fixtures.find(
        {"event_id": event_id, "round": next_round}, {"_id": 0}
    ).sort("match_number", 1).to_list(500)
    if not next_fixtures:
        return
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
async def list_sponsors(event_id: Optional[str] = None, user: Optional[dict] = Depends(get_current_user_optional)):
    """Sponsors are scoped to the caller:
    * anonymous users may only read the sponsor banner for a specific `event_id`;
    * platform_admin sees everything;
    * company_admin/organiser sees sponsors on their own events + sponsors they created;
    * when `event_id` is passed and the user cannot manage that event, only sponsors of
      that public event are returned (public read of the event's sponsor banner).
    """
    if not user:
        if not event_id:
            raise HTTPException(401, "Login required to list sponsors")
        docs = await db.sponsors.find({"event_id": event_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return [Sponsor(**d) for d in docs]
    role = user.get("role")
    if role in ("platform_admin", "admin"):
        flt = {"event_id": event_id} if event_id else {}
    else:
        # Compute the set of event ids this user can manage.
        cid = user.get("company_id")
        owned_flt = {"$or": []}
        if cid:
            owned_flt["$or"].append({"company_id": cid})
            owned_flt["$or"].append({"companies": cid})
        events = await db.events.find(owned_flt, {"_id": 0, "id": 1}).to_list(1000) if owned_flt["$or"] else []
        owned_event_ids = [e["id"] for e in events]
        or_clauses = [{"created_by": user["id"]}]
        if owned_event_ids:
            or_clauses.append({"event_id": {"$in": owned_event_ids}})
        # If event_id is explicitly requested and it's NOT one they own, still return
        # the public sponsor banner for that event (read-only).
        if event_id and event_id not in owned_event_ids:
            flt = {"event_id": event_id}
        else:
            flt = {"$or": or_clauses}
            if event_id:
                flt = {"$and": [flt, {"event_id": event_id}]}
    docs = await db.sponsors.find(flt, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [Sponsor(**d) for d in docs]


@api.post("/sponsors", response_model=Sponsor)
async def create_sponsor(body: SponsorCreate, user: dict = Depends(require_admin)):
    s = Sponsor(**body.model_dump(), created_by=user["id"])
    await db.sponsors.insert_one(s.model_dump())
    return s


async def _require_own_sponsor(sponsor_id: str, user: dict) -> dict:
    doc = await db.sponsors.find_one({"id": sponsor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Sponsor not found")
    if user.get("role") in ("platform_admin", "admin"):
        return doc
    if doc.get("created_by") == user["id"]:
        return doc
    if doc.get("event_id"):
        ev = await db.events.find_one({"id": doc["event_id"]}, {"_id": 0})
        if ev and await _can_manage_event(user, ev):
            return doc
    raise HTTPException(403, "You can only manage sponsors you created")


@api.patch("/sponsors/{sponsor_id}", response_model=Sponsor)
async def update_sponsor(sponsor_id: str, body: dict, user: dict = Depends(require_admin)):
    await _require_own_sponsor(sponsor_id, user)
    body.pop("id", None); body.pop("created_by", None)
    await db.sponsors.update_one({"id": sponsor_id}, {"$set": body})
    doc = await db.sponsors.find_one({"id": sponsor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Sponsor not found")
    return Sponsor(**doc)


@api.delete("/sponsors/{sponsor_id}")
async def delete_sponsor(sponsor_id: str, user: dict = Depends(require_admin)):
    await _require_own_sponsor(sponsor_id, user)
    await db.sponsors.delete_one({"id": sponsor_id})
    return {"ok": True}



# ---------- Event Scorers (invited match scorers) ----------
class ScorerInviteBody(BaseModel):
    email: EmailStr
    name: Optional[str] = ""
    fixture_ids: List[str] = Field(default_factory=list)  # empty = all fixtures of the event


@api.get("/events/{event_id}/scorers")
async def list_event_scorers(event_id: str, user: dict = Depends(get_current_user)):
    ev = await _get_event_or_404(event_id)
    if not await _can_manage_event(user, ev):
        raise HTTPException(403, "Only the event organiser can view scorers")
    docs = await db.event_scorers.find({"event_id": event_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@api.post("/events/{event_id}/scorers")
async def invite_event_scorer(event_id: str, body: ScorerInviteBody, user: dict = Depends(get_current_user)):
    """Invite a scorer for this event. If the email is not yet registered, a `scorer`
    user is auto-created with a temp password and an invitation email is dispatched.
    The temp password is also returned in the response so the organiser can share it
    manually if SendGrid delivery fails."""
    ev = await _get_event_or_404(event_id)
    if not await _can_manage_event(user, ev):
        raise HTTPException(403, "Only the event organiser can invite scorers")

    email = body.email.lower().strip()
    # Validate the fixture_ids actually belong to this event.
    if body.fixture_ids:
        valid = await db.fixtures.find(
            {"id": {"$in": body.fixture_ids}, "event_id": event_id}, {"_id": 0, "id": 1}
        ).to_list(500)
        if len(valid) != len(set(body.fixture_ids)):
            raise HTTPException(400, "One or more fixture ids do not belong to this event")

    existing_user = await db.users.find_one({"email": email})
    temp_password: Optional[str] = None
    if not existing_user:
        temp_password = _gen_temp_password()
        scorer_user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": body.name or email.split("@")[0],
            "role": "scorer",
            "company_id": None,
            "password_hash": hash_password(temp_password),
            "must_reset": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(scorer_user)
        scorer_user_id = scorer_user["id"]
    else:
        if existing_user.get("role") not in ("scorer", "platform_admin", "admin", "company_admin", "organiser"):
            # Existing player/vendor/sponsor accounts can still be invited — we don't
            # change their role; the scoring permission piggybacks on the event_scorers
            # collection regardless.
            pass
        scorer_user_id = existing_user["id"]

    # Upsert the scorer assignment. fixture_ids = [] means "all fixtures of this event".
    existing_assign = await db.event_scorers.find_one(
        {"event_id": event_id, "user_id": scorer_user_id}, {"_id": 0}
    )
    if existing_assign:
        await db.event_scorers.update_one(
            {"id": existing_assign["id"]},
            {"$set": {"fixture_ids": body.fixture_ids, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        assignment_id = existing_assign["id"]
    else:
        assignment_id = str(uuid.uuid4())
        await db.event_scorers.insert_one({
            "id": assignment_id,
            "event_id": event_id,
            "user_id": scorer_user_id,
            "email": email,
            "name": body.name or email.split("@")[0],
            "fixture_ids": body.fixture_ids,
            "invited_by": user.get("id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Build the email body. Always include event name + login link.
    login_url = f"{os.environ.get('PUBLIC_APP_URL', 'https://kreedanation.com').rstrip('/')}/login"
    scope_label = "all matches" if not body.fixture_ids else f"{len(body.fixture_ids)} match(es)"
    invite_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px 20px;">
      <div style="max-width:560px;margin:auto;background:#141414;border:1px solid #ffffff14;border-radius:6px;padding:32px;">
        <div style="font-size:11px;letter-spacing:.3em;color:#84CC16;text-transform:uppercase;font-family:ui-monospace,monospace;">/ You're invited to score</div>
        <h1 style="font-size:28px;letter-spacing:.05em;margin:12px 0 24px;color:#fff;">KREEDA NATION</h1>
        <p>Hi,</p>
        <p><b>{(user.get('name') or user.get('email'))}</b> has invited you to be a match scorer for
          <b style="color:#84CC16;">{ev.get('name')}</b> ({scope_label}).</p>
        {"<p>Use these credentials to sign in:</p>"
         f"<div style='background:#0a0a0a;border:1px solid #ffffff14;border-radius:4px;padding:16px;margin:16px 0;font-family:ui-monospace,monospace;font-size:13px;'>"
         f"<div>Email: <span style='color:#84CC16;'>{email}</span></div>"
         f"<div>Temporary password: <span style='color:#FACC15;'>{temp_password}</span></div></div>"
         "<p style='font-size:12px;color:#a3a3a3;'>You'll be asked to reset your password on first sign-in.</p>"
         if temp_password else "<p>Sign in with your existing Kreeda Nation credentials.</p>"}
        <p style="text-align:center;margin:28px 0;">
          <a href="{login_url}" style="display:inline-block;background:#84CC16;color:#000;font-weight:700;padding:12px 28px;border-radius:4px;text-decoration:none;letter-spacing:.05em;">SIGN IN TO SCORE</a>
        </p>
        <hr style="border:none;border-top:1px solid #ffffff14;margin:28px 0;"/>
        <p style="font-size:11px;color:#737373;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.2em;">Kreeda Nation · Where teams compete, connect &amp; grow</p>
      </div>
    </div>
    """
    try:
        from email_service import send_email as _send_real_email  # type: ignore
        email_sent = _send_real_email(
            to=email,
            subject=f"You're invited to score {ev.get('name')} on Kreeda Nation",
            html=invite_html,
        )
    except Exception:
        logger.exception("Failed to dispatch scorer invitation email")
        email_sent = False

    return {
        "ok": True,
        "assignment_id": assignment_id,
        "user_created": temp_password is not None,
        "temp_password": temp_password,  # surfaced once, in case SendGrid is down
        "email_sent": bool(email_sent),
    }


@api.delete("/events/{event_id}/scorers/{assignment_id}")
async def remove_event_scorer(event_id: str, assignment_id: str, user: dict = Depends(get_current_user)):
    ev = await _get_event_or_404(event_id)
    if not await _can_manage_event(user, ev):
        raise HTTPException(403, "Only the event organiser can remove scorers")
    await db.event_scorers.delete_one({"id": assignment_id, "event_id": event_id})
    return {"ok": True}


@api.get("/scorers/me/events")
async def scorer_my_events(user: dict = Depends(get_current_user)):
    """List event+fixture assignments for the current scorer (used by their dashboard)."""
    if user.get("role") != "scorer":
        # Allow event managers to also see their own assignments via this endpoint, but
        # the main use-case is the lightweight scorer dashboard.
        return {"events": []}
    assigns = await db.event_scorers.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)
    event_ids = list({a["event_id"] for a in assigns})
    events = {e["id"]: e async for e in db.events.find({"id": {"$in": event_ids}}, {"_id": 0})}
    out = []
    for a in assigns:
        ev = events.get(a["event_id"])
        if not ev:
            continue
        fixture_ids = a.get("fixture_ids") or []
        if fixture_ids:
            fxs = await db.fixtures.find({"id": {"$in": fixture_ids}}, {"_id": 0}).to_list(500)
        else:
            fxs = await db.fixtures.find({"event_id": ev["id"]}, {"_id": 0}).to_list(500)
        out.append({
            "assignment_id": a["id"],
            "event": {k: ev.get(k) for k in ("id", "name", "sport", "format", "status", "start_date", "venue", "banner_url")},
            "fixtures": fxs,
            "scope": "all" if not fixture_ids else "specific",
        })
    return {"events": out}



# ---------- Services catalog + classic Bookings are wired via routes/bookings.py at bottom ----------


# ---------- Player accounts (mobile + password) ----------
from routes.auth import _consume_signup_otp_sync as _make_otp_consumer  # noqa: E402
_consume_player_otp = _make_otp_consumer(db, "player_signup_otps")


@api.post("/players/register", response_model=UserPublic)
async def player_register(body: PlayerSignupBody, response: Response):
    if await db.player_profiles.find_one({"mobile": body.mobile}):
        raise HTTPException(400, "Mobile already registered")
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already in use")

    otp_input = (getattr(body, "otp", None) or "").strip()
    if not otp_input:
        raise HTTPException(400, "Email verification code is required. Request one before signing up.")
    await _consume_player_otp(email, otp_input)

    user_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": user_id,
        "email": email,
        "name": body.name,
        "role": "player",
        "company_id": body.company_id,
        "mobile": body.mobile,
        "password_hash": hash_password(body.password),
        "email_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    company_name = None
    if body.company_id:
        c = await db.companies.find_one({"id": body.company_id}, {"_id": 0, "name": 1})
        company_name = c["name"] if c else None
    profile = PlayerProfile(
        user_id=user_id, name=body.name, mobile=body.mobile, email=email,
        company_id=body.company_id, company_name=company_name,
        offline_source_vendor_id=(body.ref_vendor or None),
        slug=await _unique_player_slug(body.name),
    )
    await db.player_profiles.insert_one(profile.model_dump())
    await db.player_signup_otps.update_one(
        {"email": email}, {"$set": {"verified": True, "used_at": datetime.now(timezone.utc).isoformat()}}
    )
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


# ---------------------------------------------------------------------------
# Corporate email linking (Jul 2026) — allow a player with a personal-email
# signup to attach + verify a work email so HR at that company can find them.
# ---------------------------------------------------------------------------
# NOTE: Endpoints + `_auto_link_company_by_domain` extracted to
# routes/players_corp_email.py (registered below). We keep `_email_domain`
# here because `list_player_profiles` still uses it directly.
def _email_domain(e: str) -> str:
    return (e or "").strip().lower().split("@", 1)[-1] if "@" in (e or "") else ""


@api.get("/players/me")
async def get_my_player_profile(user: dict = Depends(get_current_user)):
    # Native `role=player` OR HR/organiser/admin who opted-in via /auth/also-player.
    if user.get("role") != "player" and not user.get("also_player"):
        raise HTTPException(403, "Player only")
    doc = await db.player_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Profile not found")
    return doc


@api.patch("/players/me")
async def update_my_profile(body: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "player" and not user.get("also_player"):
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
    sport: Optional[str] = None,
    role: Optional[str] = None,
    hand: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 500,
    user: dict = Depends(get_current_user),
):
    """Search players. Optional filters:
    - sport: only return players who picked this sport in interested_sports (cricket also matches legacy profiles).
    - role: filter by the primary role field of that sport (role / position / specialty / domain — schema-dependent).
    - hand: filter by hand-style field (batting_hand / preferred_foot / shooting_hand / hand / preferred_color).
    - city: case-insensitive city contains.
    """
    flt = {}
    hr_and_clauses = []
    # Company HRs are scoped: they see (a) players whose profile.company_id
    # matches theirs OR (b) players who verified a corporate email whose
    # domain matches the HR's login-email domain. This lets a player who
    # signed up with a personal email still be discovered once they verify
    # their work email — see /players/me/corporate-email/verify.
    if user.get("role") == "company_admin":
        own_cid = user.get("company_id")
        if not own_cid:
            return []
        own_domain = _email_domain(user.get("email") or "")
        clauses = [{"company_id": own_cid}]
        if own_domain and own_domain not in {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"}:
            clauses.append({
                "corporate_email_verified": True,
                "corporate_email": {"$regex": f"@{own_domain}$", "$options": "i"},
            })
        # Stash under $and so downstream $or-based q / sport filters don't clobber it.
        hr_and_clauses.append({"$or": clauses})
    elif company_id:
        flt["company_id"] = company_id
    if q:
        flt["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"city": {"$regex": q, "$options": "i"}},
            {"mobile": {"$regex": q, "$options": "i"}},
        ]
    if city:
        flt["city"] = {"$regex": city, "$options": "i"}

    if sport:
        # Match either the new interested_sports array OR the legacy cricket-only profiles
        # (those have no interested_sports field but valid cricket role/style fields).
        if sport == "cricket":
            flt["$or"] = (flt.get("$or") or []) + [
                {"interested_sports": "cricket"},
                # Legacy: missing or empty interested_sports + any cricket data
                {"$and": [
                    {"$or": [{"interested_sports": {"$exists": False}}, {"interested_sports": {"$size": 0}}]},
                    {"$or": [{"role": {"$exists": True, "$nin": [None, ""]}}, {"batting_hand": {"$exists": True, "$nin": [None, ""]}}]},
                ]},
            ]
        else:
            flt["interested_sports"] = sport

    # Role + hand are sport-scoped: they only make sense alongside a sport filter.
    if sport and (role or hand):
        # Primary "role-like" field varies per sport. For cricket legacy we also match the top-level
        # `role` / `batting_hand` fields. For other sports we use sport_profiles.{sport}.{key}.
        and_clauses = []
        ROLE_KEYS = ["role", "position", "specialty", "domain"]
        HAND_KEYS = ["batting_hand", "preferred_foot", "shooting_hand", "hand", "preferred_color"]
        if role:
            ors = [{f"sport_profiles.{sport}.{k}": role} for k in ROLE_KEYS]
            if sport == "cricket":
                ors.append({"role": role})  # legacy
            and_clauses.append({"$or": ors})
        if hand:
            ors = [{f"sport_profiles.{sport}.{k}": hand} for k in HAND_KEYS]
            if sport == "cricket":
                ors.append({"batting_hand": hand})  # legacy
            and_clauses.append({"$or": ors})
        # Merge: AND-combine with any existing $or (q+sport-legacy)
        if "$and" in flt:
            flt["$and"].extend(and_clauses)
        else:
            flt["$and"] = and_clauses

    limit = max(1, min(int(limit), 2000))
    if hr_and_clauses:
        flt.setdefault("$and", []).extend(hr_and_clauses)
    docs = await db.player_profiles.find(flt, {"_id": 0}).sort([("created_at", -1), ("name", 1)]).to_list(limit)
    # Mask mobile for non-self viewers (keep last 4 digits)
    for d in docs:
        if user.get("id") != d.get("user_id"):
            m = d.get("mobile") or ""
            d["mobile_masked"] = "•••• " + m[-4:] if len(m) >= 4 else m
            d.pop("mobile", None)
    return docs


@api.get("/players/profiles/{profile_id}/stats")
async def player_lifetime_stats(profile_id: str, _: Optional[dict] = Depends(get_current_user_optional)):
    """Career stats per sport. Cricket is auto-aggregated from completed fixtures where the
    player appeared in the playing XI; other sports return the player's manually-entered
    lifetime_stats dict. Manual entries always merge over auto values for fields the player
    chose to override (useful for stats from games played outside the platform)."""
    profile = await db.player_profiles.find_one({"id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(404, "Profile not found")
    manual = profile.get("lifetime_stats") or {}
    result: Dict[str, Any] = {}

    # ---- Cricket auto-aggregation ----
    cricket_auto = {
        "matches": 0, "runs": 0, "balls_faced": 0, "fours": 0, "sixes": 0,
        "innings_batted": 0, "dismissals": 0, "highest_score": 0,
        "balls_bowled": 0, "runs_conceded": 0, "wickets": 0, "overs_bowled": 0.0,
        "innings_bowled": 0,
    }
    seen_fixtures = set()
    # Find every cricket fixture where this player_id appears in playing_xi or innings.
    cursor = db.fixtures.find({
        "score.sport": "cricket",
        "$or": [
            {"score.playing_xi.team_a.player_id": profile_id},
            {"score.playing_xi.team_b.player_id": profile_id},
        ],
    }, {"_id": 0, "id": 1, "score": 1, "status": 1})
    async for fx in cursor:
        if fx["id"] in seen_fixtures:
            continue
        seen_fixtures.add(fx["id"])
        score = fx.get("score") or {}
        if score.get("match_state") != "completed":
            # Only count completed matches for "matches played" — in-progress games skew averages.
            continue
        cricket_auto["matches"] += 1
        for inn in score.get("innings", []):
            for b in inn.get("batsmen", []):
                if b.get("player_id") == profile_id:
                    cricket_auto["innings_batted"] += 1
                    cricket_auto["runs"] += int(b.get("runs", 0) or 0)
                    cricket_auto["balls_faced"] += int(b.get("balls", 0) or 0)
                    cricket_auto["fours"] += int(b.get("fours", 0) or 0)
                    cricket_auto["sixes"] += int(b.get("sixes", 0) or 0)
                    cricket_auto["highest_score"] = max(cricket_auto["highest_score"], int(b.get("runs", 0) or 0))
                    if b.get("out"):
                        cricket_auto["dismissals"] += 1
            for bw in inn.get("bowlers", []):
                if bw.get("player_id") == profile_id:
                    cricket_auto["innings_bowled"] += 1
                    cricket_auto["balls_bowled"] += int(bw.get("balls", 0) or 0)
                    cricket_auto["runs_conceded"] += int(bw.get("runs", 0) or 0)
                    cricket_auto["wickets"] += int(bw.get("wickets", 0) or 0)
    # ---- Simple-cricket shape: score = {team_a:{batters,bowlers,total}, team_b:{...}} ----
    # Local matches / quick-score events store batters/bowlers directly on the side. Walk
    # every completed fixture where this player was rostered.
    team_ids = [t["id"] async for t in db.teams.find(
        {"$or": [
            {"members": profile_id}, {"player_ids": profile_id},
            {"players.id": profile_id}, {"players.player_id": profile_id},
        ]},
        {"_id": 0, "id": 1}
    )]
    async for fx in db.fixtures.find(
        {
            "status": "completed",
            "$or": [{"team_a_id": {"$in": team_ids}}, {"team_b_id": {"$in": team_ids}}],
        },
        {"_id": 0, "id": 1, "score": 1, "event_id": 1, "winner_id": 1, "awards": 1,
         "team_a_id": 1, "team_b_id": 1}
    ):
        if fx["id"] in seen_fixtures:
            continue
        # Skip if event isn't cricket — we're only aggregating cricket right here.
        ev = await db.events.find_one({"id": fx["event_id"]}, {"_id": 0, "sport": 1})
        if not ev or ev.get("sport") != "cricket":
            continue
        score = fx.get("score") or {}
        counted = False
        for side_key in ("team_a", "team_b"):
            side = score.get(side_key) or {}
            for b in side.get("batters") or []:
                if b.get("player_id") == profile_id or b.get("id") == profile_id:
                    if not counted:
                        cricket_auto["matches"] += 1
                        counted = True
                    cricket_auto["innings_batted"] += 1
                    cricket_auto["runs"] += int(b.get("runs", 0) or 0)
                    cricket_auto["balls_faced"] += int(b.get("balls", 0) or 0)
                    cricket_auto["fours"] += int(b.get("fours", 0) or 0)
                    cricket_auto["sixes"] += int(b.get("sixes", 0) or 0)
                    cricket_auto["highest_score"] = max(cricket_auto["highest_score"], int(b.get("runs", 0) or 0))
                    if b.get("out"):
                        cricket_auto["dismissals"] += 1
            for bw in side.get("bowlers") or []:
                if bw.get("player_id") == profile_id or bw.get("id") == profile_id:
                    if not counted:
                        cricket_auto["matches"] += 1
                        counted = True
                    cricket_auto["innings_bowled"] += 1
                    balls = int(bw.get("balls", 0) or 0) or int(float(bw.get("overs", 0) or 0) * 6)
                    cricket_auto["balls_bowled"] += balls
                    cricket_auto["runs_conceded"] += int(bw.get("runs_conceded", bw.get("runs", 0)) or 0)
                    cricket_auto["wickets"] += int(bw.get("wickets", 0) or 0)
    cricket_auto["overs_bowled"] = float(f"{cricket_auto['balls_bowled'] // 6}.{cricket_auto['balls_bowled'] % 6}")
    # Derived: average + strike rate + economy
    cricket_auto["batting_average"] = round(cricket_auto["runs"] / cricket_auto["dismissals"], 2) if cricket_auto["dismissals"] else None
    cricket_auto["strike_rate"] = round((cricket_auto["runs"] / cricket_auto["balls_faced"]) * 100, 2) if cricket_auto["balls_faced"] else None
    cricket_auto["bowling_economy"] = round((cricket_auto["runs_conceded"] / cricket_auto["balls_bowled"]) * 6, 2) if cricket_auto["balls_bowled"] else None
    cricket_auto["bowling_average"] = round(cricket_auto["runs_conceded"] / cricket_auto["wickets"], 2) if cricket_auto["wickets"] else None

    # Merge: manual overrides auto for fields the player explicitly entered.
    cricket_manual = manual.get("cricket") or {}
    result["cricket"] = {"auto": cricket_auto, "manual": cricket_manual}

    # ---- Other sports: pass-through manual data ----
    for sport, entries in manual.items():
        if sport == "cricket":
            continue
        result[sport] = {"auto": {}, "manual": entries or {}}

    # ---- Auto-aggregation for non-cricket sports ----
    # Walk every completed fixture where this player was rostered, group by
    # event.sport, and roll up simple counters. Rendered as chips on the
    # SportStatsDashboard next to any manual overrides the player entered.
    if team_ids:
        # Bulk-fetch events for team's fixtures so we don't hit the DB per row.
        fx_docs = await db.fixtures.find(
            {
                "status": "completed",
                "$or": [{"team_a_id": {"$in": team_ids}}, {"team_b_id": {"$in": team_ids}}],
            },
            {"_id": 0, "id": 1, "score": 1, "event_id": 1, "winner_id": 1,
             "awards": 1, "team_a_id": 1, "team_b_id": 1}
        ).to_list(2000)
        ev_ids = list({f["event_id"] for f in fx_docs})
        ev_docs = await db.events.find({"id": {"$in": ev_ids}}, {"_id": 0, "id": 1, "sport": 1}).to_list(2000)
        sport_by_event = {e["id"]: e.get("sport") or "" for e in ev_docs}
        per_sport: Dict[str, Dict[str, Any]] = {}
        for fx in fx_docs:
            sport = sport_by_event.get(fx["event_id"], "")
            if not sport or sport == "cricket":
                continue  # cricket already handled above; other sports fall through here.
            bucket = per_sport.setdefault(sport, {
                "matches": 0, "won": 0, "lost": 0, "draw": 0,
                "goals": 0, "points": 0, "sets_won": 0, "sets_lost": 0,
                "mom": 0, "top_scorer": 0,
            })
            bucket["matches"] += 1
            my_side_key = "team_a" if fx["team_a_id"] in team_ids else "team_b"
            my_team_id = fx["team_a_id"] if my_side_key == "team_a" else fx["team_b_id"]
            winner_id = fx.get("winner_id")
            if not winner_id:
                bucket["draw"] += 1
            elif winner_id == my_team_id:
                bucket["won"] += 1
            else:
                bucket["lost"] += 1
            my_side = (fx.get("score") or {}).get(my_side_key) or {}
            opp_side = (fx.get("score") or {}).get("team_b" if my_side_key == "team_a" else "team_a") or {}
            # Racket sports store `sets: [...]`. Count sets won as sum(my > opp).
            if isinstance(my_side.get("sets"), list) and isinstance(opp_side.get("sets"), list):
                for i in range(min(len(my_side["sets"]), len(opp_side["sets"]))):
                    if (my_side["sets"][i] or 0) > (opp_side["sets"][i] or 0):
                        bucket["sets_won"] += 1
                    elif (opp_side["sets"][i] or 0) > (my_side["sets"][i] or 0):
                        bucket["sets_lost"] += 1
            # Per-player scorers list (football, basketball, etc.).
            for s in my_side.get("scorers") or []:
                if s.get("player_id") == profile_id or s.get("id") == profile_id:
                    bucket["goals"] += int(s.get("goals", 0) or 0)
                    bucket["points"] += int(s.get("points", 0) or s.get("score", 0) or 0)
            # Award chips
            awards = fx.get("awards") or {}
            for key in ("mom", "top_scorer"):
                who = awards.get(key)
                pid = who.get("player_id") if isinstance(who, dict) else who
                if pid == profile_id:
                    bucket[key] += 1
        # Merge into result.
        for sport, bag in per_sport.items():
            # Drop empty counters so the UI shows a "No stats yet" state cleanly.
            clean = {k: v for k, v in bag.items() if v}
            existing = result.get(sport) or {"auto": {}, "manual": manual.get(sport) or {}}
            existing["auto"] = clean
            result[sport] = existing

    return result


@api.get("/players/by-slug/{slug}")
async def get_player_by_slug(slug: str, user: Optional[dict] = Depends(get_current_user_optional)):
    """Resolve a pretty share URL (e.g. `/p/rahul-shingi`) → full profile.

    Same redaction rules as `/players/profiles/{id}` for anonymous viewers.
    """
    doc = await db.player_profiles.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Profile not found")
    is_self = user and user.get("id") == doc.get("user_id")
    if not is_self:
        await db.player_profiles.update_one({"slug": slug}, {"$inc": {"view_count": 1}})
        doc["view_count"] = (doc.get("view_count", 0) or 0) + 1
        m = doc.get("mobile") or ""
        doc["mobile_masked"] = "•••• " + m[-4:] if len(m) >= 4 else m
        doc.pop("mobile", None)
        if not user:
            doc.pop("email", None)
            doc.pop("dob", None)
    return doc


@api.get("/players/profiles/{profile_id}")
async def get_player_profile(profile_id: str, user: Optional[dict] = Depends(get_current_user_optional)):
    doc = await db.player_profiles.find_one({"id": profile_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Profile not found")
    is_self = user and user.get("id") == doc.get("user_id")
    if not is_self:
        await db.player_profiles.update_one({"id": profile_id}, {"$inc": {"view_count": 1}})
        doc["view_count"] = (doc.get("view_count", 0) or 0) + 1
        m = doc.get("mobile") or ""
        doc["mobile_masked"] = "•••• " + m[-4:] if len(m) >= 4 else m
        doc.pop("mobile", None)
        # Extra privacy for logged-out viewers.
        if not user:
            doc.pop("email", None)
            doc.pop("dob", None)
    return doc


# ---------- Vendors / Vendor Listings are wired via routes/vendors.py at bottom ----------
@api.get("/admin/vendors/{vendor_id}/detail")
async def admin_vendor_detail(vendor_id: str, _: dict = Depends(require_platform_admin)):
    vendor = await db.vendors.find_one({"id": vendor_id}, {"_id": 0})
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    listings = await db.vendor_listings.find({"vendor_id": vendor_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    bookings = await db.vendor_bookings.find({"vendor_id": vendor_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    reviews = await db.reviews.find({"vendor_id": vendor_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    schedules = await db.venue_schedules.find(
        {"listing_id": {"$in": [L["id"] for L in listings]}}, {"_id": 0}
    ).to_list(200) if listings else []
    owner = await db.users.find_one({"id": vendor.get("user_id")}, {"_id": 0, "password_hash": 0}) if vendor.get("user_id") else None
    return {
        "vendor": vendor,
        "owner": owner,
        "listings": listings,
        "bookings": bookings,
        "reviews": reviews,
        "schedules": schedules,
    }


@api.get("/admin/companies/{company_id}/detail")
async def admin_company_detail(company_id: str, _: dict = Depends(require_platform_admin)):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(404, "Company not found")
    members = await db.users.find(
        {"company_id": company_id}, {"_id": 0, "password_hash": 0}
    ).sort("role", 1).to_list(500)
    players = await db.player_profiles.find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    bookings = await db.vendor_bookings.find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    events = await db.events.find({"company_id": company_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {
        "company": company,
        "members": members,
        "players": players,
        "bookings": bookings,
        "events": events,
    }


@api.get("/admin/players/{player_id}/detail")
async def admin_player_detail(player_id: str, _: dict = Depends(require_platform_admin)):
    profile = await db.player_profiles.find_one({"id": player_id}, {"_id": 0})
    if not profile:
        raise HTTPException(404, "Player not found")
    user = await db.users.find_one({"id": profile.get("user_id")}, {"_id": 0, "password_hash": 0}) if profile.get("user_id") else None
    company = await db.companies.find_one({"id": profile.get("company_id")}, {"_id": 0}) if profile.get("company_id") else None
    teams = await db.teams.find({"members": profile["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    event_ids = list({t.get("event_id") for t in teams if t.get("event_id")})
    events = await db.events.find({"id": {"$in": event_ids}}, {"_id": 0}).to_list(200) if event_ids else []
    reviews = await db.reviews.find({"author_user_id": profile.get("user_id")}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {
        "player": profile,
        "user": user,
        "company": company,
        "teams": teams,
        "events": events,
        "reviews": reviews,
    }


# ---------- Vendor listings + admin approval are wired via routes/vendors.py ----------


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


async def _guard_slot_conflict(
    listing_id: str, date: str, start: str, end: str,
    sub_unit_id: Optional[str] = None, exclude_booking_id: Optional[str] = None,
) -> None:
    """Reject if the [start, end) window on `date` overlaps with any of:
      • existing platform booking (vendor_bookings) in pending/accepted/confirmed
      • vendor's own offline walk-in (private_bookings) not cancelled/expired
      • explicit vendor block (venue_blocks)

    Applied on BOTH `POST /vendor-bookings` (platform) and
    `POST /vendor/private-bookings` (offline) so vendors and platform buyers
    can't race each other into the same slot.
    """
    def _ov(a_s, a_e, b_s, b_e):
        return a_s < (b_e or "24:00") and (a_e or "24:00") > (b_s or "00:00")
    sub_flt = {"sub_unit_id": sub_unit_id} if sub_unit_id else {}
    online_flt = {
        "listing_id": listing_id, "requested_date": date,
        "status": {"$in": ["pending", "vendor_accepted", "confirmed"]},
        **sub_flt,
    }
    if exclude_booking_id:
        online_flt["id"] = {"$ne": exclude_booking_id}
    for b in await db.vendor_bookings.find(online_flt, {"_id": 0, "start_time": 1, "end_time": 1}).to_list(200):
        if _ov(start, end, b.get("start_time"), b.get("end_time")):
            raise HTTPException(409, "That slot has just been booked online — pick another slot.")
    for b in await db.private_bookings.find({
        "listing_id": listing_id, "requested_date": date,
        "status": {"$nin": ["cancelled", "expired"]},
        **sub_flt,
    }, {"_id": 0, "start_time": 1, "end_time": 1}).to_list(200):
        if _ov(start, end, b.get("start_time"), b.get("end_time")):
            raise HTTPException(409, "The vendor has an offline booking on this slot — pick another.")
    for b in await db.venue_blocks.find({
        "listing_id": listing_id, "date": date, **sub_flt,
    }, {"_id": 0, "start_time": 1, "end_time": 1, "reason": 1}).to_list(200):
        if _ov(start, end, b.get("start_time"), b.get("end_time")):
            raise HTTPException(409, f"That slot is blocked by the vendor ({b.get('reason', 'unavailable')}).")



def _reject_past_slot(requested_date: str, start_time: str) -> None:
    """Defence-in-depth: reject any booking/reschedule slot in the past.

    Compares against the server's current UTC time. We treat the booking slot as
    naive local-time stored as YYYY-MM-DD + HH:MM; a 1-hour grace window
    absorbs minor clock skew between client and server."""
    try:
        slot = datetime.fromisoformat(f"{requested_date}T{start_time}")
    except ValueError:
        raise HTTPException(400, "Invalid date/time format")
    # Strip tzinfo for naive compare; users pick local clock times.
    now = datetime.utcnow()
    if slot < now - timedelta(hours=1):
        raise HTTPException(400, "Booking slot cannot be in the past")



def _resolve_booking_sport(body_sport: Optional[str], listing_sports: list) -> Optional[str]:
    if body_sport and body_sport in listing_sports:
        return body_sport
    return listing_sports[0] if listing_sports else None


async def _require_vendor_buyer(user: dict = Depends(get_current_user)) -> dict:
    """Anyone who can send a vendor booking request: company_admin, player, organiser."""
    if user.get("role") not in ("company_admin", "player", "organiser"):
        raise HTTPException(403, "Only company admins, players or organisers can book vendors")
    return user


@api.post("/vendor-bookings")
async def request_vendor_booking(body: VendorBookingRequest, user: dict = Depends(_require_vendor_buyer)):
    listing = await db.vendor_listings.find_one({"id": body.listing_id, "approved": True, "active": True}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not available")
    _reject_past_slot(body.requested_date, body.start_time)
    company = None
    if user.get("company_id"):
        company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})

    end_time, hours = _normalize_booking_time(body.start_time, body.end_time, body.hours)
    # Slot conflict check — prevent double-booking across ALL sources
    # (platform online, vendor offline walk-ins, and explicit vendor blocks).
    # The frontend uses /availability to render slots, but this is the
    # authoritative server-side guard against simultaneous booking attempts.
    await _guard_slot_conflict(
        listing_id=listing["id"], date=body.requested_date,
        start=body.start_time, end=end_time, sub_unit_id=body.sub_unit_id,
    )
    price = float(listing["price"])
    total_price = price * hours
    sport = _resolve_booking_sport(body.sport, listing.get("sports") or [])
    applied_membership_id = None

    # --- Apply membership (Phase 3) ---------------------------------------
    if body.apply_membership_id:
        mem = await db.membership_purchases.find_one({
            "id": body.apply_membership_id,
            "buyer_user_id": user["id"],
            "status": "active",
        }, {"_id": 0})
        if not mem:
            raise HTTPException(400, "Membership not found, not yours, or not active")
        # Plan must cover this listing (either explicit list or vendor-wide)
        plan = await db.membership_plans.find_one({"id": mem["plan_id"]}, {"_id": 0}) or {}
        plan_listings = plan.get("listing_ids") or []
        if plan_listings and listing["id"] not in plan_listings:
            raise HTTPException(400, "Your membership doesn't cover this listing")
        if plan.get("vendor_id") and plan["vendor_id"] != listing["vendor_id"]:
            raise HTTPException(400, "Your membership belongs to a different vendor")
        # Has the membership expired?
        if mem.get("expires_at") and mem["expires_at"] < datetime.now(timezone.utc).isoformat():
            raise HTTPException(400, "Membership has expired — please renew before applying")
        # Free until max_bookings reached
        max_b = mem.get("max_bookings")
        used = int(mem.get("bookings_used", 0))
        if max_b is not None and used >= int(max_b):
            raise HTTPException(400, f"Membership already used its {max_b} included bookings — pay hourly or upgrade")
        # All good — free slot
        total_price = 0.0
        applied_membership_id = mem["id"]

    # Business-model: skip commission when the buyer is a player who was the
    # vendor's offline customer BEFORE joining the platform (vendor-invited via
    # ref link → player.offline_source_vendor_id set).
    offline_source = False
    if user.get("role") == "player":
        pp = await db.player_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "offline_source_vendor_id": 1})
        if pp and pp.get("offline_source_vendor_id") == listing["vendor_id"]:
            offline_source = True
    # ---- Per-vendor commission (Task 44 Feb 2026) ----
    # Vendor's `commission_percent` + `commission_min_flat` set at approval
    # time govern the platform's take. Effective commission = max(gross * pct
    # / 100, flat). Falls back to site-wide default (10% / ₹100) when vendor
    # has legacy null fields.
    vendor_doc = await db.vendors.find_one({"id": listing["vendor_id"]}, {"_id": 0, "commission_percent": 1, "commission_min_flat": 1}) or {}
    commission_percent = float(vendor_doc.get("commission_percent") if vendor_doc.get("commission_percent") is not None else 10.0)
    commission_flat = float(vendor_doc.get("commission_min_flat") if vendor_doc.get("commission_min_flat") is not None else 100.0)
    if offline_source:
        commission_percent = 0
        commission_flat = 0
    # Note: per-occurrence commission is computed inside the loop below as
    # `this_commission`, since a recurring series may include a membership-paid
    # first occurrence (zero commission) alongside hourly-paid subsequent ones.

    # -------- Compute the list of dates to create bookings for --------
    # For a plain booking this is `[requested_date]`. For a weekly recurring
    # booking, we expand into one date per matching weekday from
    # requested_date through recurrence_until (inclusive).
    dates: List[str] = []
    if body.recurrence == "weekly" and body.recurrence_until:
        try:
            first = datetime.strptime(body.requested_date, "%Y-%m-%d").date()
            until = datetime.strptime(body.recurrence_until, "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(400, "Invalid requested_date or recurrence_until (use YYYY-MM-DD)")
        if until < first:
            raise HTTPException(400, "recurrence_until must be on or after requested_date")
        days = set(body.recurrence_days_of_week or [first.weekday()])
        d = first
        one_day = timedelta(days=1)
        while d <= until:
            if d.weekday() in days:
                dates.append(d.strftime("%Y-%m-%d"))
            d += one_day
        if not dates:
            raise HTTPException(400, "Recurrence produced zero occurrences — check days_of_week vs date range")
        if len(dates) > 52:
            raise HTTPException(400, "Recurrence limited to 52 occurrences at a time — please split into shorter series")
    else:
        dates = [body.requested_date]

    group_id = str(uuid.uuid4()) if len(dates) > 1 else None
    created: List[dict] = []
    for i, dt in enumerate(dates):
        # Membership can only pay for the FIRST occurrence — subsequent
        # occurrences fall back to hourly pricing so the buyer isn't accidentally
        # billed against a single membership counter for 4 slots.
        this_price = total_price if i == 0 else (price * hours)
        this_membership = applied_membership_id if i == 0 else None
        # max(pct * price, flat). Membership-covered slots waive commission.
        _pct_amt = float(this_price) * commission_percent / 100.0
        this_commission = round(max(_pct_amt, commission_flat if float(this_price) > 0 else 0), 2)
        booking = VendorBooking(
            listing_id=listing["id"], listing_title=listing["title"],
            vendor_id=listing["vendor_id"], vendor_type=listing["vendor_type"],
            company_id=user.get("company_id") or "",
            company_name=(company or {}).get("name") or user.get("name") or user.get("email") or "Player",
            requested_date=dt, start_time=body.start_time, end_time=end_time,
            hours=hours, sport=sport, city=listing.get("city"), sub_unit_id=body.sub_unit_id,
            price=price, currency=listing.get("currency", "INR"), total=this_price,
            notes=body.notes or "", created_by=user["id"], hr_email=user.get("email"),
            applied_membership_id=this_membership,
            offline_source=offline_source,
            commission_percent=commission_percent if not this_membership else 0,
            commission_amount=this_commission if not this_membership else 0,
            commission_min_flat=commission_flat if not this_membership else 0,
            recurrence_group_id=group_id,
        )
        payload = booking.model_dump()
        payload["notifications"] = [_booking_notification(
            "created",
            (f"Request submitted for {listing['title']} on {dt} {body.start_time} ({hours}h)."
             + (" Paid via membership." if this_membership else "")
             + (f" · Series {i+1}/{len(dates)}." if group_id else "")),
            user,
        )]
        await db.vendor_bookings.insert_one(payload)
        created.append(payload)
        if this_membership:
            await db.membership_purchases.update_one(
                {"id": this_membership}, {"$inc": {"bookings_used": 1}}
            )
    logger.warning(
        "BOOKING NOTIFICATION for %s | series=%s | count=%d | listing=%s",
        user.get("email"), group_id, len(created), listing["title"],
    )
    # For a single booking, keep the legacy shape (single object). For a
    # recurring series, return a summary so the client can show the count.
    if group_id:
        return {"recurrence_group_id": group_id, "count": len(created), "bookings": [VendorBooking(**b).model_dump() for b in created]}
    return VendorBooking(**created[0])


def _mask_for_vendor(doc: dict) -> dict:
    """Privacy mask — vendors see KN-originated booking customers only by name.

    They keep visibility of `company_name`, the slot data, total + status. Email,
    phone, free-text notes (which may contain personal info) and the `created_by`
    user_id are stripped so vendor-side reports don't leak HR PII. Internal IDs
    (booking id, listing id, vendor id) are preserved for joins.
    """
    masked = dict(doc)
    masked["hr_email"] = None
    masked["created_by"] = ""
    masked["notes"] = ""
    return masked


@api.get("/vendor-bookings", response_model=List[VendorBooking])
async def list_vendor_bookings(user: dict = Depends(get_current_user)):
    from routes.booking_lifecycle import sweep_online_bookings
    role = user.get("role")
    if role == "vendor":
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        flt = {"vendor_id": vendor["id"]} if vendor else {"vendor_id": "__none__"}
    elif role == "company_admin":
        flt = {"company_id": user.get("company_id")}
    elif role in ("player", "organiser"):
        # Players + organisers see the bookings they themselves created.
        flt = {"created_by": user["id"]}
    elif role in ("platform_admin", "admin"):
        flt = {}
    else:
        raise HTTPException(403, "Forbidden")
    docs = await db.vendor_bookings.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
    # Auto-expire any elapsed active bookings (4h grace) BEFORE returning.
    docs = await sweep_online_bookings(db, docs)
    if role == "vendor":
        docs = [_mask_for_vendor(d) for d in docs]
    return [VendorBooking(**d) for d in docs]


@api.post("/vendor-bookings/{booking_id}/check-in", response_model=VendorBooking)
async def check_in_vendor_booking(booking_id: str, user: dict = Depends(get_current_user)):
    """Vendor confirms the customer arrived. Marks status=completed."""
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    role = user.get("role")
    if role == "vendor":
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor or doc["vendor_id"] != vendor["id"]:
            raise HTTPException(403, "Not your booking")
    elif role not in ("platform_admin", "admin"):
        raise HTTPException(403, "Only the vendor or platform admin can mark arrival")
    if doc.get("status") in ("cancelled", "rejected", "expired", "no_show"):
        raise HTTPException(400, f"Booking is {doc['status']} — cannot mark arrival")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.vendor_bookings.update_one(
        {"id": booking_id},
        {"$set": {"status": "completed", "completed_at": now_iso,
                  "checked_in_at": now_iso, "checked_in_by": user["id"]}},
    )
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    return VendorBooking(**doc)


@api.post("/vendor-bookings/{booking_id}/no-show", response_model=VendorBooking)
async def mark_no_show_vendor_booking(booking_id: str, user: dict = Depends(get_current_user)):
    """Vendor / admin explicitly marks a booking as customer no-show."""
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    role = user.get("role")
    if role == "vendor":
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor or doc["vendor_id"] != vendor["id"]:
            raise HTTPException(403, "Not your booking")
    elif role not in ("platform_admin", "admin"):
        raise HTTPException(403, "Only the vendor or platform admin can mark a no-show")
    if doc.get("status") in ("cancelled", "rejected", "completed"):
        raise HTTPException(400, f"Booking is {doc['status']} — cannot mark no-show")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.vendor_bookings.update_one(
        {"id": booking_id},
        {"$set": {"status": "expired", "no_show_at": now_iso}},
    )
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    return VendorBooking(**doc)


@api.post("/vendor-bookings/{booking_id}/reopen", response_model=VendorBooking)
async def reopen_vendor_booking(booking_id: str, user: dict = Depends(get_current_user)):
    """Revert a wrongly-expired platform booking back to confirmed so the vendor
    can then check-in / complete it. Vendor or platform admin only."""
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    role = user.get("role")
    if role == "vendor":
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor or doc["vendor_id"] != vendor["id"]:
            raise HTTPException(403, "Not your booking")
    elif role not in ("platform_admin", "admin"):
        raise HTTPException(403, "Only the vendor or platform admin can reopen a booking")
    if doc.get("status") not in ("expired", "no_show", "cancelled"):
        raise HTTPException(400, f"Only expired/cancelled bookings can be reopened (current: {doc.get('status')})")
    await db.vendor_bookings.update_one(
        {"id": booking_id},
        {"$set": {"status": "confirmed"}, "$unset": {"no_show_at": "", "completed_at": ""}},
    )
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    return VendorBooking(**doc)


def _time_to_minutes(hhmm: str) -> int:
    try:
        h, m = (hhmm or "0:0").split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return 0


def _ceil_to_block(minutes: int, block: int) -> int:
    if minutes <= 0:
        return 0
    block = max(1, int(block or 15))
    return ((int(minutes) + block - 1) // block) * block


@api.post("/vendor-bookings/{booking_id}/complete", response_model=VendorBooking)
async def complete_vendor_booking(booking_id: str, body: dict = None, user: dict = Depends(get_current_user)):
    """Complete a platform booking with optional overtime capture.
    Body: `{actual_end_time?: "HH:MM", overtime_note?: str}`.

    Computes:
      overtime_minutes  = actual_end - booked_end (ceil to vendor block).
      overtime_amount   = billed_hours × listing_rate_per_hour × multiplier.
      overtime_commission_amount = overtime_amount × commission_percent%.
    """
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Booking not found")
    role = user.get("role")
    vendor_doc = None
    if role == "vendor":
        vendor_doc = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor_doc or doc["vendor_id"] != vendor_doc["id"]:
            raise HTTPException(403, "Not your booking")
    elif role not in ("platform_admin", "admin"):
        raise HTTPException(403, "Only the vendor or platform admin can complete a booking")
    if doc.get("status") in ("cancelled", "rejected", "completed"):
        raise HTTPException(400, f"Booking is {doc['status']}")
    if vendor_doc is None:
        vendor_doc = await db.vendors.find_one({"id": doc["vendor_id"]}, {"_id": 0}) or {}
    body = body or {}
    actual_end = (body.get("actual_end_time") or "").strip() or doc.get("end_time")
    overtime_raw = max(0, _time_to_minutes(actual_end) - _time_to_minutes(doc.get("end_time")))
    block = int(vendor_doc.get("overtime_block_minutes") or 15)
    multiplier = float(vendor_doc.get("overtime_charge_multiplier") or 1.0)
    overtime_minutes = _ceil_to_block(overtime_raw, block)
    rate_per_hour = float(doc.get("price") or 0)
    overtime_amount = round((overtime_minutes / 60.0) * rate_per_hour * multiplier, 2)
    commission_pct = float(doc.get("commission_percent") or 0)
    overtime_commission = round(overtime_amount * commission_pct / 100.0, 2) if not doc.get("offline_source") else 0
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.vendor_bookings.update_one(
        {"id": booking_id},
        {"$set": {
            "status": "completed",
            "completed_at": now_iso,
            "checked_in_at": doc.get("checked_in_at") or now_iso,
            "checked_in_by": user["id"],
            "arrived_at": doc.get("arrived_at") or doc.get("checked_in_at") or now_iso,
            "actual_end_time": actual_end,
            "overtime_minutes": overtime_minutes,
            "overtime_amount": overtime_amount,
            "overtime_commission_amount": overtime_commission,
            "overtime_note": body.get("overtime_note", ""),
        }},
    )
    doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
    return VendorBooking(**doc)


VENDOR_STATUSES = {"vendor_accepted", "vendor_declined"}
ADMIN_STATUSES = {"confirmed", "rejected", "completed"}
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


# ---------- Reviews & Ratings (vendor moderation -> admin moderation -> public) ----------
@api.post("/vendor-listings/{listing_id}/reviews", response_model=Review)
async def create_review(listing_id: str, body: dict, user: dict = Depends(get_current_user)):
    rating = int(body.get("rating") or 0)
    if rating < 1 or rating > 5:
        raise HTTPException(400, "rating must be between 1 and 5")
    text = (body.get("text") or "").strip()
    booking_id = body.get("booking_id")
    listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not found")
    # Require a completed booking owned by the reviewer (player / HR) to allow review
    if booking_id:
        booking = await db.vendor_bookings.find_one({"id": booking_id, "listing_id": listing_id}, {"_id": 0})
        if not booking:
            raise HTTPException(400, "Booking does not belong to this listing")
        if booking.get("status") != "completed":
            raise HTTPException(400, "You can only review completed bookings")
        if booking.get("company_id") != user.get("company_id") and booking.get("created_by") != user.get("id"):
            raise HTTPException(403, "Not your booking")
        existing = await db.reviews.find_one({"booking_id": booking_id, "author_user_id": user["id"]}, {"_id": 0})
        if existing:
            raise HTTPException(400, "You already reviewed this booking")
    review = Review(
        listing_id=listing_id,
        vendor_id=listing["vendor_id"],
        booking_id=booking_id,
        author_user_id=user["id"],
        author_name=user.get("name") or user.get("email") or "User",
        author_role=user.get("role") or "player",
        rating=rating,
        text=text[:2000],
    )
    await db.reviews.insert_one(review.model_dump())
    # Notify vendor for moderation
    vendor_user = await db.users.find_one({"vendor_id": listing["vendor_id"], "role": "vendor"}, {"_id": 0, "email": 1}) or {}
    if vendor_user.get("email"):
        send_email(vendor_user["email"], f"New review awaiting your response — {listing['title']}",
                   f"{review.author_name} left a {rating}/5 review:\n\n{text[:200]}\n\nApprove or flag it from your vendor dashboard.",
                   kind="review_pending_vendor")
    return review


@api.get("/vendor-listings/{listing_id}/reviews")
async def list_listing_reviews(listing_id: str, include_pending: bool = False, user: Optional[dict] = Depends(get_current_user_optional)):
    """Public route: by default returns only `visible` reviews. Vendor or platform admin can pass include_pending=true to see all."""
    flt = {"listing_id": listing_id}
    if not include_pending:
        flt["status"] = "visible"
    else:
        # Authorize: must be vendor owner or platform admin
        listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(404, "Listing not found")
        if not user:
            raise HTTPException(401, "Auth required to view pending reviews")
        role = user.get("role")
        if role not in ("platform_admin", "admin"):
            v = await db.vendors.find_one({"user_id": user.get("id")}, {"_id": 0}) or {}
            if v.get("id") != listing["vendor_id"]:
                raise HTTPException(403, "Not allowed to view pending reviews")
    docs = await db.reviews.find(flt, {"_id": 0}).sort("created_at", -1).to_list(200)
    # Compute rating summary (visible only) for the listing
    if not include_pending:
        agg = await db.reviews.aggregate([
            {"$match": {"listing_id": listing_id, "status": "visible"}},
            {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
        ]).to_list(1)
        summary = agg[0] if agg else {"avg": 0, "count": 0}
        return {"reviews": docs, "summary": {"average": round(summary.get("avg") or 0, 2), "count": summary.get("count") or 0}}
    return {"reviews": docs}


@api.post("/reviews/{review_id}/respond")
async def vendor_review_response(review_id: str, body: dict, user: dict = Depends(get_current_user)):
    """Vendor approves/rejects or appends a public response to a pending review."""
    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(404, "Review not found")
    listing = await db.vendor_listings.find_one({"id": review["listing_id"]}, {"_id": 0}) or {}
    v = await db.vendors.find_one({"user_id": user.get("id")}, {"_id": 0}) or {}
    if user.get("role") != "vendor" or v.get("id") != listing.get("vendor_id"):
        raise HTTPException(403, "Only the listing's vendor can respond")
    action = body.get("action")  # "approve" | "flag" | "respond"
    upd = {}
    if action == "approve":
        if review["status"] != "pending_vendor":
            raise HTTPException(400, "Review already moderated")
        upd["status"] = "pending_admin"  # next step: admin moderation
        upd["moderated_by_role"] = "vendor"
        upd["moderated_at"] = datetime.now(timezone.utc).isoformat()
    elif action == "flag":
        upd["status"] = "flagged"
        upd["moderation_note"] = (body.get("note") or "")[:500]
        upd["moderated_by_role"] = "vendor"
        upd["moderated_at"] = datetime.now(timezone.utc).isoformat()
    elif action == "respond":
        upd["vendor_response"] = (body.get("response") or "")[:1500]
    else:
        raise HTTPException(400, "action must be approve, flag, or respond")
    await db.reviews.update_one({"id": review_id}, {"$set": upd})
    return await db.reviews.find_one({"id": review_id}, {"_id": 0})


@api.post("/admin/reviews/{review_id}/moderate")
async def admin_moderate_review(review_id: str, body: dict, _: dict = Depends(require_permission("manage_reviews"))):
    """Platform admin final verdict: publish (visible), reject, or override flag."""
    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(404, "Review not found")
    action = body.get("action")  # "publish" | "reject"
    upd = {
        "moderated_by_role": "platform_admin",
        "moderated_at": datetime.now(timezone.utc).isoformat(),
    }
    if action == "publish":
        upd["status"] = "visible"
    elif action == "reject":
        upd["status"] = "rejected"
        upd["moderation_note"] = (body.get("note") or "")[:500]
    else:
        raise HTTPException(400, "action must be publish or reject")
    await db.reviews.update_one({"id": review_id}, {"$set": upd})
    return await db.reviews.find_one({"id": review_id}, {"_id": 0})


@api.get("/admin/reviews/queue")
async def admin_reviews_queue(_: dict = Depends(require_platform_admin)):
    docs = await db.reviews.find(
        {"status": {"$in": ["pending_admin", "flagged"]}}, {"_id": 0}
    ).sort("moderated_at", -1).to_list(200)
    return docs


# ---------- Staff admin management (super-admin only) ----------
class StaffAdminCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    permissions: List[str] = Field(default_factory=list)


class StaffAdminUpdate(BaseModel):
    name: Optional[str] = None
    permissions: Optional[List[str]] = None
    password: Optional[str] = None


def _staff_admin_public(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "email": doc["email"],
        "name": doc.get("name", ""),
        "role": doc.get("role", "platform_admin"),
        "is_super_admin": bool(doc.get("is_super_admin")),
        "permissions": list(doc.get("permissions") or []),
        "created_at": doc.get("created_at"),
    }


@api.get("/admin/permissions/me")
async def my_admin_permissions(user: dict = Depends(require_platform_admin)):
    """Return the calling admin's permissions + super flag (used by FE to gate UI)."""
    return {
        "id": user["id"],
        "email": user["email"],
        "is_super_admin": bool(user.get("is_super_admin")),
        "permissions": list(ALL_PERMISSIONS) if user.get("is_super_admin") else list(user.get("permissions") or []),
        "all_permissions": list(ALL_PERMISSIONS),
    }


@api.get("/admin/staff")
async def list_staff_admins(_: dict = Depends(require_super_admin)):
    docs = await db.users.find(
        {"role": "platform_admin"}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(200)
    return [_staff_admin_public(d) for d in docs]


@api.post("/admin/staff")
async def create_staff_admin(body: StaffAdminCreate, _: dict = Depends(require_super_admin)):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    invalid = [p for p in (body.permissions or []) if p not in ALL_PERMISSIONS]
    if invalid:
        raise HTTPException(400, f"Invalid permissions: {invalid}")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": email,
        "name": body.name.strip() or email.split("@")[0],
        "role": "platform_admin",
        "is_super_admin": False,
        "permissions": list(body.permissions or []),
        "company_id": None,
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    logger.info("STAFF ADMIN CREATED | %s | perms=%s", email, doc["permissions"])
    # Mock invite "email" — surface credentials so super admin can share them
    return {
        "ok": True,
        "admin": _staff_admin_public(doc),
        "invite": {
            "email": email,
            "temp_password": body.password,
            "login_url": "/login",
            "note": "Share these credentials with the new admin. They can change their password from the profile after sign-in.",
        },
    }


@api.patch("/admin/staff/{admin_id}")
async def update_staff_admin(admin_id: str, body: StaffAdminUpdate, _: dict = Depends(require_super_admin)):
    target = await db.users.find_one({"id": admin_id, "role": "platform_admin"}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Admin not found")
    if target.get("is_super_admin"):
        raise HTTPException(400, "Cannot modify the super admin account from this endpoint")
    upd = {}
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.permissions is not None:
        invalid = [p for p in body.permissions if p not in ALL_PERMISSIONS]
        if invalid:
            raise HTTPException(400, f"Invalid permissions: {invalid}")
        upd["permissions"] = list(body.permissions)
    if body.password is not None:
        if len(body.password) < 6:
            raise HTTPException(400, "Password must be at least 6 characters")
        upd["password_hash"] = hash_password(body.password)
    if upd:
        await db.users.update_one({"id": admin_id}, {"$set": upd})
    doc = await db.users.find_one({"id": admin_id}, {"_id": 0, "password_hash": 0})
    return _staff_admin_public(doc)


@api.delete("/admin/staff/{admin_id}")
async def delete_staff_admin(admin_id: str, user: dict = Depends(require_super_admin)):
    target = await db.users.find_one({"id": admin_id, "role": "platform_admin"}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Admin not found")
    if target.get("is_super_admin"):
        raise HTTPException(400, "Cannot delete the super admin account")
    if target["id"] == user["id"]:
        raise HTTPException(400, "Cannot delete yourself")
    await db.users.delete_one({"id": admin_id})
    logger.info("STAFF ADMIN DELETED | %s", target.get("email"))
    return {"ok": True}


# ---------- Account suspension (uniform for organisers / vendors / players / company admins) ----------
# Roles a platform admin is allowed to disable. Platform admins themselves are managed via /admin/staff.
SUSPENDABLE_ROLES = {"organiser", "vendor", "player", "company_admin", "sponsor", "scorer"}


@api.get("/admin/users")
async def admin_list_users(role: str | None = None, _: dict = Depends(require_platform_admin)):
    """List user accounts with optional ?role= filter. Returns disabled state + company name for context."""
    query: dict = {"role": {"$in": list(SUSPENDABLE_ROLES)}}
    if role:
        if role not in SUSPENDABLE_ROLES:
            raise HTTPException(400, f"Unsupported role filter. Allowed: {sorted(SUSPENDABLE_ROLES)}")
        query["role"] = role
    docs = await db.users.find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(2000)
    # Enrich with company name (organisers + company_admins) and vendor business name where applicable.
    company_ids = list({d.get("company_id") for d in docs if d.get("company_id")})
    companies = {}
    if company_ids:
        async for c in db.companies.find({"id": {"$in": company_ids}}, {"_id": 0, "id": 1, "name": 1, "org_type": 1}):
            companies[c["id"]] = c
    vendor_user_ids = [d["id"] for d in docs if d.get("role") == "vendor"]
    vendor_map = {}
    if vendor_user_ids:
        async for v in db.vendors.find({"user_id": {"$in": vendor_user_ids}}, {"_id": 0, "user_id": 1, "id": 1, "business_name": 1, "vendor_type": 1, "approved": 1}):
            vendor_map[v["user_id"]] = v

    # Enrich player accounts with their player_profile id so the admin UI can deep-link
    # straight to /players/{id} on click.
    player_user_ids = [d["id"] for d in docs if d.get("role") == "player"]
    player_map = {}
    if player_user_ids:
        async for p in db.player_profiles.find(
            {"user_id": {"$in": player_user_ids}},
            {"_id": 0, "user_id": 1, "id": 1, "city": 1, "interested_sports": 1, "view_count": 1},
        ):
            player_map[p["user_id"]] = p

    # Sponsors: their profile is keyed by user_id directly.
    sponsor_user_ids = [d["id"] for d in docs if d.get("role") == "sponsor"]
    sponsor_map = {}
    if sponsor_user_ids:
        async for s in db.sponsor_profiles.find(
            {"user_id": {"$in": sponsor_user_ids}},
            {"_id": 0, "user_id": 1, "brand_name": 1, "industry": 1, "logo_url": 1, "location": 1},
        ):
            sponsor_map[s["user_id"]] = s

    # Scorers: list of events / fixtures they've been assigned to (count only).
    scorer_user_ids = [d["id"] for d in docs if d.get("role") == "scorer"]
    scorer_map = {}
    if scorer_user_ids:
        async for a in db.event_scorers.find(
            {"user_id": {"$in": scorer_user_ids}},
            {"_id": 0, "user_id": 1, "event_id": 1, "fixture_ids": 1},
        ):
            entry = scorer_map.setdefault(a["user_id"], {"assignments": 0, "fixtures": 0})
            entry["assignments"] += 1
            entry["fixtures"] += len(a.get("fixture_ids") or [])

    for d in docs:
        d["disabled"] = bool(d.get("disabled"))
        if d.get("company_id"):
            c = companies.get(d["company_id"]) or {}
            d["company_name"] = c.get("name")
            d["org_type"] = c.get("org_type")
        if d["role"] == "vendor":
            v = vendor_map.get(d["id"]) or {}
            d["vendor_id"] = v.get("id")
            d["vendor_business_name"] = v.get("business_name")
            d["vendor_type"] = v.get("vendor_type")
            d["vendor_approved"] = bool(v.get("approved"))
        if d["role"] == "player":
            p = player_map.get(d["id"]) or {}
            d["player_profile_id"] = p.get("id")
            d["player_city"] = p.get("city")
            d["player_sports"] = p.get("interested_sports") or []
            d["player_view_count"] = p.get("view_count") or 0
        if d["role"] == "sponsor":
            s = sponsor_map.get(d["id"]) or {}
            d["sponsor_brand_name"] = s.get("brand_name")
            d["sponsor_industry"] = s.get("industry")
            d["sponsor_logo_url"] = s.get("logo_url")
            d["sponsor_location"] = s.get("location")
        if d["role"] == "scorer":
            sc = scorer_map.get(d["id"]) or {"assignments": 0, "fixtures": 0}
            d["scorer_assignments"] = sc["assignments"]
            d["scorer_fixtures"] = sc["fixtures"]
    return docs


@api.patch("/admin/users/{user_id}/disabled")
async def admin_toggle_user_disabled(user_id: str, body: dict, actor: dict = Depends(require_platform_admin)):
    """Enable or disable a user account. Body: {disabled: bool}.

    Disabled users keep their data but cannot log in — they receive the canned admin-contact message.
    """
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target.get("role") not in SUSPENDABLE_ROLES:
        raise HTTPException(400, "This account type cannot be disabled here. Use /admin/staff for platform admins.")
    if target["id"] == actor["id"]:
        raise HTTPException(400, "You cannot disable your own account")
    disabled = bool((body or {}).get("disabled", True))
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "disabled": disabled,
            "disabled_at": datetime.now(timezone.utc).isoformat() if disabled else None,
            "disabled_by": actor["email"] if disabled else None,
        }},
    )
    logger.info("USER %s | %s | by=%s", "DISABLED" if disabled else "ENABLED", target.get("email"), actor.get("email"))
    return {"ok": True, "id": user_id, "disabled": disabled}


@api.get("/vendors/me/reviews")
async def vendor_pending_reviews(user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(403, "Vendor only")
    v = await db.vendors.find_one({"user_id": user.get("id")}, {"_id": 0})
    if not v:
        return []
    docs = await db.reviews.find(
        {"vendor_id": v["id"], "status": {"$in": ["pending_vendor", "pending_admin", "flagged"]}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    return docs


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
    # HR can cancel only their company's bookings; players/organisers only their own; admins all
    if role == "company_admin" and doc.get("company_id") != user.get("company_id"):
        raise HTTPException(403, "Not your booking")
    if role in ("player", "organiser") and doc.get("created_by") != user["id"]:
        raise HTTPException(403, "Not your booking")
    if role not in ("company_admin", "player", "organiser", "platform_admin", "admin"):
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
    if role in ("player", "organiser") and doc.get("created_by") != user["id"]:
        raise HTTPException(403, "Not your booking")
    if role not in ("company_admin", "player", "organiser", "platform_admin", "admin"):
        raise HTTPException(403, "Reschedule not allowed for this role")
    if doc.get("status") in ("cancelled", "declined", "completed"):
        raise HTTPException(400, "Booking cannot be rescheduled in its current state")

    new_date = (body.get("requested_date") or "").strip()
    new_start = (body.get("start_time") or "").strip()
    hours_arg = body.get("hours") or doc.get("hours") or 1
    if not (new_date and new_start):
        raise HTTPException(400, "requested_date and start_time are required")
    _reject_past_slot(new_date, new_start)

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


# ============================================================================
#  SPONSORSHIP MARKETPLACE — Phase 1: profiles, opportunities, interests
# ============================================================================
def _require_sponsor_or_company(user: dict = Depends(get_current_user)) -> dict:
    """Sponsorship browse + interest actions are open to dedicated sponsor users AND
    company admins (per product spec — companies can sponsor other organisers' events)."""
    if user.get("role") not in ("sponsor", "company_admin"):
        raise HTTPException(403, "Only sponsors or company admins can perform this action")
    return user


@api.post("/auth/sponsors/signup", response_model=UserPublic)
async def sponsor_signup(body: SponsorSignupBody, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "An account with this email already exists")
    mobile = (body.mobile or "").strip()
    if mobile and await db.users.find_one({"mobile": mobile}):
        raise HTTPException(400, "An account with this mobile number already exists")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id, "email": email, "name": body.contact_person or body.company_name,
        "role": "sponsor", "password_hash": hash_password(body.password),
        "email_verified": True, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if mobile:
        user_doc["mobile"] = mobile
    await db.users.insert_one(user_doc)
    profile = SponsorProfile(user_id=user_id, company_name=body.company_name.strip(), contact_person=body.contact_person or "")
    await db.sponsor_profiles.insert_one(profile.model_dump())
    token = create_access_token(user_id, email, "sponsor", None)
    set_auth_cookie(response, token)
    logger.info("SPONSOR SIGNUP | %s | %s", email, body.company_name)
    return UserPublic(id=user_id, email=email, name=body.contact_person or body.company_name, role="sponsor", company_id=None, company=None)


async def _resolve_sponsor_profile(user: dict) -> Optional[dict]:
    """Look up the sponsor profile for the current user. Auto-creates a stub for
    company admins so they can populate their sponsor-facing info on first visit."""
    profile = await db.sponsor_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if profile:
        return profile
    if user.get("role") == "company_admin":
        # Bootstrap an empty sponsor profile reusing the company name as default.
        company = await db.companies.find_one({"id": user.get("company_id")}, {"_id": 0, "name": 1})
        stub = SponsorProfile(user_id=user["id"], company_name=(company or {}).get("name") or user.get("name") or "Unnamed company")
        await db.sponsor_profiles.insert_one(stub.model_dump())
        return stub.model_dump()
    return None


@api.get("/sponsor-profile/me")
async def sponsor_get_me(user: dict = Depends(_require_sponsor_or_company)):
    profile = await _resolve_sponsor_profile(user)
    if not profile:
        raise HTTPException(404, "Sponsor profile not found")
    return profile


@api.patch("/sponsor-profile/me")
async def sponsor_update_me(body: dict, user: dict = Depends(_require_sponsor_or_company)):
    profile = await _resolve_sponsor_profile(user)
    if not profile:
        raise HTTPException(404, "Sponsor profile not found")
    EDITABLE = {"company_name", "contact_person", "industry", "location", "target_locations",
                "target_event_types", "target_audience", "budget_range", "website", "logo_url", "sponsor_interests"}
    updates = {k: v for k, v in (body or {}).items() if k in EDITABLE}
    if not updates:
        return profile
    await db.sponsor_profiles.update_one({"user_id": user["id"]}, {"$set": updates})
    profile.update(updates)
    return profile


def _opportunity_active_count(opp: dict) -> int:
    """Number of 'available' slots remaining for an opportunity. 'sold' slots are excluded."""
    return max(0, int(opp.get("quantity_available", 0)) - int(opp.get("sold_count", 0)))


@api.get("/events/{event_id}/sponsorships")
async def list_event_sponsorships(event_id: str):
    """Public — anyone (even not logged in) can browse the sponsorships of an event.
    Returns each opportunity with derived `slots_remaining` and `sold_to` list."""
    event = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(404, "Event not found")
    opps = event.get("sponsorship_opportunities") or []
    for o in opps:
        o["slots_remaining"] = _opportunity_active_count(o)
    return {
        "event_id": event_id,
        "event_name": event.get("name"),
        "accept_sponsorships": bool(event.get("accept_sponsorships")),
        "data_share_agreement": bool(event.get("data_share_agreement")),
        "requirements": event.get("sponsorship_requirements") or {},
        "opportunities": opps,
    }


async def _ensure_event_owner(event_id: str, user: dict) -> dict:
    """Platform admins, the event's owning company admin, and organisers of the event
    can mutate its sponsorship opportunities."""
    event = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(404, "Event not found")
    role = user.get("role")
    if role == "platform_admin":
        return event
    if role in ("company_admin", "organiser") and (event.get("company_id") == user.get("company_id")):
        return event
    raise HTTPException(403, "Not allowed to modify this event")


@api.post("/events/{event_id}/sponsorships")
async def add_event_sponsorship(event_id: str, body: dict, user: dict = Depends(get_current_user)):
    await _ensure_event_owner(event_id, user)
    name = (body or {}).get("name", "").strip()
    if not name:
        raise HTTPException(400, "Sponsorship name required")
    opp = {
        "id": str(uuid.uuid4()),
        "name": name,
        "type": body.get("type") or "associate",
        "price": float(body.get("price") or 0),
        "currency": body.get("currency") or "INR",
        "quantity_available": int(body.get("quantity_available") or 1),
        "sold_count": 0,
        "benefits": body.get("benefits") or "",
        "status": "available",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.events.update_one({"id": event_id}, {"$push": {"sponsorship_opportunities": opp}})
    return opp


@api.patch("/events/{event_id}/sponsorships/{opp_id}")
async def update_event_sponsorship(event_id: str, opp_id: str, body: dict, user: dict = Depends(get_current_user)):
    event = await _ensure_event_owner(event_id, user)
    opps = event.get("sponsorship_opportunities") or []
    idx = next((i for i, o in enumerate(opps) if o.get("id") == opp_id), -1)
    if idx < 0:
        raise HTTPException(404, "Opportunity not found")
    EDITABLE = {"name", "type", "price", "currency", "quantity_available", "benefits"}
    for k, v in (body or {}).items():
        if k in EDITABLE:
            opps[idx][k] = v
    await db.events.update_one({"id": event_id}, {"$set": {"sponsorship_opportunities": opps}})
    return opps[idx]


@api.delete("/events/{event_id}/sponsorships/{opp_id}")
async def delete_event_sponsorship(event_id: str, opp_id: str, user: dict = Depends(get_current_user)):
    event = await _ensure_event_owner(event_id, user)
    opps = [o for o in (event.get("sponsorship_opportunities") or []) if o.get("id") != opp_id]
    await db.events.update_one({"id": event_id}, {"$set": {"sponsorship_opportunities": opps}})
    return {"ok": True}


# ---------- Marketplace browse (sponsor-side) ----------
@api.get("/sponsorships/marketplace")
async def sponsorship_marketplace(
    sport: Optional[str] = None,
    location: Optional[str] = None,
    event_type: Optional[str] = None,
    price_max: Optional[float] = None,
    min_reach: Optional[int] = None,
    start_after: Optional[str] = None,
):
    """List events accepting sponsorships, with embedded opportunities for quick browse.
    `price_max` filters to events that have AT LEAST ONE opportunity ≤ that price (sponsor-budget filter).
    `min_reach` filters by expected_reach in requirements. `start_after` filters by start_date."""
    query: Dict[str, Any] = {"accept_sponsorships": True, "data_share_agreement": True}
    if sport:
        query["sport"] = sport
    if event_type:
        query["event_type"] = event_type
    if location:
        query["$or"] = [
            {"venue": {"$regex": location, "$options": "i"}},
            {"sponsorship_requirements.venue_location": {"$regex": location, "$options": "i"}},
        ]
    if start_after:
        query["start_date"] = {"$gte": start_after}
    events = await db.events.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    out = []
    for e in events:
        opps = e.get("sponsorship_opportunities") or []
        # Annotate slots_remaining + filter by price_max if asked.
        for o in opps:
            o["slots_remaining"] = max(0, int(o.get("quantity_available", 0)) - int(o.get("sold_count", 0)))
        if price_max is not None:
            matching = [o for o in opps if float(o.get("price") or 0) <= float(price_max) and o["slots_remaining"] > 0]
            if not matching:
                continue
        reqs = e.get("sponsorship_requirements") or {}
        if min_reach is not None and int(reqs.get("expected_reach") or 0) < int(min_reach):
            continue
        e["opportunities"] = opps
        e["min_price"] = min((float(o.get("price") or 0) for o in opps if (o.get("price") or 0) > 0), default=0)
        e["total_value"] = sum(float(o.get("price") or 0) * int(o.get("quantity_available") or 0) for o in opps)
        e["available_slots"] = sum(o["slots_remaining"] for o in opps)
        out.append(e)
    return out


# ---------- Interest creation / queue / approval ----------
@api.post("/sponsorships/interests")
async def create_sponsorship_interest(body: dict, user: dict = Depends(_require_sponsor_or_company)):
    event_id = (body or {}).get("event_id")
    opp_id = (body or {}).get("opportunity_id")
    if not event_id or not opp_id:
        raise HTTPException(400, "event_id and opportunity_id required")
    sponsor_profile = await _resolve_sponsor_profile(user)
    if not sponsor_profile:
        raise HTTPException(400, "Complete your sponsor profile first")
    event = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not event or not event.get("accept_sponsorships") or not event.get("data_share_agreement"):
        raise HTTPException(400, "This event is not currently accepting sponsorships")
    opp = next((o for o in (event.get("sponsorship_opportunities") or []) if o.get("id") == opp_id), None)
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    if max(0, int(opp.get("quantity_available", 0)) - int(opp.get("sold_count", 0))) <= 0:
        raise HTTPException(400, "All slots for this opportunity have been sold")
    # Block duplicate active interests from the same sponsor.
    existing = await db.sponsorship_interests.find_one({
        "event_id": event_id, "opportunity_id": opp_id, "sponsor_id": sponsor_profile["id"], "status": "pending",
    })
    if existing:
        raise HTTPException(400, "You have already expressed interest in this opportunity")
    interest = SponsorshipInterest(
        event_id=event_id, event_name=event.get("name"),
        opportunity_id=opp_id, opportunity_name=opp.get("name"), opportunity_price=float(opp.get("price") or 0),
        sponsor_id=sponsor_profile["id"], sponsor_user_id=user["id"],
        sponsor_company_name=sponsor_profile.get("company_name"),
        sponsor_industry=sponsor_profile.get("industry"),
        sponsor_budget_range=sponsor_profile.get("budget_range"),
        sponsor_website=sponsor_profile.get("website"),
        proposal_message=(body or {}).get("proposal_message", ""),
    )
    await db.sponsorship_interests.insert_one(interest.model_dump())
    logger.info("SPONSORSHIP INTEREST | %s wants %s on event %s", sponsor_profile.get("company_name"), opp.get("name"), event_id)
    return interest.model_dump()


@api.get("/sponsorships/interests/mine")
async def list_my_sponsorship_interests(user: dict = Depends(_require_sponsor_or_company)):
    sponsor_profile = await _resolve_sponsor_profile(user)
    if not sponsor_profile:
        return []
    return await db.sponsorship_interests.find({"sponsor_id": sponsor_profile["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.get("/sponsorships/my-activity")
async def sponsorship_my_activity(user: dict = Depends(get_current_user)):
    """Unified sponsorship inbox — returns both:
    * `sent`: interests THIS user (as a sponsor OR company_admin) has expressed on events run by others.
    * `received`: interests received on events THIS user's company (or events they own) is organising.
    Used by the CompanyDashboard sidebar card so a company that is *also* a sponsor sees both sides.
    """
    role = user.get("role")
    sent: list = []
    received: list = []

    # SENT — anyone who has a sponsor profile (dedicated sponsor OR company_admin).
    if role in ("sponsor", "company_admin"):
        sp = await _resolve_sponsor_profile(user)
        if sp:
            sent = await db.sponsorship_interests.find(
                {"sponsor_id": sp["id"]}, {"_id": 0}
            ).sort("created_at", -1).to_list(500)

    # RECEIVED — events owned by this user (company owner or organiser).
    q_events = None
    if role == "company_admin" and user.get("company_id"):
        q_events = {"company_id": user["company_id"]}
    elif role in ("organiser", "platform_admin"):
        q_events = {"organiser_id": user["id"]} if role == "organiser" else {}
    if q_events is not None:
        events = await db.events.find(q_events, {"_id": 0, "id": 1, "name": 1}).to_list(500)
        event_ids = [e["id"] for e in events]
        event_map = {e["id"]: e.get("name") for e in events}
        if event_ids:
            received = await db.sponsorship_interests.find(
                {"event_id": {"$in": event_ids}}, {"_id": 0}
            ).sort("created_at", -1).to_list(500)
            for r in received:
                r.setdefault("event_name", event_map.get(r.get("event_id")))
    return {"sent": sent, "received": received}


@api.get("/events/{event_id}/sponsorships/interests")
async def list_event_sponsorship_interests(event_id: str, user: dict = Depends(get_current_user)):
    await _ensure_event_owner(event_id, user)
    return await db.sponsorship_interests.find({"event_id": event_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.patch("/sponsorships/interests/{interest_id}")
async def decide_sponsorship_interest(interest_id: str, body: dict, user: dict = Depends(get_current_user)):
    """Organiser accepts or rejects an interest. Accept => opportunity sold_count++, opportunity
    awarded_to_sponsor_id/name written; if all slots filled, opportunity.status='sold'."""
    interest = await db.sponsorship_interests.find_one({"id": interest_id}, {"_id": 0})
    if not interest:
        raise HTTPException(404, "Interest not found")
    event = await _ensure_event_owner(interest["event_id"], user)
    decision = (body or {}).get("status")
    if decision not in ("accepted", "rejected"):
        raise HTTPException(400, "status must be 'accepted' or 'rejected'")
    if interest.get("status") != "pending":
        raise HTTPException(400, "This interest has already been decided")

    now = datetime.now(timezone.utc).isoformat()
    update = {"status": decision, "decided_at": now}
    await db.sponsorship_interests.update_one({"id": interest_id}, {"$set": update})

    if decision == "accepted":
        # Look up the sponsor profile so we can stamp logo + website onto awarded_to —
        # downstream surfaces (Sponsors tab, public event page) render the brand cards from there.
        sponsor_profile = await db.sponsor_profiles.find_one({"id": interest["sponsor_id"]}, {"_id": 0, "logo_url": 1, "website": 1, "industry": 1})
        sp = sponsor_profile or {}
        opps = event.get("sponsorship_opportunities") or []
        idx = next((i for i, o in enumerate(opps) if o.get("id") == interest["opportunity_id"]), -1)
        if idx >= 0:
            opp = opps[idx]
            opp["sold_count"] = int(opp.get("sold_count", 0)) + 1
            awarded = list(opp.get("awarded_to") or [])
            awarded.append({
                "sponsor_id": interest["sponsor_id"],
                "name": interest.get("sponsor_company_name"),
                "logo_url": sp.get("logo_url") or "",
                "website": sp.get("website") or "",
                "industry": sp.get("industry") or "",
                "interest_id": interest_id,
                "awarded_at": now,
            })
            opp["awarded_to"] = awarded
            if opp["sold_count"] >= int(opp.get("quantity_available", 0)):
                opp["status"] = "sold"
            opps[idx] = opp
            await db.events.update_one({"id": event["id"]}, {"$set": {"sponsorship_opportunities": opps}})
            # If this opportunity is now sold-out, auto-reject any other pending interests on it.
            if opp["status"] == "sold":
                await db.sponsorship_interests.update_many(
                    {"event_id": event["id"], "opportunity_id": interest["opportunity_id"], "status": "pending"},
                    {"$set": {"status": "rejected", "decided_at": now, "auto_rejected": True}},
                )
    logger.info("SPONSORSHIP %s | %s for opp %s on event %s", decision.upper(), interest.get("sponsor_company_name"), interest.get("opportunity_name"), event["id"])
    return {"ok": True, "status": decision}


# ---------- Admin metrics ----------
@api.get("/admin/sponsorship-metrics")
async def sponsorship_metrics(_: dict = Depends(require_platform_admin)):
    """Aggregate metrics for the Platform Admin dashboard sponsorship card."""
    total_opps = 0
    total_value = 0.0
    awarded_value = 0.0
    awarded_count = 0
    top_events_value = {}
    async for ev in db.events.find({"accept_sponsorships": True}, {"_id": 0, "id": 1, "name": 1, "sponsorship_opportunities": 1}):
        opps = ev.get("sponsorship_opportunities") or []
        ev_value = 0
        for o in opps:
            qty = int(o.get("quantity_available") or 0)
            sold = int(o.get("sold_count") or 0)
            price = float(o.get("price") or 0)
            total_opps += qty
            total_value += price * qty
            awarded_value += price * sold
            awarded_count += sold
            ev_value += price * qty
        if ev_value > 0:
            top_events_value[ev["id"]] = {"id": ev["id"], "name": ev.get("name"), "value": ev_value}

    pending = await db.sponsorship_interests.count_documents({"status": "pending"})
    accepted = await db.sponsorship_interests.count_documents({"status": "accepted"})
    rejected = await db.sponsorship_interests.count_documents({"status": "rejected"})

    # Top sponsors by awarded count
    top_sponsors_pipeline = [
        {"$match": {"status": "accepted"}},
        {"$group": {"_id": "$sponsor_id", "name": {"$first": "$sponsor_company_name"}, "count": {"$sum": 1}, "value": {"$sum": "$opportunity_price"}}},
        {"$sort": {"value": -1}},
        {"$limit": 10},
    ]
    top_sponsors = [{"sponsor_id": d["_id"], "name": d.get("name"), "count": d["count"], "value": d.get("value", 0)}
                    async for d in db.sponsorship_interests.aggregate(top_sponsors_pipeline)]

    top_events = sorted(top_events_value.values(), key=lambda x: x["value"], reverse=True)[:10]

    return {
        "total_opportunities": total_opps,
        "total_sponsorship_value": total_value,
        "awarded_value": awarded_value,
        "awarded_count": awarded_count,
        "pending_applications": pending,
        "accepted_applications": accepted,
        "rejected_applications": rejected,
        "top_sponsors": top_sponsors,
        "top_events": top_events,
    }


# Uploads (define route + mount BEFORE including router)
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
# Note: UPLOAD_DIR is preserved ONLY for legacy URLs that still point at disk-stored images.
# New uploads go into MongoDB so they survive container restarts / redeploys on production.


def _recompress_image_bytes(raw: bytes, content_type: str, *, max_dim: int = 1280, max_bytes: int = 350_000) -> tuple[bytes, str]:
    """Server-side safety-net compression. Resize down if >max_dim AND re-encode JPEG with
    quality stepping until under max_bytes (or floor q=55). GIF/SVG pass through unchanged.
    Returns (bytes, mime). Idempotent — files already small / already JPEG-q≤55 are returned as-is."""
    if content_type in ("image/gif", "image/svg+xml"):
        return raw, content_type
    try:
        from io import BytesIO
        from PIL import Image, ImageOps
        img = Image.open(BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        # Convert palette / alpha to RGB so JPEG encode never fails.
        if img.mode not in ("RGB",):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        # Quality step-down until under cap or floor.
        for q in (82, 75, 65, 55):
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=q, optimize=True, progressive=True)
            data = buf.getvalue()
            if len(data) <= max_bytes:
                return data, "image/jpeg"
        return data, "image/jpeg"  # last attempt at q=55
    except Exception:
        return raw, content_type  # fall back to original on any decode error


@api.post("/upload")
async def upload_image(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload an image. The bytes are recompressed server-side and stored in MongoDB so
    they survive container restarts and redeploys on production. Returns the canonical
    relative URL `/api/uploads/<id>` — the frontend resolves to absolute at render time
    using REACT_APP_BACKEND_URL so the same URL works in preview AND production."""
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Only JPEG, PNG, WEBP or GIF images allowed")
    raw = await file.read()
    if len(raw) > 1 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 1 MB after client-side compression)")
    data, mime = _recompress_image_bytes(raw, file.content_type or "image/jpeg")
    image_id = uuid.uuid4().hex
    await db.uploaded_images.insert_one({
        "id": image_id,
        "data": data,
        "mime": mime,
        "size": len(data),
        "uploaded_by": user.get("id"),
        "original_filename": file.filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": f"/api/uploads/{image_id}", "filename": image_id, "size": len(data), "mime": mime}


@api.get("/uploads/{image_id}")
async def serve_uploaded_image(image_id: str):
    """Serve an image stored in MongoDB. Falls back to the legacy on-disk uploads directory
    so any pre-existing URLs from before this change still work in preview."""
    # Strip extension if a client appended one (we store id without extension).
    bare_id = image_id.rsplit(".", 1)[0]
    doc = await db.uploaded_images.find_one({"id": bare_id}, {"_id": 0, "data": 1, "mime": 1})
    if doc:
        return Response(content=doc["data"], media_type=doc.get("mime") or "image/jpeg",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})
    # Legacy fallback: file on disk (works in preview where the disk hasn't been wiped).
    legacy_path = UPLOAD_DIR / image_id
    if legacy_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(legacy_path), media_type="image/jpeg")
    raise HTTPException(404, "Image not found")


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
            "is_super_admin": True,
            "permissions": list(ALL_PERMISSIONS),
            "company_id": None,
            "password_hash": hash_password(admin_password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Seeded platform admin: {admin_email}")
    else:
        # ensure role, name, permissions are all correct — but NEVER auto-reset the
        # password on restart. Doing so wiped out user-initiated password changes
        # (via forgot-password) every time the backend hot-reloaded, forcing the
        # admin to keep resetting. If the password is somehow blank/corrupt we still
        # heal it below.
        updates: dict = {}
        if existing.get("role") not in ("platform_admin",):
            updates["role"] = "platform_admin"
        # Only reseed the password when it's missing/blank OR when the operator
        # has explicitly requested a reset via FORCE_ADMIN_PASSWORD_RESET=true.
        current_hash = existing.get("password_hash") or ""
        force_reset = os.environ.get("FORCE_ADMIN_PASSWORD_RESET", "").lower() in ("1", "true", "yes")
        if not current_hash or force_reset:
            updates["password_hash"] = hash_password(admin_password)
            if force_reset:
                logger.warning("FORCE_ADMIN_PASSWORD_RESET=true — admin password reset to ADMIN_PASSWORD env value")
        if existing.get("name") in ("PlaySphere Admin", "PLAYSPHERE Admin"):
            updates["name"] = "Kreeda Nation Admin"
        if not existing.get("is_super_admin"):
            updates["is_super_admin"] = True
        if not existing.get("permissions"):
            updates["permissions"] = list(ALL_PERMISSIONS)
        if updates:
            await db.users.update_one({"email": admin_email}, {"$set": updates})

    viewer_email = "viewer@kreedanation.com"
    # Migrate legacy viewer email if it still exists; do NOT create a new viewer
    # account (production wants a clean slate — only the platform admin is seeded).
    if await db.users.find_one({"email": "viewer@playsphere.com"}) and not await db.users.find_one({"email": viewer_email}):
        await db.users.update_one({"email": "viewer@playsphere.com"}, {"$set": {"email": viewer_email}})
        logger.info(f"Migrated viewer email: viewer@playsphere.com -> {viewer_email}")


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
    from routes.fixtures import generate_round_robin as _gen_rr
    fixtures = _gen_rr(team_ids, ev.id)
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
    {"value": "pickleball", "label": "Pickleball"},
    {"value": "tabletennis", "label": "Table Tennis"},
    {"value": "tennis", "label": "Lawn Tennis"},
    {"value": "snooker", "label": "Snooker / Pool"},
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


# Built-in sport metadata — used to auto-populate scoring_pattern + player_format
# for well-known sports (so admin doesn't have to configure them manually) AND
# to backfill legacy sport rows on-the-fly during list_sports().
#   scoring_pattern → drives which scorer UI + `renderScore()` branch runs.
#   player_format:
#     "team"       → team sport (cricket / football / basketball / volleyball / hackathon).
#     "individual" → 1v1 sport with a single player per side (chess / quiz).
#     "both"       → racket-sport that supports singles AND doubles — the event
#                    creator picks one at event creation time.
_SPORT_DEFAULTS = {
    "cricket":    {"scoring_pattern": "cricket",    "player_format": "team",
                   "config": {"players_per_team": {"min": 6, "max": 15, "on_field": 11},
                              "formats_supported": ["league", "knockout", "round_robin", "group_knockout"],
                              "tie_breakers": ["points", "nrr", "head_to_head"],
                              "standings_fields": ["played", "won", "lost", "nrr", "points"],
                              "has_toss": True, "has_playing_xi": True,
                              "match_duration_min": 240}},
    "football":   {"scoring_pattern": "football",   "player_format": "team",
                   "config": {"players_per_team": {"min": 7, "max": 18, "on_field": 11},
                              "formats_supported": ["league", "knockout", "round_robin", "group_knockout", "double_elimination"],
                              "tie_breakers": ["points", "goal_diff", "goals_for", "head_to_head"],
                              "standings_fields": ["played", "won", "drawn", "lost", "gf", "ga", "gd", "points"],
                              "has_cards": True, "has_substitutions": True,
                              "match_duration_min": 90}},
    "basketball": {"scoring_pattern": "basketball", "player_format": "team",
                   "config": {"players_per_team": {"min": 5, "max": 12, "on_field": 5},
                              "formats_supported": ["league", "knockout", "round_robin", "group_knockout"],
                              "tie_breakers": ["points", "point_diff", "head_to_head"],
                              "standings_fields": ["played", "won", "lost", "pf", "pa", "pd", "points"],
                              "has_substitutions": True,
                              "match_duration_min": 40}},
    "volleyball": {"scoring_pattern": "racket",     "player_format": "team",
                   "config": {"players_per_team": {"min": 6, "max": 12, "on_field": 6},
                              "formats_supported": ["league", "knockout", "round_robin"],
                              "tie_breakers": ["points", "sets_won", "point_diff"],
                              "standings_fields": ["played", "won", "lost", "sets_won", "sets_lost", "points"],
                              "match_duration_min": 60}},
    "badminton":  {"scoring_pattern": "racket",     "player_format": "both",
                   "config": {"players_per_team": {"min": 1, "max": 2, "on_field": 2},
                              "formats_supported": ["knockout", "round_robin", "group_knockout", "double_elimination"],
                              "tie_breakers": ["points", "sets_won", "point_diff", "head_to_head"],
                              "standings_fields": ["played", "won", "lost", "sets_won", "points"],
                              "best_of_sets": 3,
                              "match_duration_min": 45}},
    "tabletennis": {"scoring_pattern": "racket",    "player_format": "both",
                    "config": {"players_per_team": {"min": 1, "max": 2, "on_field": 2},
                               "formats_supported": ["knockout", "round_robin", "group_knockout"],
                               "tie_breakers": ["points", "sets_won", "head_to_head"],
                               "standings_fields": ["played", "won", "lost", "sets_won", "points"],
                               "best_of_sets": 5,
                               "match_duration_min": 30}},
    "tennis":     {"scoring_pattern": "racket",     "player_format": "both",
                   "config": {"players_per_team": {"min": 1, "max": 2, "on_field": 2},
                              "formats_supported": ["knockout", "round_robin"],
                              "tie_breakers": ["sets_won", "games_won"],
                              "standings_fields": ["played", "won", "lost", "sets_won", "games_won"],
                              "best_of_sets": 3, "has_tiebreak": True,
                              "match_duration_min": 90}},
    "lawntennis": {"scoring_pattern": "racket",     "player_format": "both",
                   "config": {"players_per_team": {"min": 1, "max": 2, "on_field": 2},
                              "formats_supported": ["knockout", "round_robin"],
                              "tie_breakers": ["sets_won", "games_won"],
                              "standings_fields": ["played", "won", "lost", "sets_won", "games_won"],
                              "best_of_sets": 3, "has_tiebreak": True,
                              "match_duration_min": 90}},
    "pickleball": {"scoring_pattern": "racket",     "player_format": "both",
                   "config": {"players_per_team": {"min": 1, "max": 2, "on_field": 2},
                              "formats_supported": ["knockout", "round_robin", "group_knockout"],
                              "tie_breakers": ["points", "sets_won", "point_diff"],
                              "standings_fields": ["played", "won", "lost", "sets_won", "points"],
                              "best_of_sets": 3, "points_to_win_set": 11,
                              "match_duration_min": 30}},
    "squash":     {"scoring_pattern": "racket",     "player_format": "both",
                   "config": {"players_per_team": {"min": 1, "max": 2, "on_field": 2},
                              "formats_supported": ["knockout", "round_robin"],
                              "tie_breakers": ["sets_won", "points"],
                              "standings_fields": ["played", "won", "lost", "sets_won"],
                              "best_of_sets": 5,
                              "match_duration_min": 45}},
    "snooker":    {"scoring_pattern": "generic",    "player_format": "individual",
                   "config": {"players_per_team": {"min": 1, "max": 1, "on_field": 1},
                              "formats_supported": ["knockout", "round_robin"],
                              "tie_breakers": ["frames_won", "frames_diff", "head_to_head"],
                              "standings_fields": ["played", "won", "lost", "frames_won", "frames_diff"],
                              "race_to_frames": 5,
                              "match_duration_min": 60}},
    "pool":       {"scoring_pattern": "generic",    "player_format": "individual",
                   "config": {"players_per_team": {"min": 1, "max": 1, "on_field": 1},
                              "formats_supported": ["knockout", "round_robin"],
                              "tie_breakers": ["frames_won", "frames_diff"],
                              "standings_fields": ["played", "won", "lost", "frames_won", "frames_diff"],
                              "race_to_frames": 5,
                              "match_duration_min": 30}},
    "chess":      {"scoring_pattern": "chess",      "player_format": "individual",
                   "config": {"players_per_team": {"min": 1, "max": 1, "on_field": 1},
                              "formats_supported": ["swiss", "knockout", "round_robin"],
                              "tie_breakers": ["points", "buchholz", "sonneborn_berger", "head_to_head"],
                              "standings_fields": ["played", "won", "lost", "drawn", "points", "buchholz"],
                              "time_control": "10+5",
                              "match_duration_min": 60}},
    "quiz":       {"scoring_pattern": "quiz",       "player_format": "individual",
                   "config": {"players_per_team": {"min": 1, "max": 5, "on_field": 4},
                              "formats_supported": ["league", "knockout"],
                              "tie_breakers": ["points", "correct_answers"],
                              "standings_fields": ["played", "won", "lost", "points"],
                              "match_duration_min": 45}},
    "hackathon":  {"scoring_pattern": "hackathon",  "player_format": "team",
                   "config": {"players_per_team": {"min": 1, "max": 6, "on_field": 6},
                              "formats_supported": ["league"],
                              "tie_breakers": ["score"],
                              "standings_fields": ["projects", "score", "rank"],
                              "match_duration_min": 1440}},
}


def _enrich_sport(doc: dict) -> dict:
    """Ensure a sport doc has scoring_pattern + player_format + config set,
    using _SPORT_DEFAULTS as a fallback for well-known sports; otherwise
    defaults to a generic team-sport config."""
    if not doc:
        return doc
    defaults = _SPORT_DEFAULTS.get(doc.get("value", "").lower(), {
        "scoring_pattern": "generic", "player_format": "team",
        "config": {"players_per_team": {"min": 1, "max": 20, "on_field": 11},
                   "formats_supported": ["league", "knockout", "round_robin"],
                   "tie_breakers": ["points"],
                   "standings_fields": ["played", "won", "lost", "points"]},
    })
    if not doc.get("scoring_pattern"):
        doc["scoring_pattern"] = defaults["scoring_pattern"]
    if not doc.get("player_format"):
        doc["player_format"] = defaults["player_format"]
    # Config: merge stored + defaults so admin overrides win.
    stored = doc.get("config") or {}
    merged = {**defaults.get("config", {}), **stored}
    doc["config"] = merged
    return doc


@api.get("/sports")
async def list_sports(include_inactive: bool = False):
    flt = {} if include_inactive else {"active": True}
    docs = await db.sports.find(flt, {"_id": 0}).sort("sort_order", 1).to_list(200)
    return [_enrich_sport(d) for d in docs]


@api.post("/sports")
async def create_sport(body: dict, _: dict = Depends(require_platform_admin)):
    # Canonicalise the slug — strip spaces + lower-case so "Pickle Ball" and
    # "pickleball" don't produce duplicate rows. Admin can still set any label.
    value = "".join((body.get("value") or "").strip().lower().split())
    label = (body.get("label") or "").strip()
    if not (value and label):
        raise HTTPException(400, "value and label required")
    if await db.sports.find_one({"value": value}):
        raise HTTPException(400, "Sport with this value already exists")
    defaults = _SPORT_DEFAULTS.get(value, {"scoring_pattern": "generic", "player_format": "team"})
    doc = {
        "id": str(uuid.uuid4()),
        "value": value, "label": label, "active": True,
        "sort_order": int(body.get("sort_order", 999)),
        "scoring_pattern": (body.get("scoring_pattern") or defaults["scoring_pattern"]),
        "player_format": (body.get("player_format") or defaults["player_format"]),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sports.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.patch("/sports/{sport_id}")
async def update_sport(sport_id: str, body: dict, _: dict = Depends(require_platform_admin)):
    allowed = {k: v for k, v in body.items() if k in ("label", "active", "sort_order", "scoring_pattern", "player_format", "config")}
    if not allowed:
        raise HTTPException(400, "No allowed fields")
    await db.sports.update_one({"id": sport_id}, {"$set": allowed})
    doc = await db.sports.find_one({"id": sport_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404)
    return _enrich_sport(doc)


@api.delete("/sports/{sport_id}")
async def delete_sport(sport_id: str, _: dict = Depends(require_platform_admin)):
    res = await db.sports.delete_one({"id": sport_id})
    if not res.deleted_count:
        raise HTTPException(404)
    return {"ok": True}


# ---------- Dashboards ----------
@api.get("/dashboard/admin")
async def dashboard_admin(_: dict = Depends(require_platform_admin)):
    organisers = await db.companies.count_documents({"org_type": "organiser"})
    all_companies = await db.companies.count_documents({})
    return {
        "events_total": await db.events.count_documents({}),
        "events_ongoing": await db.events.count_documents({"status": "ongoing"}),
        "events_upcoming": await db.events.count_documents({"status": "upcoming"}),
        "events_completed": await db.events.count_documents({"status": "completed"}),
        "companies": all_companies - organisers,
        "organisers": organisers,
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
        # Player-hosted local matches — split by visibility so the admin can spot
        # abuse (spam events) vs healthy usage at a glance.
        "local_matches_total": await db.events.count_documents({"is_local_match": True}),
        "local_matches_public": await db.events.count_documents({"is_local_match": True, "listed_publicly": {"$ne": False}}),
        "local_matches_hidden": await db.events.count_documents({"is_local_match": True, "listed_publicly": False}),
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
            "allow_after_hours": False,
        }
    doc.setdefault("happy_hours", [])
    doc.setdefault("allow_after_hours", False)
    return doc


@api.patch("/vendor-listings/{listing_id}/schedule")
async def update_schedule(listing_id: str, body: dict, user: dict = Depends(get_current_user)):
    await _require_vendor_owner(listing_id, user)
    allowed = {k: body[k] for k in ("opening_time", "closing_time", "slot_minutes", "peak_hours",
                                     "peak_price_factor", "weekend_price_factor", "happy_hours", "amenities",
                                     "allow_after_hours") if k in body}
    if not allowed:
        raise HTTPException(400, "no allowed fields")
    if "allow_after_hours" in allowed:
        allowed["allow_after_hours"] = bool(allowed["allow_after_hours"])
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
    listing = await _require_vendor_owner(listing_id, user)
    date = body.get("date") or ""
    start = body.get("start_time") or ""
    end = body.get("end_time") or ""
    if not (date and start and end):
        raise HTTPException(400, "date, start_time, end_time required")
    _reject_past_slot(date, start)
    if end <= start:
        raise HTTPException(400, "end_time must be after start_time")
    doc = {
        "id": str(uuid.uuid4()),
        "vendor_id": listing.get("vendor_id"),
        "listing_id": listing_id,
        "sub_unit_id": body.get("sub_unit_id"),
        "date": date, "start_time": start, "end_time": end,
        "reason": (body.get("reason") or "").strip() or "maintenance",
        "notes": (body.get("notes") or "").strip(),
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
    # Vendor's private (offline) bookings — block the slot for KN buyers too.
    privates = await db.private_bookings.find({
        "listing_id": listing_id, "requested_date": date,
    }, {"_id": 0, "start_time": 1, "end_time": 1}).to_list(200)
    booked = list(booked) + list(privates)

    slots = []
    # Filter out past-time slots for the current day so users can't book slots
    # that have already elapsed. Uses the server's naive local date/time; if
    # the deployment is UTC-only, the filter is still correct because clients
    # send date+start_time in the same reference frame as `date`.
    now = datetime.now(timezone.utc)
    is_today = date == now.date().isoformat()
    now_min = now.hour * 60 + now.minute if is_today else -1
    for s in _slots_between(opening, closing, minutes):
        s_end = _hhmm_add(s, max(1, minutes // 60))
        status = "available"
        if is_today and _hhmm_to_min(s) <= now_min:
            status = "past"
        for b in booked:
            if status == "available" and _overlaps(s, s_end, b["start_time"], b["end_time"]):
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
cricket_routes.register(
    api, db, ws_manager, require_admin, propagate_knockout_winner,
    get_current_user=get_current_user, can_score_fixture=_can_score_fixture,
)

# Site settings / About / Contact (extracted into routes/settings.py)
from routes import settings as settings_routes  # noqa: E402
settings_routes.register(api, db, SiteSettings, require_platform_admin)

# Auth / Company signup / Password reset (extracted into routes/auth.py)
from routes import auth as auth_routes  # noqa: E402
from types import SimpleNamespace  # noqa: E402

auth_routes.register(api, db, SimpleNamespace(
    UserPublic=UserPublic,
    RegisterBody=RegisterBody,
    LoginBody=LoginBody,
    CompanySignupBody=CompanySignupBody,
    Company=Company,
    hash_password=hash_password,
    verify_password=verify_password,
    create_access_token=create_access_token,
    set_auth_cookie=set_auth_cookie,
    get_current_user=get_current_user,
    require_company_admin=require_company_admin,
    require_platform_admin=require_platform_admin,
    _user_with_company=_user_with_company,
    _unique_player_slug=_unique_player_slug,
))

# Events / Teams / Team-roster players (extracted into routes/events.py)
from routes import events as events_routes  # noqa: E402

events_routes.register(api, db, SimpleNamespace(
    Event=Event,
    EventCreate=EventCreate,
    Team=Team,
    TeamCreate=TeamCreate,
    Player=Player,
    PlayerCreate=PlayerCreate,
    get_current_user_optional=get_current_user_optional,
    get_current_user=get_current_user,
    require_admin=require_admin,
    require_company_admin=require_company_admin,
    can_manage_event=_can_manage_event,
    SPORT_DEFAULTS=_SPORT_DEFAULTS,
))

# Fixtures + WebSocket (extracted into routes/fixtures.py)
from routes import fixtures as fixtures_routes  # noqa: E402

fixtures_routes.register(api, app, db, ws_manager, SimpleNamespace(
    Fixture=Fixture,
    ScoreUpdate=ScoreUpdate,
    require_admin=require_admin,
    get_current_user=get_current_user,
    can_manage_event=_can_manage_event,
    can_score_fixture=_can_score_fixture,
    fixtures_locked=_fixtures_locked,
    get_event_or_404=_get_event_or_404,
    default_score=default_score,
    propagate_knockout_winner=propagate_knockout_winner,
))

# Vendors + Vendor Listings (extracted into routes/vendors.py)
from routes import vendors as vendors_routes  # noqa: E402

vendors_routes.register(api, db, SimpleNamespace(
    UserPublic=UserPublic,
    VendorSignupBody=VendorSignupBody,
    Vendor=Vendor,
    VendorListing=VendorListing,
    VendorListingCreate=VendorListingCreate,
    hash_password=hash_password,
    create_access_token=create_access_token,
    set_auth_cookie=set_auth_cookie,
    get_current_user=get_current_user,
    require_platform_admin=require_platform_admin,
    require_permission=require_permission,
))

# Services catalog + classic Bookings (extracted into routes/bookings.py)
from routes import bookings as bookings_routes  # noqa: E402

bookings_routes.register(api, db, SimpleNamespace(
    Service=Service,
    ServiceCreate=ServiceCreate,
    Booking=Booking,
    BookingCreate=BookingCreate,
    get_current_user=get_current_user,
    require_company_admin=require_company_admin,
    require_super_admin=require_super_admin,
))


# Vendor memberships (Phase 1 — vendor-defined, no payment yet)
from routes import memberships as memberships_routes  # noqa: E402

memberships_routes.register(api, db, SimpleNamespace(
    get_current_user=get_current_user,
))


# Business model — venue leads + vendor offline-mode subscription + private bookings (Phase 5A + 5C)
from routes import business as business_routes  # noqa: E402

business_routes.register(api, db, SimpleNamespace(
    get_current_user=get_current_user,
    require_platform_admin=require_platform_admin,
    VENDOR_CATEGORY_SPORTS=VENDOR_CATEGORY_SPORTS,
    send_email=send_email,
    guard_slot_conflict=_guard_slot_conflict,
))


# Commission invoices — vendor's platform commission dues + admin reminders
from routes import commission_invoices as commission_routes  # noqa: E402

commission_routes.register(api, db, SimpleNamespace(
    get_current_user=get_current_user,
    require_platform_admin=require_platform_admin,
    send_email=send_email,
))


# Corporate Services — RFQ-based event package catalogue (admin-configurable)
from routes import corporate_services as cs_routes  # noqa: E402

cs_routes.register(api, db, SimpleNamespace(
    get_current_user=get_current_user,
    require_platform_admin=require_platform_admin,
))


# Corporate Services Invoices + Razorpay pay-link (Phase 3 follow-up)
from routes import cs_invoices as cs_invoice_routes  # noqa: E402

cs_invoice_routes.register(api, db, SimpleNamespace(
    get_current_user=get_current_user,
    require_platform_admin=require_platform_admin,
))


# Sitemap + robots.txt — SEO surface (materialises static files into
# frontend/public so search-engines can crawl at root domain).
from routes import sitemap as sitemap_routes  # noqa: E402

sitemap_routes.register(api, app, db, SimpleNamespace(
    require_platform_admin=require_platform_admin,
))


# Player corporate-email verification — extracted from server.py (P2 refactor)
from routes import players_corp_email as _players_corp_email_routes  # noqa: E402

_players_corp_email_routes.register(api, db, SimpleNamespace(
    get_current_user=get_current_user,
))


# Event Lifecycle Automation — status transitions + reminder emails
from routes import event_lifecycle as _event_lifecycle_routes  # noqa: E402

_event_lifecycle_routes.register(api, db, send_email, SimpleNamespace(
    require_platform_admin=require_platform_admin,
))


# Admin-triggerable seeds — used to re-seed the demo vendor on production
# without needing shell access.
from routes import admin_seeds as _admin_seeds_routes  # noqa: E402

_admin_seeds_routes.register(api, db, SimpleNamespace(
    require_platform_admin=require_platform_admin,
    hash_password=hash_password,
))


# Register router + static mount AFTER all @api.x definitions above
app.include_router(api)
api_router = api  # alias kept for any callers
# /api/uploads/<id> is now handled by the dynamic route above (Mongo-backed with disk fallback).


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
    # Sparse unique index — some old rows may lack a slug; the backfill below
    # fills them in idempotently.
    await db.player_profiles.create_index("slug", unique=True, sparse=True)
    # ---- Backfill: give every existing PlayerProfile a slug. Runs once per boot;
    # subsequent boots find no missing rows and finish in one query.
    async for doc in db.player_profiles.find({"$or": [{"slug": None}, {"slug": {"$exists": False}}]}, {"_id": 0, "id": 1, "name": 1}):
        slug = await _unique_player_slug(doc.get("name") or "")
        await db.player_profiles.update_one({"id": doc["id"]}, {"$set": {"slug": slug}})
    await db.vendors.create_index("user_id", unique=True)
    await db.vendor_listings.create_index("vendor_id")
    await db.vendor_bookings.create_index("company_id")
    await db.vendor_bookings.create_index("vendor_id")
    await db.membership_purchases.create_index("buyer_user_id")
    await db.membership_purchases.create_index("vendor_id")
    await db.membership_purchases.create_index([("status", 1), ("expires_at", 1)])
    await seed_admin()
    # seed_demo_data() intentionally disabled (Feb 18, 2026) — production wants a clean slate.
    # Only services + sports catalogs are still seeded so the platform UI has its lookups.
    await seed_services()
    await seed_sports()
    # Background: send membership renewal reminders 7d before expiry
    from routes.memberships_scheduler import start_membership_scheduler
    start_membership_scheduler(db, send_email)
    # Background: Event Lifecycle Automation — status transitions + reminders (daily)
    from routes.event_lifecycle import start_event_lifecycle_scheduler
    start_event_lifecycle_scheduler(db, send_email)


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
