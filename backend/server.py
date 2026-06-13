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
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, EmailStr


# ---------- DB ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# ---------- App ----------
app = FastAPI(title="PlaySphere API")
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
MatchStatus = Literal["scheduled", "live", "completed"]


class Team(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    department: Optional[str] = ""
    captain: Optional[str] = ""
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
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    venue: Optional[str] = ""
    status: EventStatus = "upcoming"
    banner_url: Optional[str] = ""
    company_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventCreate(BaseModel):
    name: str
    sport: SportType
    description: Optional[str] = ""
    format: FixtureFormat = "round_robin"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    venue: Optional[str] = ""
    banner_url: Optional[str] = ""


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
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SponsorCreate(BaseModel):
    name: str
    tier: SponsorTier = "bronze"
    logo_url: str
    website: Optional[str] = ""
    description: Optional[str] = ""
    show_in_banner: bool = True


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
    body.pop("id", None); body.pop("slug", None); body.pop("owner_user_id", None)
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
async def list_events(company_id: Optional[str] = None):
    q = {"company_id": company_id} if company_id else {}
    docs = await db.events.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [Event(**d) for d in docs]


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


# ---------- Players ----------
@api.get("/players", response_model=List[Player])
async def list_players(team_id: Optional[str] = None):
    q = {"team_id": team_id} if team_id else {}
    docs = await db.players.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [Player(**d) for d in docs]


@api.get("/players/{player_id}", response_model=Player)
async def get_player(player_id: str):
    doc = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Player not found")
    return Player(**doc)


@api.post("/players", response_model=Player)
async def create_player(body: PlayerCreate):
    p = Player(**body.model_dump())
    await db.players.insert_one(p.model_dump())
    return p


@api.patch("/players/{player_id}", response_model=Player)
async def update_player(player_id: str, body: dict, _: dict = Depends(require_admin)):
    body.pop("id", None)
    await db.players.update_one({"id": player_id}, {"$set": body})
    doc = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Player not found")
    return Player(**doc)


@api.delete("/players/{player_id}")
async def delete_player(player_id: str, _: dict = Depends(require_admin)):
    await db.players.delete_one({"id": player_id})
    return {"ok": True}


# ---------- Fixture generation ----------
def generate_round_robin(team_ids: List[str], event_id: str) -> List[dict]:
    teams = list(team_ids)
    if len(teams) % 2 == 1:
        teams.append(None)  # bye
    n = len(teams)
    rounds = []
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
    match_num = fixture["match_number"]
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
async def list_sponsors():
    docs = await db.sponsors.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
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
    body.pop("id", None); body.pop("company_id", None); body.pop("total_price", None)
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


# ---------- Stats ----------
@api.get("/stats")
async def get_stats(user: Optional[dict] = None):
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
    return {"name": "PlaySphere API", "tagline": "Where Teams Compete, Connect & Grow"}


app.include_router(api)

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
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@playsphere.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "PlaySphere Admin",
            "role": "platform_admin",
            "company_id": None,
            "password_hash": hash_password(admin_password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Seeded platform admin: {admin_email}")
    else:
        # ensure role is set correctly and password matches
        updates = {}
        if existing.get("role") not in ("platform_admin",):
            updates["role"] = "platform_admin"
        if not verify_password(admin_password, existing["password_hash"]):
            updates["password_hash"] = hash_password(admin_password)
        if updates:
            await db.users.update_one({"email": admin_email}, {"$set": updates})

    viewer = await db.users.find_one({"email": "viewer@playsphere.com"})
    if not viewer:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": "viewer@playsphere.com",
            "name": "Viewer",
            "role": "viewer",
            "company_id": None,
            "password_hash": hash_password("viewer123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


async def seed_demo_data():
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
    if await db.services.count_documents({}) > 0:
        return
    services = [
        {
            "name": "Live YouTube Streaming",
            "category": "streaming",
            "description": "Multi-camera live broadcast on YouTube with on-screen scoreboard, replays and commentary.",
            "images": ["https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?w=900"],
            "base_price": 499.0,
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
            "images": ["https://images.unsplash.com/photo-1517438476312-10d79c5f25af?w=900"],
            "base_price": 120.0,
            "price_unit": "per session",
            "config_fields": [
                {"key": "sessions", "label": "Number of sessions", "type": "number", "min": 1, "max": 30, "default": "4", "required": True},
                {"key": "with_coach", "label": "Include certified coach", "type": "select", "options": ["Yes", "No"], "default": "Yes"},
                {"key": "team_size", "label": "Approx team size", "type": "number", "default": "15"},
            ],
            "variants": [],
            "allow_custom_text": True, "custom_text_label": "Focus areas (e.g., fitness, batting, bowling)",
        },
    ]
    for s in services:
        await db.services.insert_one(Service(**s).model_dump())
    logger.info(f"Seeded {len(services)} services")


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.companies.create_index("slug", unique=True)
    await db.teams.create_index("event_id")
    await db.events.create_index("company_id")
    await db.fixtures.create_index("event_id")
    await db.players.create_index("team_id")
    await db.bookings.create_index("company_id")
    await seed_admin()
    await seed_demo_data()
    await seed_services()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
