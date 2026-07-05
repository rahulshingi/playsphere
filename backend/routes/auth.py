"""Authentication, registration, company signup, and password reset routes.

Wired via `register(api, db, deps)` from server.py. The `deps` namespace bundles all
helpers/models needed so the closure stays clean.

**Refactored in iteration 33** — the single 321-line `register()` closure was broken
into four thematic module-level helpers so each concern is testable in isolation:

  * `_register_core_auth`        — /auth/{register,login,logout,me}
  * `_register_signup_otp`       — request-otp endpoints for company/vendor/player/organiser
  * `_register_signup`           — /companies/signup, /organisers/signup, /companies/me
  * `_register_password_reset`   — forgot-password + reset-password

The top-level `register()` now just wires each sub-register — no behaviour change.
"""
import os
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from fastapi import Depends, HTTPException, Response

from email_service import send_otp_email, send_password_reset_email, is_email_configured

logger = logging.getLogger("kreeda.routes.auth")

# ---------------------------------------------------------------------------
# Free / personal email providers — blocked from company signup
# ---------------------------------------------------------------------------
FREE_EMAIL_DOMAINS = {
    # Google
    "gmail.com", "googlemail.com",
    # Yahoo
    "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "ymail.com", "rocketmail.com",
    # Microsoft
    "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com", "msn.com",
    # Apple
    "icloud.com", "me.com", "mac.com",
    # AOL / Verizon
    "aol.com",
    # ProtonMail
    "protonmail.com", "proton.me", "pm.me",
    # Russian / German
    "yandex.com", "yandex.ru", "gmx.com", "gmx.de", "web.de", "mail.ru",
    # Indian personal
    "rediffmail.com", "rediff.com",
    # Other free / disposable
    "tutanota.com", "fastmail.com", "hushmail.com", "inbox.com",
    "zoho.com",  # personal Zoho — business uses zoho-domains
    # Disposable / temporary
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "tempmail.com",
    "trashmail.com", "throwawaymail.com", "yopmail.com",
}


# ---------------------------------------------------------------------------
# Module-level helpers (imported by other route files too)
# ---------------------------------------------------------------------------
def _slugify(s: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out or "company"


def _domain_of(email: str) -> str:
    return (email.split("@", 1)[1] if "@" in email else "").strip().lower()


def _is_corporate_email(email: str) -> bool:
    return _domain_of(email) not in FREE_EMAIL_DOMAINS


def _consume_signup_otp_sync(db, collection_name: str):
    """Standalone OTP consumer reusable by routes outside routes/auth.py.

    Returns an async function (email, otp_input) -> None that validates the OTP record,
    increments attempts on mismatch, and raises HTTPException on any failure. Marking
    the OTP as 'used' is left to the caller (so they can do it after the user/profile
    insert succeeds, preventing the OTP from being burnt if the downstream create fails).
    """
    async def _consume(email: str, otp_input: str):
        rec = await db[collection_name].find_one({"email": email})
        if not rec:
            raise HTTPException(400, "No verification code has been requested for this email. Request one first.")
        if rec.get("expires_at") < datetime.now(timezone.utc).isoformat():
            raise HTTPException(400, "Verification code has expired. Request a new one.")
        if (rec.get("attempts") or 0) >= 5:
            raise HTTPException(429, "Too many incorrect attempts. Request a new verification code.")
        if (otp_input or "").strip() != rec.get("otp"):
            await db[collection_name].update_one({"email": email}, {"$inc": {"attempts": 1}})
            raise HTTPException(400, "Incorrect verification code. Please double-check the email we sent.")
    return _consume


def _generate_otp() -> str:
    # 6-digit numeric, cryptographically secure (CSPRNG-backed) — protects signup/password-reset codes.
    return f"{secrets.randbelow(1000000):06d}"


async def _issue_signup_otp(db, *, email: str, label: str, display_name: str,
                            otp_collection: str, require_corporate: bool):
    """Shared OTP issuance for company / vendor / player / organiser signup flows.

    Extracted from the previous closure so it can be unit-tested + reused by any
    signup route added in future without a nested-closure indirection.
    """
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email is required")
    if require_corporate and not _is_corporate_email(email):
        raise HTTPException(
            400,
            "Please use your official company email — public providers like Gmail, Yahoo, Outlook etc. aren't supported for company signups.",
        )
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "An account already exists with that email — sign in instead.")
    if not is_email_configured():
        raise HTTPException(503, "Email service is not configured yet — please contact admin@kreedanation.com to complete onboarding.")
    otp = _generate_otp()
    now = datetime.now(timezone.utc)
    await db[otp_collection].update_one(
        {"email": email},
        {"$set": {
            "email": email, "otp": otp, "display_name": display_name,
            "expires_at": (now + timedelta(minutes=10)).isoformat(),
            "verified": False, "attempts": 0,
            "created_at": now.isoformat(),
        }},
        upsert=True,
    )
    if not send_otp_email(to=email, otp=otp, company_name=display_name):
        await db[otp_collection].delete_one({"email": email})
        raise HTTPException(502, "We couldn't send the verification email right now. Please try again in a few minutes.")
    logger.info("%s OTP issued | email=%s ttl=600s", label, email)
    return {"ok": True, "expires_in": 600, "email": email}


