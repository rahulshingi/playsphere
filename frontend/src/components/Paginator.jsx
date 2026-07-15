import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Paginator — universal client-side pagination + sort widget.
 *
 * Two API surfaces:
 *   1. usePagination(items, options)  — hook that returns {view, controls}.
 *      Handles sorting + slicing in-memory. Perfect for list endpoints that
 *      already return the full array (Kreeda Nation's current pattern).
 *   2. <Paginator page total pageSize onPage onPageSize />  — dumb controls
 *      for server-driven pagination (once endpoints support ?page=&size=).
 *
 * Design goals (per user spec):
 *   • Numbered pages (Prev · 1 · 2 · 3 · Next)
 *   • Page-size dropdown (10 / 20 / 50)
 *   • "Latest relevant" on top of page 1 via `sortFn`
 *   • URL query-string sync so refresh / share preserves position
 */

const PAGE_SIZES = [10, 20, 50];

// ─────────────────────────── Hook ───────────────────────────
export function usePagination(items, { defaultPageSize = 20, sortFn = null, storageKey = null } = {}) {
  const params = new URLSearchParams(window.location.search);
  const initialPage = Math.max(1, parseInt(params.get("page") || "1", 10) || 1);
  const initialSize = PAGE_SIZES.includes(parseInt(params.get("size") || "0", 10))
    ? parseInt(params.get("size"), 10) : defaultPageSize;

  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialSize);

  // Persist to URL so refresh keeps position.
  useEffect(() => {
    const url = new URL(window.location.href);
    if (page > 1) url.searchParams.set("page", String(page)); else url.searchParams.delete("page");
    if (pageSize !== defaultPageSize) url.searchParams.set("size", String(pageSize)); else url.searchParams.delete("size");
    // avoid pushing to history — use replaceState so back-button isn't polluted
    window.history.replaceState({}, "", url.toString());
  }, [page, pageSize, defaultPageSize, storageKey]);

  const sorted = useMemo(
    () => (sortFn ? [...(items || [])].sort(sortFn) : (items || [])),
    [items, sortFn],
  );
  const total = sorted.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(page, pages);
  const start = (currentPage - 1) * pageSize;
  const view = sorted.slice(start, start + pageSize);

  // Reset to page 1 whenever the underlying list changes size (e.g. filter applied)
  useEffect(() => {
    if (page > pages) setPage(1);
  }, [pages]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    view,
    controls: {
      page: currentPage,
      pageSize,
      pages,
      total,
      setPage,
      setPageSize: (n) => { setPageSize(n); setPage(1); },
    },
  };
}

// ─────────────────────────── Controls UI ───────────────────────────
export default function Paginator({ page, pages, pageSize, total, setPage, setPageSize, label = "items", showSizePicker = true }) {
  if (total === 0) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);

  return (
    <div data-testid="paginator" className="flex flex-wrap items-center gap-3 pt-4 mt-4 border-t border-white/5">
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">
        {start}–{end} of {total} {label}
      </div>

      <div className="flex-1" />

      {showSizePicker && (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono uppercase text-neutral-500">per page</span>
          <select
            data-testid="paginator-size"
            value={pageSize}
            onChange={(e) => setPageSize(parseInt(e.target.value, 10))}
            className="bg-black/40 border border-white/10 text-white text-xs rounded-sm px-2 py-1 focus:border-[#84CC16] outline-none"
          >
            {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      )}

      {pages > 1 && (
        <div className="flex items-center gap-1">
          <button
            data-testid="paginator-prev"
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="h-7 w-7 grid place-items-center border border-white/10 rounded-sm text-neutral-400 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
          ><ChevronLeft className="w-3.5 h-3.5" /></button>

          {pageWindow(page, pages).map((p, i) =>
            p === "…" ? (
              <span key={`gap-${i}`} className="text-[10px] font-mono text-neutral-500 px-1">…</span>
            ) : (
              <button
                key={p}
                data-testid={`paginator-page-${p}`}
                onClick={() => setPage(p)}
                className={`h-7 min-w-[28px] px-2 text-xs font-mono border rounded-sm ${
                  p === page
                    ? "border-[#84CC16] bg-[#84CC16] text-black"
                    : "border-white/10 text-neutral-300 hover:bg-white/5"
                }`}
              >{p}</button>
            )
          )}

          <button
            data-testid="paginator-next"
            onClick={() => setPage(Math.min(pages, page + 1))}
            disabled={page >= pages}
            className="h-7 w-7 grid place-items-center border border-white/10 rounded-sm text-neutral-400 hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed"
          ><ChevronRight className="w-3.5 h-3.5" /></button>
        </div>
      )}
    </div>
  );
}

// Build a sensible page window with ellipses. Always shows first, last, current ±1.
function pageWindow(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out = [1];
  if (current > 3) out.push("…");
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) out.push(i);
  if (current < total - 2) out.push("…");
  out.push(total);
  return out;
}

// ─────────────────────────── Reusable sort keys ───────────────────────────
// Consistent "latest-relevant on top" comparators used across pages.
export const SORT = {
  // Events — upcoming/ongoing first (soonest start_date), then completed/cancelled by end_date desc.
  eventsByLifecycle: (a, b) => {
    const bucket = (s) => (s === "ongoing" ? 0 : s === "upcoming" ? 1 : s === "completed" ? 2 : 3);
    const bd = bucket(a.status) - bucket(b.status);
    if (bd !== 0) return bd;
    // Within upcoming/ongoing: soonest start first (ascending).
    if (bucket(a.status) < 2) return (a.start_date || "").localeCompare(b.start_date || "");
    // Within completed/cancelled: latest end first (descending).
    return (b.end_date || "").localeCompare(a.end_date || "");
  },
  // Newest created_at first — generic use case for users, vendors, players, organisers, RFQs.
  byCreatedDesc: (a, b) => (b.created_at || "").localeCompare(a.created_at || ""),
  // Bookings — upcoming (by date asc), then past (by date desc).
  bookingsByDate: (a, b) => {
    const today = new Date().toISOString().slice(0, 10);
    const aFut = (a.date || a.start_date || "") >= today;
    const bFut = (b.date || b.start_date || "") >= today;
    if (aFut !== bFut) return aFut ? -1 : 1;
    const cmp = (a.date || a.start_date || "").localeCompare(b.date || b.start_date || "");
    return aFut ? cmp : -cmp;
  },
};
