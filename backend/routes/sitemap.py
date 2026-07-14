"""Sitemap.xml + robots.txt — dynamic FastAPI endpoints (under /api) and a
startup task that also drops static snapshots into `/app/frontend/public/`.

Search engines fetch these from the root, and Kubernetes ingress routes root
paths to the frontend — so we materialise physical files during backend
startup, then re-materialise on-demand via `POST /api/admin/sitemap/rebuild`.

Endpoints:
  • GET /api/sitemap.xml           — dynamic, always fresh
  • GET /api/robots.txt            — dynamic, always fresh
  • POST /api/admin/sitemap/rebuild — regenerates the static snapshots

Static file locations (served by the frontend at the root):
  • /app/frontend/public/sitemap.xml → https://kreedanation.com/sitemap.xml
  • /app/frontend/public/robots.txt  → https://kreedanation.com/robots.txt
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, HTTPException
from fastapi.responses import Response


PUBLIC_BASE_URL_DEFAULT = "https://kreedanation.com"
STATIC_DIR = Path("/app/frontend/public")


def _public_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", PUBLIC_BASE_URL_DEFAULT).rstrip("/")


def _xml_escape(s: str | None) -> str:
    return (str(s or "")
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


def _iso_date(dt: Any) -> str:
    if not dt:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(dt, str):
        return dt[:10]
    try:
        result: str = dt.date().isoformat()
        return result
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


STATIC_ROUTES: list[tuple[str, str, str]] = [
    # path,                    priority, changefreq
    ("/",                       "1.0",   "daily"),
    ("/events",                 "0.9",   "daily"),
    ("/hire",                   "0.9",   "daily"),
    ("/corporate-services",     "0.9",   "weekly"),
    ("/sponsorships",           "0.8",   "daily"),
    ("/sponsors",               "0.7",   "weekly"),
    ("/players/profiles",       "0.7",   "weekly"),
    ("/about",                  "0.6",   "monthly"),
    ("/contact",                "0.6",   "monthly"),
    ("/standings",              "0.6",   "daily"),
    ("/register",               "0.5",   "monthly"),
    ("/signup-company",         "0.5",   "monthly"),
    ("/signup-organiser",       "0.5",   "monthly"),
    ("/players/signup",         "0.5",   "monthly"),
    ("/vendor/signup",          "0.5",   "monthly"),
    ("/sponsor/signup",         "0.5",   "monthly"),
    ("/login",                  "0.4",   "yearly"),
]


ROBOTS_TEMPLATE = """# Kreeda Nation — search-engine crawler config
User-agent: *
Allow: /
Disallow: /api/
Disallow: /platform-admin
Disallow: /vendor/dashboard
Disallow: /scorer/dashboard
Disallow: /dashboard
Disallow: /admin
Disallow: /bookings
Disallow: /rfqs
Disallow: /auth/
Disallow: /players/me
Disallow: /my-memberships

Sitemap: {base}/sitemap.xml
"""


async def build_sitemap_xml(db: Any, base_url: str) -> str:
    urls: list[str] = []
    today = datetime.now(timezone.utc).date().isoformat()

    # Static routes
    for path, pri, freq in STATIC_ROUTES:
        urls.append(
            f"  <url>\n"
            f"    <loc>{_xml_escape(base_url + path)}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{pri}</priority>\n"
            f"  </url>"
        )

    # Public events
    try:
        cursor = db.events.find(
            {"$or": [{"approval_status": {"$exists": False}}, {"approval_status": "approved"}],
             "hidden": {"$ne": True}},
            {"_id": 0, "id": 1, "updated_at": 1, "created_at": 1},
        ).limit(2000)
        async for e in cursor:
            if not e.get("id"):
                continue
            lastmod = _iso_date(e.get("updated_at") or e.get("created_at"))
            loc = f"{base_url}/events/{e['id']}"
            urls.append(
                f"  <url>\n"
                f"    <loc>{_xml_escape(loc)}</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                f"    <changefreq>weekly</changefreq>\n"
                f"    <priority>0.7</priority>\n"
                f"  </url>"
            )
    except Exception as exc:
        print(f"[sitemap] events fetch failed: {exc}")

    # Approved vendor listings
    try:
        cursor = db.vendor_listings.find(
            {"approval_status": {"$in": ["approved", None]}, "active": {"$ne": False}},
            {"_id": 0, "id": 1, "updated_at": 1, "created_at": 1},
        ).limit(2000)
        async for v in cursor:
            if not v.get("id"):
                continue
            lastmod = _iso_date(v.get("updated_at") or v.get("created_at"))
            loc = f"{base_url}/vendor-listing/{v['id']}"
            urls.append(
                f"  <url>\n"
                f"    <loc>{_xml_escape(loc)}</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                f"    <changefreq>weekly</changefreq>\n"
                f"    <priority>0.6</priority>\n"
                f"  </url>"
            )
    except Exception as exc:
        print(f"[sitemap] vendor_listings fetch failed: {exc}")

    # Player public profiles
    try:
        cursor = db.player_profiles.find(
            {"slug": {"$exists": True, "$ne": None}, "profile_visibility": {"$ne": "private"}},
            {"_id": 0, "slug": 1, "updated_at": 1, "created_at": 1},
        ).limit(5000)
        async for p in cursor:
            slug = p.get("slug")
            if not slug:
                continue
            lastmod = _iso_date(p.get("updated_at") or p.get("created_at"))
            loc = f"{base_url}/p/{slug}"
            urls.append(
                f"  <url>\n"
                f"    <loc>{_xml_escape(loc)}</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                f"    <changefreq>monthly</changefreq>\n"
                f"    <priority>0.5</priority>\n"
                f"  </url>"
            )
    except Exception as exc:
        print(f"[sitemap] player_profiles fetch failed: {exc}")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) +
        "\n</urlset>\n"
    )


async def write_static_snapshots(db: Any) -> dict[str, Any]:
    """Write /app/frontend/public/sitemap.xml + robots.txt. Returns counts."""
    base = _public_base_url()
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    xml = await build_sitemap_xml(db, base)
    (STATIC_DIR / "sitemap.xml").write_text(xml, encoding="utf-8")
    (STATIC_DIR / "robots.txt").write_text(ROBOTS_TEMPLATE.format(base=base), encoding="utf-8")
    return {"sitemap_urls": xml.count("<loc>"), "base": base}


def register(api: Any, app: Any, db: Any, deps: Any) -> None:
    require_platform_admin = deps.require_platform_admin

    @api.get("/sitemap.xml", include_in_schema=False)
    async def sitemap_api(base: Optional[str] = None) -> Response:
        base_url = (base or _public_base_url()).rstrip("/")
        body = await build_sitemap_xml(db, base_url)
        return Response(
            content=body,
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @api.get("/robots.txt", include_in_schema=False)
    async def robots_api() -> Response:
        body = ROBOTS_TEMPLATE.format(base=_public_base_url())
        return Response(
            content=body,
            media_type="text/plain",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @api.post("/admin/sitemap/rebuild")
    async def rebuild(_: dict = Depends(require_platform_admin)) -> dict[str, Any]:
        try:
            info = await write_static_snapshots(db)
            return {"ok": True, **info, "written_at": datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            raise HTTPException(500, f"Rebuild failed: {exc}")

    # Register a startup hook via FastAPI app.on_event
    @app.on_event("startup")
    async def _seed_sitemap_on_startup() -> None:
        try:
            info = await write_static_snapshots(db)
            print(f"[sitemap] snapshot written ({info['sitemap_urls']} urls, base={info['base']})")
        except Exception as exc:
            print(f"[sitemap] startup snapshot failed: {exc}")