async def _unique_company_slug(db, company_name: str) -> str:
    """Generate a unique slug for a new company/organiser doc."""
    base = _slugify(company_name)
    slug = base
    n = 1
    while await db.companies.find_one({"slug": slug}):
        n += 1
        slug = f"{base}-{n}"
    return slug


# ============================================================================
# Sub-registrars — each owns a slice of the auth surface area
# ============================================================================
def _register_core_auth(api, db, ctx: SimpleNamespace):
    """/auth/register, /auth/login, /auth/logout, /auth/me."""
    UserPublic = ctx.UserPublic
    RegisterBody = ctx.RegisterBody
    LoginBody = ctx.LoginBody

    @api.post("/auth/register", response_model=UserPublic)
    async def auth_register(body: RegisterBody, response: Response):
        email = body.email.lower()
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": body.name,
            "role": "viewer",
            "company_id": None,
            "password_hash": ctx.hash_password(body.password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
        token = ctx.create_access_token(user["id"], user["email"], user["role"], None)
        ctx.set_auth_cookie(response, token)
        return UserPublic(**await ctx._user_with_company(user))

    @api.post("/auth/login", response_model=UserPublic)
    async def auth_login(body: LoginBody, response: Response):
        # Guard against copy-paste whitespace — a common cause of "correct
        # password but still fails" reports from real users.
        email = (body.email or "").strip().lower()
        password = (body.password or "").rstrip("\r\n\t ")
        user = await db.users.find_one({"email": email})
        if not user or not ctx.verify_password(password, user["password_hash"]):
            reason = "no-user" if not user else "bad-password"
            logger.info("LOGIN FAIL email=%s reason=%s", email, reason)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if user.get("disabled"):
            raise HTTPException(
                status_code=403,
                detail="Your account has been disabled. Please contact admin with admin email: admin@kreedanation.com",
            )
        token = ctx.create_access_token(user["id"], user["email"], user["role"], user.get("company_id"))
        ctx.set_auth_cookie(response, token)
        return UserPublic(**await ctx._user_with_company(user))

    @api.post("/auth/logout")
    async def auth_logout(response: Response):
        response.delete_cookie("access_token", path="/")
        return {"ok": True}

    @api.get("/auth/me", response_model=UserPublic)
    async def auth_me(user: dict = Depends(ctx.get_current_user)):
        return UserPublic(**await ctx._user_with_company(user))


def _register_signup_otp(api, db):
    """POST /{companies,vendors,players,organisers}/signup/request-otp."""

    @api.post("/companies/signup/request-otp")
    async def company_signup_request_otp(body: dict):
        return await _issue_signup_otp(
            db,
            email=(body or {}).get("admin_email", ""),
            display_name=(body or {}).get("company_name", ""),
            label="Company signup",
            otp_collection="company_signup_otps",
            require_corporate=True,
        )

    @api.post("/vendors/signup/request-otp")
    async def vendor_signup_request_otp(body: dict):
        return await _issue_signup_otp(
            db,
            email=(body or {}).get("email", ""),
            display_name=(body or {}).get("business_name", ""),
            label="Vendor signup",
            otp_collection="vendor_signup_otps",
            require_corporate=False,
        )

    @api.post("/players/signup/request-otp")
    async def player_signup_request_otp(body: dict):
        return await _issue_signup_otp(
            db,
            email=(body or {}).get("email", ""),
            display_name=(body or {}).get("name", ""),
            label="Player signup",
            otp_collection="player_signup_otps",
            require_corporate=False,
        )

    @api.post("/organisers/signup/request-otp")
    async def organiser_signup_request_otp(body: dict):
        return await _issue_signup_otp(
            db,
            email=(body or {}).get("admin_email", ""),
            display_name=(body or {}).get("organiser_name", ""),
            label="Organiser signup",
            otp_collection="organiser_signup_otps",
            require_corporate=False,
        )


def _register_signup(api, db, ctx: SimpleNamespace):
    """Company + organiser signup (POST /*/signup) + /companies/me + /companies."""
    UserPublic = ctx.UserPublic
    CompanySignupBody = ctx.CompanySignupBody
    Company = ctx.Company
    consume_org_otp = _consume_signup_otp_sync(db, "organiser_signup_otps")
    consume_co_otp = _consume_signup_otp_sync(db, "company_signup_otps")

    @api.post("/organisers/signup", response_model=UserPublic)
    async def organiser_signup(body: CompanySignupBody, response: Response):
        """Independent tournament organiser signup. Mirrors company signup but with
        no corporate-email rule. Creates a `companies` doc tagged
        `org_type="organiser"` and a user with role `organiser` — same event/booking
        powers as company_admin.
        """
        email = body.admin_email.lower()
        otp_input = (getattr(body, "otp", None) or "").strip()
        if not otp_input:
            raise HTTPException(400, "Email verification code is required. Request one before signing up.")
        await consume_org_otp(email, otp_input)

        if await db.users.find_one({"email": email}):
            raise HTTPException(400, "Email already registered")
        slug = await _unique_company_slug(db, body.company_name)
        org = Company(
            name=body.company_name, slug=slug,
            logo_url=body.logo_url or "", contact_email=email,
            contact_phone=body.contact_phone or "", address_line=body.address_line or "",
            area=body.area or "", city=body.city or "", state=body.state or "",
            pincode=body.pincode or "",
        )
        org_doc = org.model_dump()
        org_doc["org_type"] = "organiser"  # distinguishes from corporate companies
        user_id = str(uuid.uuid4())
        org_doc["owner_user_id"] = user_id
        await db.companies.insert_one(org_doc)
        user_doc = {
            "id": user_id, "email": email, "name": body.admin_name,
            "role": "organiser", "company_id": org.id,
            "password_hash": ctx.hash_password(body.admin_password),
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)
        await db.organiser_signup_otps.update_one(
            {"email": email},
            {"$set": {"verified": True, "used_at": datetime.now(timezone.utc).isoformat()}},
        )
        token = ctx.create_access_token(user_id, email, "organiser", org.id)
        ctx.set_auth_cookie(response, token)
        return UserPublic(**await ctx._user_with_company(user_doc))

    @api.post("/companies/signup", response_model=UserPublic)
    async def company_signup(body: CompanySignupBody, response: Response):
        email = body.admin_email.lower()
        if not _is_corporate_email(email):
            raise HTTPException(
                400,
                "Please use your official company email — public providers like Gmail, Yahoo, Outlook etc. aren't supported for company signups.",
            )
        otp_input = (getattr(body, "otp", None) or "").strip()
        if not otp_input:
            raise HTTPException(400, "Email verification code is required. Request one before signing up.")
        await consume_co_otp(email, otp_input)

        if await db.users.find_one({"email": email}):
            raise HTTPException(400, "Email already registered")
        slug = await _unique_company_slug(db, body.company_name)
        company = Company(
            name=body.company_name, slug=slug,
            logo_url=body.logo_url or "", contact_email=email,
            contact_phone=body.contact_phone or "", address_line=body.address_line or "",
            area=body.area or "", city=body.city or "", state=body.state or "",
            pincode=body.pincode or "",
        )
        user_id = str(uuid.uuid4())
        company.owner_user_id = user_id
        await db.companies.insert_one(company.model_dump())
        user_doc = {
            "id": user_id, "email": email, "name": body.admin_name,
            "role": "company_admin", "company_id": company.id,
            "password_hash": ctx.hash_password(body.admin_password),
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)
        await db.company_signup_otps.update_one(
            {"email": email},
            {"$set": {"verified": True, "used_at": datetime.now(timezone.utc).isoformat()}},
        )
        token = ctx.create_access_token(user_id, email, "company_admin", company.id)
        ctx.set_auth_cookie(response, token)
        return UserPublic(**await ctx._user_with_company(user_doc))

    @api.get("/companies/me")
    async def get_my_company(user: dict = Depends(ctx.require_company_admin)):
        if not user.get("company_id"):
            raise HTTPException(404, "No company")
        c = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Company not found")
        return c

    @api.patch("/companies/me")
    async def update_my_company(body: dict, user: dict = Depends(ctx.require_company_admin)):
        body.pop("id", None)
        body.pop("slug", None)
        body.pop("owner_user_id", None)
        await db.companies.update_one({"id": user["company_id"]}, {"$set": body})
        return await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})

    @api.get("/companies")
    async def list_companies(_: dict = Depends(ctx.require_platform_admin)):
        return await db.companies.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


