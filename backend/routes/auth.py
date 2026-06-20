"""Authentication, registration, company signup, and password reset routes.

Wired via `register(api, db, deps)` from server.py. The `deps` namespace bundles all
helpers/models needed so the closure stays clean.
"""
import os
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from fastapi import Depends, HTTPException, Response

from email_service import send_otp_email, send_password_reset_email, is_email_configured

logger = logging.getLogger("kreeda.routes.auth")

# Free / personal email providers — blocked from company signup
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
    increments attempts on mismatch, and raises HTTPException on any failure. Marking the
    OTP as 'used' is left to the caller (so they can do it after the user/profile insert
    succeeds, preventing the OTP from being burnt if the downstream create fails)."""
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


def register(api, db, deps):
    """deps is an object exposing:
    UserPublic, RegisterBody, LoginBody, CompanySignupBody, Company,
    hash_password, verify_password, create_access_token, set_auth_cookie,
    get_current_user, require_company_admin, require_platform_admin, _user_with_company.
    """
    UserPublic = deps.UserPublic
    RegisterBody = deps.RegisterBody
    LoginBody = deps.LoginBody
    CompanySignupBody = deps.CompanySignupBody
    Company = deps.Company
    hash_password = deps.hash_password
    verify_password = deps.verify_password
    create_access_token = deps.create_access_token
    set_auth_cookie = deps.set_auth_cookie
    get_current_user = deps.get_current_user
    require_company_admin = deps.require_company_admin
    require_platform_admin = deps.require_platform_admin
    _user_with_company = deps._user_with_company

    @api.post("/auth/register", response_model=UserPublic)
    async def auth_register(body: RegisterBody, response: Response):
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
    async def auth_login(body: LoginBody, response: Response):
        email = body.email.lower()
        user = await db.users.find_one({"email": email})
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if user.get("disabled"):
            raise HTTPException(
                status_code=403,
                detail="Your account has been disabled. Please contact admin with admin email: admin@kreedanation.com",
            )
        token = create_access_token(user["id"], user["email"], user["role"], user.get("company_id"))
        set_auth_cookie(response, token)
        return UserPublic(**await _user_with_company(user))

    @api.post("/auth/logout")
    async def auth_logout(response: Response):
        response.delete_cookie("access_token", path="/")
        return {"ok": True}

    @api.get("/auth/me", response_model=UserPublic)
    async def auth_me(user: dict = Depends(get_current_user)):
        return UserPublic(**await _user_with_company(user))

    async def _issue_signup_otp(*, email: str, label: str, display_name: str = "",
                                otp_collection: str, require_corporate: bool):
        """Shared OTP issuance for company / vendor / player signup flows."""
        email = email.strip().lower()
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

    async def _consume_signup_otp(*, email: str, otp_input: str, otp_collection: str):
        """Closure-level wrapper around the module-level consumer (single source of truth)."""
        await _consume_signup_otp_sync(db, otp_collection)(email, otp_input)

    @api.post("/companies/signup/request-otp")
    async def company_signup_request_otp(body: dict):
        return await _issue_signup_otp(
            email=(body or {}).get("admin_email", ""),
            display_name=(body or {}).get("company_name", ""),
            label="Company signup",
            otp_collection="company_signup_otps",
            require_corporate=True,
        )

    @api.post("/vendors/signup/request-otp")
    async def vendor_signup_request_otp(body: dict):
        return await _issue_signup_otp(
            email=(body or {}).get("email", ""),
            display_name=(body or {}).get("business_name", ""),
            label="Vendor signup",
            otp_collection="vendor_signup_otps",
            require_corporate=False,
        )

    @api.post("/players/signup/request-otp")
    async def player_signup_request_otp(body: dict):
        return await _issue_signup_otp(
            email=(body or {}).get("email", ""),
            display_name=(body or {}).get("name", ""),
            label="Player signup",
            otp_collection="player_signup_otps",
            require_corporate=False,
        )

    @api.post("/organisers/signup/request-otp")
    async def organiser_signup_request_otp(body: dict):
        return await _issue_signup_otp(
            email=(body or {}).get("admin_email", ""),
            display_name=(body or {}).get("organiser_name", ""),
            label="Organiser signup",
            otp_collection="organiser_signup_otps",
            require_corporate=False,
        )

    @api.post("/organisers/signup", response_model=UserPublic)
    async def organiser_signup(body: CompanySignupBody, response: Response):
        """Independent tournament organiser signup. Mirrors company signup but with no
        corporate-email rule. Creates a `companies` doc tagged `org_type="organiser"`
        and a user with role `organiser` — same event/booking powers as company_admin."""
        email = body.admin_email.lower()
        otp_input = (getattr(body, "otp", None) or "").strip()
        if not otp_input:
            raise HTTPException(400, "Email verification code is required. Request one before signing up.")
        await _consume_signup_otp(email=email, otp_input=otp_input, otp_collection="organiser_signup_otps")

        if await db.users.find_one({"email": email}):
            raise HTTPException(400, "Email already registered")
        base_slug = _slugify(body.company_name)
        slug = base_slug
        n = 1
        while await db.companies.find_one({"slug": slug}):
            n += 1
            slug = f"{base_slug}-{n}"
        org = Company(
            name=body.company_name,
            slug=slug,
            logo_url=body.logo_url or "",
            contact_email=email,
            contact_phone=body.contact_phone or "",
        )
        org_doc = org.model_dump()
        org_doc["org_type"] = "organiser"  # distinguishes from corporate companies
        user_id = str(uuid.uuid4())
        org_doc["owner_user_id"] = user_id
        await db.companies.insert_one(org_doc)
        user_doc = {
            "id": user_id,
            "email": email,
            "name": body.admin_name,
            "role": "organiser",
            "company_id": org.id,
            "password_hash": hash_password(body.admin_password),
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)
        await db.organiser_signup_otps.update_one(
            {"email": email}, {"$set": {"verified": True, "used_at": datetime.now(timezone.utc).isoformat()}}
        )
        token = create_access_token(user_id, email, "organiser", org.id)
        set_auth_cookie(response, token)
        return UserPublic(**await _user_with_company(user_doc))

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
        await _consume_signup_otp(email=email, otp_input=otp_input, otp_collection="company_signup_otps")

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
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)
        await db.company_signup_otps.update_one(
            {"email": email}, {"$set": {"verified": True, "used_at": datetime.now(timezone.utc).isoformat()}}
        )
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
            {"$set": {"password_hash": hash_password(new_password), "must_reset": False}},
        )
        await db.password_resets.update_one({"token": token}, {"$set": {"used": True}})
        return {"ok": True}
