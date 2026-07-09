"""
Seed script for iteration 35 frontend E2E tests.
Creates events (pickleball, snooker, chess, tabletennis, swiss, double_elim, knockout)
with 4 teams each and generated fixtures, so Playwright tests can navigate
directly to /events/{id} without needing to build state through the UI.

Idempotent: reruns delete existing TEST_iter35_* events and recreate.
"""
import os
import sys
import requests
import json
import time

BASE = "https://live-scoring-hub-5.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@kreedanation.com"
ADMIN_PASSWORD = "admin123"
PREFIX = "TEST_iter35_"

s = requests.Session()

def login():
    r = s.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    print(f"[seed] logged in as {ADMIN_EMAIL}")

def cleanup():
    r = s.get(f"{BASE}/events?limit=200")
    if r.status_code != 200:
        return
    for ev in r.json():
        if ev.get("name", "").startswith(PREFIX):
            try:
                s.delete(f"{BASE}/events/{ev['id']}")
                print(f"[seed] deleted stale event {ev['name']}")
            except Exception:
                pass

def create_event(label, sport, format_, event_type="playsphere_organized", player_format=None):
    payload = {
        "name": f"{PREFIX}{label}",
        "description": "Iter35 auto-seeded",
        "sport": sport,
        "format": format_,
        "event_type": event_type,
        "venue": "Seed venue",
    }
    if player_format:
        payload["player_format"] = player_format
    r = s.post(f"{BASE}/events", json=payload)
    r.raise_for_status()
    ev = r.json()
    print(f"[seed] created event {ev['id']} - {ev['name']} ({sport}/{format_})")
    return ev

def add_teams(event_id, sport, n=4, individual=False):
    ids = []
    for i in range(n):
        payload = {
            "name": f"Team {chr(65+i)}",
            "color": ["#84CC16", "#EC4899", "#06B6D4", "#F59E0B"][i % 4],
            "department": "Dept",
        }
        r = s.post(f"{BASE}/events/{event_id}/teams", json=payload)
        r.raise_for_status()
        ids.append(r.json()["id"])
    print(f"[seed]   added {n} teams to {event_id}")
    return ids

def generate_fixtures(event_id):
    r = s.post(f"{BASE}/events/{event_id}/generate-fixtures")
    if not r.ok:
        print(f"[seed]   generate-fixtures FAILED for {event_id}: {r.status_code} {r.text}")
        return
    print(f"[seed]   generated fixtures for {event_id}")

def main():
    login()
    cleanup()
    seeds = {}
    # Phase 5 sport scorer tests
    for label, sport, fmt, pf, individual in [
        ("pickleball_singles", "pickleball", "knockout", "singles", False),
        ("snooker_knock", "snooker", "knockout", None, True),
        ("chess_knock", "chess", "knockout", None, True),
        ("tabletennis_singles", "tabletennis", "knockout", "singles", False),
        ("knockout_generic", "football", "knockout", None, False),
        ("swiss_football", "football", "swiss", None, False),
        ("double_elim", "football", "double_elimination", None, False),
    ]:
        ev = create_event(label, sport, fmt, player_format=pf)
        # For individual sports, still create 4 "teams" (backend represents individuals as teams under the hood too)
        add_teams(ev["id"], sport, n=4, individual=individual)
        generate_fixtures(ev["id"])
        seeds[label] = ev["id"]
        time.sleep(0.15)

    print("\n[seed] === Seeded event IDs ===")
    for k, v in seeds.items():
        print(f"  {k}: {v}")
    with open("/app/test_reports/iter35_event_ids.json", "w") as f:
        json.dump(seeds, f, indent=2)
    print("[seed] Saved to /app/test_reports/iter35_event_ids.json")

if __name__ == "__main__":
    main()
