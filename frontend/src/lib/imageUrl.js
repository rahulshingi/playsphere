/**
 * Resolve an image URL stored in the database to one the browser can fetch.
 *
 * The platform stores uploads as RELATIVE paths (`/api/uploads/<id>`) so the same
 * value works across preview and production. External URLs (https://…) and data:
 * URIs are returned unchanged.
 *
 * Also handles legacy URLs that hard-coded an old preview hostname: we detect the
 * `/api/uploads/` segment and replace whatever host came before with the current
 * REACT_APP_BACKEND_URL. This silently heals images that were uploaded before the
 * Feb-22 backend-storage refactor.
 */
export function resolveImageUrl(value) {
  if (!value) return "";
  // data: URIs and external CDNs pass through.
  if (value.startsWith("data:") || (value.startsWith("http") && !value.includes("/api/uploads/"))) {
    return value;
  }
  // Heal legacy absolute URLs by stripping any host before `/api/uploads/`.
  const idx = value.indexOf("/api/uploads/");
  if (idx >= 0) {
    return `${process.env.REACT_APP_BACKEND_URL}${value.slice(idx)}`;
  }
  // Relative path: prefix with backend URL.
  if (value.startsWith("/")) return `${process.env.REACT_APP_BACKEND_URL}${value}`;
  return value;
}

const FALLBACK = "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=400&w=400";

/** onError handler that swaps in a neutral fallback so a 404 doesn't show the broken-image icon. */
export function imageOnError(e) {
  if (e?.currentTarget && e.currentTarget.src !== FALLBACK) {
    e.currentTarget.src = FALLBACK;
  }
}

/**
 * Install ONE document-level capture-phase listener that heals broken <img> URLs across
 * the entire app. Two heal steps applied in order:
 *
 *  1) **Hostname rewrite** — if the URL is an absolute one containing `/api/uploads/`
 *     (typically a legacy preview-hostname URL from before backend storage was added),
 *     swap the host for the CURRENT REACT_APP_BACKEND_URL and try again ONCE.
 *  2) **Graceful fallback** — if it still fails, swap to a neutral Pexels placeholder so
 *     the broken-image icon never shows.
 *
 * This means we don't have to touch the 17 pages that render uploaded images — they all
 * benefit from this one hook. Idempotent: only installs once even if hot-reloaded.
 */
let _installed = false;
export function installGlobalImageHealer() {
  if (_installed || typeof document === "undefined") return;
  _installed = true;
  document.addEventListener("error", (e) => {
    const el = e.target;
    if (!el || el.tagName !== "IMG") return;
    const src = el.src || "";
    // Step 1: rewrite legacy hostnames the first time we see a failure on this <img>.
    if (!el.dataset.healed) {
      el.dataset.healed = "1";
      const idx = src.indexOf("/api/uploads/");
      if (idx >= 0) {
        const corrected = `${process.env.REACT_APP_BACKEND_URL}${src.slice(idx)}`;
        if (corrected !== src) {
          el.src = corrected;
          return;
        }
      }
    }
    // Step 2: graceful neutral placeholder.
    if (src !== FALLBACK) el.src = FALLBACK;
  }, true);
}
