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


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
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
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
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


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


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
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user)
    token = create_access_token(user["id"], user["email"], user["role"])
    set_auth_cookie(response, token)
    return UserPublic(id=user["id"], email=user["email"], name=user["name"], role=user["role"])


@api.post("/auth/login", response_model=UserPublic)
async def login(body: LoginBody, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], user["email"], user["role"])
    set_auth_cookie(response, token)
    return UserPublic(id=user["id"], email=user["email"], name=user["name"], role=user["role"])


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return UserPublic(**{k: user[k] for k in ["id", "email", "name", "role"]})


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
async def list_events():
    docs = await db.events.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [Event(**d) for d in docs]


@api.get("/events/{event_id}", response_model=Event)
async def get_event(event_id: str):
    doc = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Event not found")
    return Event(**doc)


@api.post("/events", response_model=Event)
async def create_event(body: EventCreate, _: dict = Depends(require_admin)):
    ev = Event(**body.model_dump())
    await db.events.insert_one(ev.model_dump())
    return ev


@api.patch("/events/{event_id}", response_model=Event)
async def update_event(event_id: str, body: dict, _: dict = Depends(require_admin)):
    body.pop("id", None)
    await db.events.update_one({"id": event_id}, {"$set": body})
    doc = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Event not found")
    return Event(**doc)


@api.delete("/events/{event_id}")
async def delete_event(event_id: str, _: dict = Depends(require_admin)):
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
            "name": "Admin",
            "role": "admin",
            "password_hash": hash_password(admin_password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Seeded admin: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})

    # Seed a viewer
    viewer = await db.users.find_one({"email": "viewer@playsphere.com"})
    if not viewer:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": "viewer@playsphere.com",
            "name": "Viewer",
            "role": "viewer",
            "password_hash": hash_password("viewer123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


async def seed_demo_data():
    if await db.events.count_documents({}) > 0:
        return
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
    )
    await db.events.insert_one(ev3.model_dump())


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.teams.create_index("event_id")
    await db.fixtures.create_index("event_id")
    await db.players.create_index("team_id")
    await seed_admin()
    await seed_demo_data()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
