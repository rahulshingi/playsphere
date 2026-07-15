/**
 * EventStatusBadge — single-source-of-truth colored pill for event lifecycle
 * states. Mirrors backend `EventStatus` literal + the auto-derived states
 * from `routes/event_lifecycle.py` (upcoming / ongoing / completed / cancelled).
 *
 * Reused wherever the raw `event.status` string appears — one line swap.
 */
const TONE = {
  upcoming:  { fg: "#FACC15", border: "#FACC15/40", bg: "#FACC15/10" },
  ongoing:   { fg: "#84CC16", border: "#84CC16/40", bg: "#84CC16/10" },
  completed: { fg: "#06B6D4", border: "#06B6D4/40", bg: "#06B6D4/10" },
  cancelled: { fg: "#FF3B30", border: "#FF3B30/40", bg: "#FF3B30/10" },
  draft:     { fg: "#a3a3a3", border: "#FFFFFF/10", bg: "#FFFFFF/5" },
};

export function EventStatusBadge({ status, className = "" }) {
  const s = (status || "upcoming").toLowerCase();
  const tone = TONE[s] || TONE.draft;
  return (
    <span
      data-testid={`event-status-${s}`}
      className={`font-mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm border ${className}`}
      style={{ color: tone.fg, borderColor: `${tone.fg}66`, background: `${tone.fg}1a` }}
    >
      {s}
    </span>
  );
}

export default EventStatusBadge;
