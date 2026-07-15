"""Admin-triggerable seeds for production repair.

Currently exposes one endpoint:

  POST /api/admin/seed/demo-vendor
       — Re-runs `scripts/seed_demo_vendor.py::main()` inline against the
         live DB. Platform-admin only. Idempotent — safe to hit multiple
         times; passwords are reset to `vendor123` each time.

This exists so the user can repair prod without shell access. It's the
same code path as the CLI seed script — no divergence.
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException


def register(api: Any, db: Any, deps: Any) -> None:
    require_platform_admin = deps.require_platform_admin

    @api.post("/admin/seed/demo-vendor")
    async def seed_demo_vendor(_: dict = Depends(require_platform_admin)) -> dict[str, Any]:
        try:
            from scripts import seed_demo_vendor  # type: ignore[import-not-found]
        except ImportError:
            try:
                # Fall back to a direct file import when /app/backend/scripts
                # isn't on sys.path (production may vary).
                import importlib.util
                import os
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