def _register_password_reset(api, db, ctx: SimpleNamespace):
    """POST /{auth,players}/forgot-password + /{auth,players}/reset-password."""

    @api.post("/players/forgot-password")
    @api.post("/auth/forgot-password")
    async def forgot_password(body: dict):
        email = ((body or {}).get("email") or "").strip().lower()
        if not email:
            raise HTTPException(400, "email required")
        user = await db.users.find_one({"email": email})
        # Don't leak whether email exists; respond OK either way.
        if user:
            token = secrets.token_urlsafe(32)
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            await db.password_resets.insert_one({
                "token": token, "user_id": user["id"], "email": email,
                "role": user.get("role", ""),
                "expires_at": expires_at, "used": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            frontend = os.environ.get("FRONTEND_URL") or ""
            reset_url = f"{frontend.rstrip('/')}/reset-password?token={token}" if frontend else f"/reset-password?token={token}"
            # Send via SendGrid; if it fails, the link is still in the backend log as a fallback for ops.
            sent = send_password_reset_email(to=email, reset_url=reset_url, name=user.get("name", ""))
            if not sent:
                logger.warning("PASSWORD RESET LINK for %s: %s", email, reset_url)
            else:
                logger.info("PASSWORD RESET EMAIL sent for %s", email)
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
            {"$set": {"password_hash": ctx.hash_password(new_password), "must_reset": False}},
        )
        await db.password_resets.update_one({"token": token}, {"$set": {"used": True}})
        return {"ok": True}


# ============================================================================
# Top-level registrar — thin orchestrator, no logic of its own
# ============================================================================
def register(api, db, deps):
    """Wire every auth-related route onto `api`. See module docstring for the
    breakdown into sub-registrars."""
    ctx = SimpleNamespace(
        UserPublic=deps.UserPublic,
        RegisterBody=deps.RegisterBody,
        LoginBody=deps.LoginBody,
        CompanySignupBody=deps.CompanySignupBody,
        Company=deps.Company,
        hash_password=deps.hash_password,
        verify_password=deps.verify_password,
        create_access_token=deps.create_access_token,
        set_auth_cookie=deps.set_auth_cookie,
        get_current_user=deps.get_current_user,
        require_company_admin=deps.require_company_admin,
        require_platform_admin=deps.require_platform_admin,
        _user_with_company=deps._user_with_company,
    )
    _register_core_auth(api, db, ctx)
    _register_signup_otp(api, db)
    _register_signup(api, db, ctx)
    _register_password_reset(api, db, ctx)
