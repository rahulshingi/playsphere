import { useEffect, useRef, useState, useCallback } from "react";
import api from "@/lib/api";
import { Bell, BellOff, X, Check } from "lucide-react";

const MAX_ITEMS = 3;
const AUTOHIDE_MS = 30000;
const MUTE_KEY = "kn_arrival_mute";

/**
 * Play a short 2-note chime (A5 → E6) using Web Audio. No asset needed and
 * browsers only require a prior user gesture to allow playback — which is
 * always satisfied on a vendor dashboard (they clicked login / navigated).
 * Kept short (~350ms) and light so it's audible but not annoying.
 */
function playChime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const beep = (freq, startOffset, duration) => {
      const t = ctx.currentTime + startOffset;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.001, t);
      gain.gain.exponentialRampToValueAtTime(0.28, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, t + duration);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + duration + 0.05);
    };
    beep(880, 0, 0.18);   // A5
    beep(1320, 0.13, 0.22); // E6
    setTimeout(() => { try { ctx.close(); } catch { /* noop */ } }, 800);
  } catch { /* audio unavailable — silently no-op */ }
}

/**
 * Live "arrival" banner for the vendor dashboard.
 *
 * Opens a WebSocket to /api/ws (same infra used by the live scoreboard) and
 * listens for `type: "vendor_arrival"` payloads. Filters to messages where
 * `vendor_id` matches the current vendor and shows up to the last 3 arrivals
 * as a stacked banner in the bottom-right corner. Each card auto-dismisses
 * after 30s or when the vendor closes it.
 *
 * Connection uses the same host as `REACT_APP_BACKEND_URL` (converted to
 * ws://wss:// automatically).
 */
export default function VendorArrivalBanner() {
  const [vendorId, setVendorId] = useState("");
  const [items, setItems] = useState([]);
  const [muted, setMuted] = useState(() => {
    try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
  });
  const mutedRef = useRef(muted);
  useEffect(() => { mutedRef.current = muted; }, [muted]);
  const wsRef = useRef(null);

  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      try { localStorage.setItem(MUTE_KEY, next ? "1" : "0"); } catch { /* noop */ }
      return next;
    });
  }, []);

  useEffect(() => {
    api.get("/vendors/me").then((r) => setVendorId(r.data?.id || "")).catch(() => {});
  }, []);

  const push = useCallback((payload) => {
    setItems((prev) => {
      const item = { ...payload, _key: `${payload.booking_id}-${payload.at}` };
      const next = [item, ...prev.filter((x) => x._key !== item._key)].slice(0, MAX_ITEMS);
      return next;
    });
    if (!mutedRef.current) playChime();
    // schedule auto-hide
    setTimeout(() => {
      setItems((prev) => prev.filter((x) => x._key !== `${payload.booking_id}-${payload.at}`));
    }, AUTOHIDE_MS);
  }, []);

  useEffect(() => {
    if (!vendorId) return;
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const wsUrl = base.replace(/^http/, "ws") + "/api/ws";
    let ws;
    let heartbeat;
    let closed = false;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;
      } catch {
        return;
      }
      ws.onopen = () => {
        heartbeat = setInterval(() => {
          try { ws.readyState === 1 && ws.send("ping"); } catch { /* noop */ }
        }, 30000);
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "vendor_arrival" && msg.vendor_id === vendorId) push(msg);
        } catch { /* ignore malformed */ }
      };
      ws.onclose = () => {
        clearInterval(heartbeat);
        if (!closed) setTimeout(connect, 3000); // reconnect
      };
      ws.onerror = () => { try { ws.close(); } catch { /* noop */ } };
    };

    connect();
    return () => {
      closed = true;
      clearInterval(heartbeat);
      try { ws && ws.close(); } catch { /* noop */ }
    };
  }, [vendorId, push]);

  if (items.length === 0) {
    // No arrivals right now — still expose a small mute toggle at bottom-right
    // so the vendor can pre-configure the chime before a busy shift starts.
    return (
      <button
        data-testid="arrival-mute-toggle"
        onClick={toggleMute}
        title={muted ? "Arrival chime muted — tap to unmute" : "Arrival chime on — tap to mute"}
        className="fixed z-[60] bottom-6 right-6 w-9 h-9 rounded-full bg-[#141414]/90 border border-white/10 grid place-items-center text-neutral-400 hover:text-white hover:border-white/30 transition backdrop-blur"
      >
        {muted ? <BellOff className="w-4 h-4" /> : <Bell className="w-4 h-4 text-[#84CC16]" />}
      </button>
    );
  }

  const fmtTime = (iso) => {
    try { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
    catch { return ""; }
  };

  return (
    <div data-testid="vendor-arrival-banner"
         className="fixed z-[60] bottom-6 right-6 flex flex-col gap-2 max-w-xs">
      {/* Header row with mute toggle */}
      <div className="flex justify-end pointer-events-auto">
        <button
          data-testid="arrival-mute-toggle"
          onClick={toggleMute}
          title={muted ? "Arrival chime muted — tap to unmute" : "Arrival chime on — tap to mute"}
          className="w-7 h-7 rounded-sm bg-[#141414]/90 border border-white/10 grid place-items-center text-neutral-400 hover:text-white hover:border-white/30 transition backdrop-blur"
        >
          {muted ? <BellOff className="w-3.5 h-3.5" /> : <Bell className="w-3.5 h-3.5 text-[#84CC16]" />}
        </button>
      </div>
      {items.map((it) => (
        <div key={it._key} data-testid={`arrival-item-${it.booking_id}`}
             className="pointer-events-auto bg-[#141414] border border-[#84CC16]/40 rounded-sm shadow-lg shadow-[#84CC16]/10 p-3 flex items-start gap-3 animate-in slide-in-from-right-6 duration-300">
          <div className="w-8 h-8 rounded-sm bg-[#84CC16]/20 grid place-items-center shrink-0">
            <Bell className="w-4 h-4 text-[#84CC16]" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#84CC16] flex items-center gap-1">
              <Check className="w-3 h-3" /> Arrived
              <span className="text-neutral-500">· {fmtTime(it.at)}</span>
            </div>
            <div className="text-sm font-semibold text-white truncate mt-1">{it.player_name || "Guest"}</div>
            <div className="text-[11px] font-mono text-neutral-400 truncate">
              {it.listing_title || "—"}{it.sport ? ` · ${it.sport}` : ""}
              {it.source === "walkin" && <span className="text-[#FACC15]"> · WALK-IN</span>}
              {it.source === "offline" && <span className="text-[#06B6D4]"> · OFFLINE</span>}
            </div>
          </div>
          <button aria-label="Dismiss" data-testid={`arrival-dismiss-${it.booking_id}`}
                  onClick={() => setItems((prev) => prev.filter((x) => x._key !== it._key))}
                  className="text-neutral-500 hover:text-white transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
