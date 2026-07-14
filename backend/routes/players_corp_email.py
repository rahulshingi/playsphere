"""Corporate email verification for players.

Extracted from server.py (Jul 2026) as the first module of the ongoing
`server.py` refactor. The endpoints let a player who signed up with a
personal email attach + verify a work email — once verified, HR at that
company can discover the player through the /players/profiles search.

Endpoints:
  • POST /api/players/me/corporate-email/request-otp
  • POST /api/players/me/corporate-email/verify

Collections touched:
  • player_corp_otps    — pending verification codes (per user × email)
  • player_profiles     — mutated on success
  • users               — mirrored company_id for HR search
  • companies           — resolved company_name

No other module reads or writes these — safe to extract.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import Depends, HTTPException

from email_service import is_email_configured, send_otp_email


FREE_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "icloud.com", "protonmail.com",
})


def _email_domain(e: str | None) -> str:
    """Extract the lowercase domain from an email address, or '' if malformed."""
    if not e or "@" not in e:
        return ""
    return e.strip().lower().split("@", 1)[-1]


async def _auto_link_company_by_domain(db: Any, corporate_email: str) -> Optional[str]:
    """Best-effort: find a company_id whose company_admin shares the corporate email's domain."""
    domain = _email_domain(corporate_email)
    if not domain or domain in FREE_EMAIL_DOMAINS:
        return None
    company_admin: Optional[dict] = await db.users.find_one(
        {"role": "company_admin", "email": {"$regex": f"@{domain}$", "$options": "i"}, "company_id": {"$ne": None}},
        {"_id": 0, "company_id": 1},
    )
    if not company_admin:
        return None
    company_id: str = company_admin["company_id"]
    return company_id


def _assert_player(user: dict) -> None:
    """Enforce that the caller is a native player OR opted into also_player mode."""
    if user.get("role") != "player" and not user.get("also_player"):
        raise HTTPException(403, "Player only")


def register(api: Any, db: Any, deps: Any) -> None:
    get_current_user = deps.get_current_user

    @api.post("/players/me/corporate-email/request-otp")
    async def player_corporate_email_request_otp(
        body: dict,
        user: dict = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Send a 6-digit code to the player's work email for verification."""
        _assert_player(user)
        corp_email = ((body or {}).get("corporate_email") or "").strip().lower()
        if not corp_email or "@" not in corp_email:
            raise HTTPException(400, "Valid corporate email is required")
        if _email_domain(corp_email) in FREE_EMAIL_DOMAINS:
            raise HTTPException(400,
                "Please enter your official work email "
                "(personal providers like Gmail can't be verified as a company email).")
        if not is_email_configured():
            raise HTTPException(503, "Email service is not configured — please contact admin@kreedanation.com.")

        otp = f"{secrets.randbelow(1_000_000):06d}"
        now = datetime.now(timezone.utc)
        await db.player_corp_otps.update_one(
            {"user_id": user["id"], "corporate_email": corp_email},
            {"$set": {
                "user_id": user["id"], "corporate_email": corp_email, "otp": otp,
                "expires_at": (now + timedelta(minutes=10)).isoformat(),
                "attempts": 0, "created_at": now.isoformat(),
            }},
            upsert=True,
        )
        ok = send_otp_email(to=corp_email, otp=otp, company_name="your company at Kreeda Nation")
        if not ok:
            await db.player_corp_otps.delete_one({"user_id": user["id"], "corporate_email": corp_email})
            raise HTTPException(502, "Couldn't send the verification email. Please try again shortly.")
        return {"ok": True, "expires_in": 600, "corporate_email": corp_email}

    @api.post("/players/me/corporate-email/verify")
    async def player_corporate_email_verify(
        body: dict,
        user: dict = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Verify the OTP and link the corporate email + (best-effort) company_id."""
        _assert_player(user)
        corp_email = ((body or {}).get("corporate_email") or "").strip().lower()
        otp_input = ((body or {}).get("otp") or "").strip()
        if not (corp_email and otp_input):
            raise HTTPException(400, "corporate_email and otp are required")

        rec: Optional[dict] = await db.player_corp_otps.find_one(
            {"user_id": user["id"], "corporate_email": corp_email}
        )
        if not rec:
            raise HTTPException(400, "No verification request pending — request a code first.")

        exp = rec.get("expires_at", "")
        try:
            if datetime.fromisoformat(exp) < datetime.now(timezone.utc):
                raise HTTPException(400, "Verification code expired. Request a fresh one.")
        except (TypeError, ValueError):
            raise HTTPException(400, "Verification record corrupt — request a fresh code.")

        if int(rec.get("attempts") or 0) >= 5:
            raise HTTPException(429, "Too many attempts — request a fresh code.")

        if rec["otp"] != otp_input:
            await db.player_corp_otps.update_one({"_id": rec["_id"]}, {"$inc": {"attempts": 1}})
            raise HTTPException(400, "Incorrect code")

        # ✔ verified — try to auto-link company by domain
        company_id = await _auto_link_company_by_domain(db, corp_email)
        upd: dict[str, Any] = {
            "corporate_email": corp_email,
            "corporate_email_verified": True,
            "corporate_email_verified_at": datetime.now(timezone.utc).isoformat(),
        }
        company_name: Optional[str] = None
        if company_id:
            c: Optional[dict] = await db.companies.find_one(
                {"id": company_id}, {"_id": 0, "name": 1}
            )
            company_name = c["name"] if c else None
            upd["company_id"] = company_id
            upd["company_name"] = company_name

        await db.player_profiles.update_one({"user_id": user["id"]}, {"$set": upd})
        if company_id:
            await db.users.update_one({"id": user["id"]}, {"$set": {"company_id": company_id}})
        await db.player_corp_otps.delete_one({"_id": rec["_id"]})

        return {
            "ok": True,
            "corporate_email": corp_email,
            "linked_company_id": company_id,
            "linked_company_name": company_name,
            "message": (
                f"Corporate email verified · linked to {company_name}"
                if company_name
                else "Corporate email verified. When your HR joins Kreeda Nation, "
                     "you'll be auto-linked to their roster."
            ),
        }
