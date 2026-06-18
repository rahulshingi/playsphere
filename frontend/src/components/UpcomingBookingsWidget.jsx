import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Clock, AlertTriangle, ArrowRight } from "lucide-react";

const ACTIVE_STATUSES = new Set(["pending", "vendor_accepted", "confirmed"]);

/**
 * Sidebar/dashboard widget that surfaces upcoming bookings + cancellation-window countdowns.
 * Reads `/api/vendor-bookings` (already scoped to the caller's company for company_admin),
 * filters out cancelled/completed, sorts by start time ascending.
 */
export default function UpcomingBookingsWidget() {
  const [items, setItems] = useState([]);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let cancelled = false;
    api.get("/vendor-bookings").then((r) => {
      if (!cancelled) setItems(r.data || []);
    }).catch(() => {});
    const t = setInterval(() => setNow(Date.now()), 60000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  const upcoming = useMemo(() => {
    const future = items
      .filter((b) => ACTIVE_STATUSES.has(b.status))
      .map((b) => {
        const slot = new Date(`${b.requested_date}T${b.start_time}:00`);
        return { ...b, _slotMs: slot.getTime() };
      })
      .filter((b) => b._slotMs > now - 60 * 60 * 1000) // include bookings up to 1h in the past
      .sort((a, b) => a._slotMs - b._slotMs)
      .slice(0, 5);
    return future;
  }, [items, now]);

  if (upcoming.length === 0) return null;

  return (
    <section data-testid="upcoming-bookings-widget" className="border border-[#06B6D4]/30 bg-[#06B6D4]/5 rounded-sm p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4]">/ Upcoming bookings</div>
          <h3 className="font-display text-xl mt-1">Next on the calendar</h3>
        </div>
        <Link to="/bookings" className="text-[10px] font-mono uppercase text-neutral-400 hover:text-white flex items-center gap-1">
          All bookings <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
      <div className="mt-4 space-y-2">
        {upcoming.map((b) => (
          <Row key={b.id} booking={b} now={now} />
        ))}
      </div>
    </section>
  );
}

function Row({ booking, now }) {
  const slotMs = new Date(`${booking.requested_date}T${booking.start_time}:00`).getTime();
  const hrsLeft = Math.max(0, (slotMs - now) / 3600000);

  // Compute the policy banner using the booking's currency
  const banner = useMemo(() => deriveCancellationBanner(booking, hrsLeft), [booking, hrsLeft]);

  return (
    <div data-testid={`upcoming-${booking.id}`} className="border border-white/10 rounded-sm bg-black/30 p-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="text-sm font-semibold truncate">{booking.listing_title}</div>
          <div className="text-[10px] font-mono uppercase text-neutral-500 mt-0.5">
            {booking.requested_date} · {booking.start_time}–{booking.end_time} · {booking.hours}h
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-sm text-[#84CC16]">{booking.status?.replace("vendor_", "").toUpperCase()}</div>
          <div className="font-mono text-[10px] text-neutral-500 mt-0.5">
            <Clock className="w-3 h-3 inline-block mr-1" />{formatCountdown(hrsLeft)}
          </div>
        </div>
      </div>
      {banner && (
        <div className="mt-2 text-[11px] flex items-center gap-1 font-mono" style={{ color: banner.color }}>
          <AlertTriangle className="w-3 h-3" />
          {banner.text}
        </div>
      )}
    </div>
  );
}

function formatCountdown(hours) {
  if (hours <= 0) return "starts now";
  if (hours < 1) return `in ${Math.round(hours * 60)}m`;
  if (hours < 24) return `in ${hours.toFixed(1)}h`;
  return `in ${Math.floor(hours / 24)}d`;
}

function deriveCancellationBanner(booking, hrsLeft) {
  // We don't have the listing's policy on the booking — surface a generic countdown for now
  // and call out the no-refund window if the slot is < 24h away.
  if (hrsLeft <= 0) return null;
  if (hrsLeft <= 2) {
    return { color: "#FF3B30", text: `Cancellation window closed — no refund available` };
  }
  if (hrsLeft <= 6) {
    return { color: "#F59E0B", text: `Cancel before slot to get partial refund` };
  }
  if (hrsLeft <= 24) {
    return { color: "#06B6D4", text: `Full-refund window closing soon — cancel ${(24 - hrsLeft).toFixed(0)}h to lose 100%` };
  }
  return null;
}
