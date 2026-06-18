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

logger = logging.getLogger("kreeda.routes.auth")


def _slugify(s: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out or "company"


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

    @api.post("/players/forgot-password")
    @api.post("/auth/forgot-password")
    async def forgot_password(body: dict):
        email = ((body or {}).get("email") or "").strip().lower()
        if not email:
            raise HTTPException(400, "email required")
        user = await db.users.find_one({"email": email})
        # Don't leak whether email exists; respond OK either way
        if user:
            token = secrets.token_urlsafe(32)
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
