"""Seed two test players directly in MongoDB for iteration_17 testing."""
import os
import sys
import uuid
import bcrypt
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

users = db["users"]
players = db["player_profiles"]

PW = bcrypt.hashpw(b"test123", bcrypt.gensalt()).decode("utf-8")
print("bcrypt prefix:", PW[:4])
now = datetime.now(timezone.utc).isoformat()


def seed_player(mobile, name, extras_user=None, extras_player=None, email=None):
    # delete prior runs
    users.delete_many({"mobile": mobile})
    players.delete_many({"mobile": mobile})

    uid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    user_doc = {
        "id": uid,
        "email": email or f"{mobile.strip('+')}@example.com",
        "name": name,
        "role": "player",
        "mobile": mobile,
        "password_hash": PW,
        "email_verified": True,
        "created_at": now,
    }
    if extras_user:
        user_doc.update(extras_user)
    users.insert_one(user_doc)

    player_doc = {
        "id": pid,
        "user_id": uid,
        "name": name,
        "mobile": mobile,
        "email": user_doc["email"],
        "photo_url": "",
        "city": "",
        "view_count": 0,
        "created_at": now,
    }
    if extras_player:
        player_doc.update(extras_player)
    players.insert_one(player_doc)
    print(f"Seeded user {uid} + player {pid} mobile={mobile}")
    return uid, pid


# Player A: multi-sport target (empty - will be populated via UI)
seed_player(
    "+919900111111",
    "QA Multi",
    extras_player={
        "interested_sports": [],
        "sport_profiles": {},
    },
)

# Player B: legacy cricket-only (NO interested_sports field at all)
seed_player(
    "+919900222222",
    "QA Legacy",
    extras_player={
        "role": "batsman",
        "batting_hand": "left",
        "bowling_style": "right-arm-spin",
        "jersey_number": 99,
    },
)

# Sanity verify
for m in ("+919900111111", "+919900222222"):
    u = users.find_one({"mobile": m}, {"_id": 0, "password_hash": 0})
    p = players.find_one({"mobile": m}, {"_id": 0})
    print("USER", u)
    print("PLAYER", p)
