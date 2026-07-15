"""Admin-triggerable ops for production repair.

Endpoints:
  • POST /api/admin/seed/demo-vendor              — reseed demo vendor (idempotent)
  • POST /api/admin/users/{user_id}/reset-password — reset any user's password
    and email them a temp-password + one-click reset link (1h TTL)

Platform-admin only.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import Depends, HTTPException

from email_service import send_admin_password_reset_email


def register(api: Any, db: Any, deps: Any) -> None:
    require_platform_admin = deps.require_platform_admin
    hash_password = deps.hash_password

    @api.post("/admin/seed/demo-vendor")
    async def seed_demo_vendor(_: dict = Depends(require_platform_admin)) -> dict[str, Any]:
        try:
            from scripts import seed_demo_vendor  # type: ignore[import-not-found]
        except ImportError:
            try:
                import importlib.util
                here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                path = os.path.join(here, "scripts", "seed_demo_vendor.py")
                spec = importlib.util.spec_from_file_location("seed_demo_vendor", path)
                if spec is None or spec.loader is None:
                    raise HTTPException(500, "Cannot locate seed_demo_vendor.py")
                seed_demo_vendor = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(seed_demo_vendor)
            except Exception as exc:
                raise HTTPException(500, f"Seed module unavailable: {exc}")

        try:
            await seed_demo_vendor.main()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"Seed failed: {exc}")

        return {
            "ok": True,
            "primary_email": seed_demo_vendor.VENDOR_EMAIL,
            "alias_email": seed_demo_vendor.VENDOR_EMAIL_ALIAS,
            "password": seed_demo_vendor.VENDOR_PASSWORD,
            "landing": "/vendor/overview",
            "note": "Both emails now log in with the shared demo password.",
        }

    @api.post("/admin/users/{user_id}/reset-password")
    async def admin_reset_user_password(
        user_id: str,
        body: dict | None = None,
        actor: dict = Depends(require_platform_admin),
    ) -> dict[str, Any]:
        """Reset any user's password + email them a temp password + reset link.

        Body (all optional):
          {new_password?: str}   — supply your own; else we generate a 10-char temp

        Flow:
          1. Mints a 10-char temp password (or uses the caller's)
          2. Updates `users.password_hash` + sets `must_reset=true` so first login
             forces a real change
          3. Mints a `password_resets` token (1h TTL) — reuses the existing flow
          4. Sends email with temp password + reset link
          5. Writes an audit-log entry (best-effort)
        """
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(404, "User not found")

        new_password = ((body or {}).get("new_password") or "").strip()
        if not new_password:
            # Auto-generate — 10 chars, url-safe, not confusable
            new_password = secrets.token_urlsafe(9)[:10]
        if len(new_password) < 6:
            raise HTTPException(400, "Password must be at least 6 characters")

        now = datetime.now(timezone.utc)
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "password_hash": hash_password(new_password),
                "must_reset": True,
                "password_reset_by_admin_at": now.isoformat(),
                "password_reset_by_admin_id": actor["id"],
            }},
        )

        # Mint a reset token so the email's button lands on /reset-password?token=…
        token = secrets.token_urlsafe(32)
        await db.password_resets.insert_one({
            "token": token, "user_id": user_id, "email": user["email"],
            "role": user.get("role", ""),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "used": False,
            "created_at": now.isoformat(),
            "issued_by_admin_id": actor["id"],
        })

        frontend = os.environ.get("FRONTEND_URL") or "https://kreedanation.com"
        reset_url = f"{frontend.rstrip('/')}/reset-password?token={token}"

        email_sent = False
        try:
            email_sent = send_admin_password_reset_email(
                to=user["email"],
                temp_password=new_password,
                reset_url=reset_url,
                name=user.get("name", ""),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[admin_reset_password] email failed: {exc}")

        # Audit log — best-effort, don't fail the reset if it errors
        try:
            await db.admin_audit_log.insert_one({
                "action": "password_reset",
                "target_user_id": user_id,
                "target_email": user["email"],
                "actor_id": actor["id"],
                "actor_email": actor.get("email"),
                "email_sent": email_sent,
                "at": now.isoformat(),
            })
        except Exception:
            pass

        return {
            "ok": True,
            "user_id": user_id,
            "email": user["email"],
            "temp_password": new_password,
            "reset_url": reset_url,
            "email_sent": email_sent,
            "note": "User will be forced to pick a new password on next login (must_reset=true).",
        }

