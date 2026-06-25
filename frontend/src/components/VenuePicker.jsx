import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { fmtPrice } from "@/lib/currency";
import { X, MapPin, Search } from "lucide-react";

/**
 * Modal picker for selecting a verified venue when creating an event.
 *
 * Props:
 *   open, onClose, onPick(listing)
 *   sport (optional): only show venues that support this sport. Without it the picker
 *                     shows every approved ground/court — useful for "other" events.
 *
 * UX details:
 *  - Single search input — works for either venue name OR location keyword (city / area).
 *    Backend matches against both `title` and `city` substrings, so a user in Pune can
 *    type "kharadi" / "balewadi" and find venues even though they typed an area, not the
 *    full city.
 *  - Venues in the signed-in user's stored company city are surfaced first by the server.
 *  - Free-text venue name remains the fallback in the parent input outside this picker.
 */
export default function VenuePicker({ open, onClose, onPick, sport }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (sport) params.set("sport", sport);
      setLoading(true);
      api.get(`/venues/suggest?${params.toString()}`)
        .then((r) => setResults(r.data || []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 250); // small debounce so we don't hammer the API on every keystroke
    return () => clearTimeout(t);
  }, [q, sport, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6" onClick={onClose}>
      <div data-testid="venue-picker"
        className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-2xl my-10 text-white"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h3 className="font-display text-2xl tracking-wider">
            PICK A VERIFIED {sport ? sport.toUpperCase() : ""} VENUE
          </h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <Input
              data-testid="vp-query"
              placeholder={`Search by venue name or location (e.g. ${sport ? `${sport} grounds, ` : ""}"kharadi", "Pune")…`}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="pl-9 bg-black/40 border-white/10 text-white"
              autoFocus
            />
          </div>
          {sport && (
            <p className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">
              / Showing only approved <span className="text-[#84CC16]">{sport}</span> venues
            </p>
          )}
          <div className="space-y-2 max-h-[440px] overflow-auto">
            {loading && <div className="text-center text-neutral-500 py-8 text-sm">Searching…</div>}
            {!loading && results.length === 0 && (
              <div data-testid="vp-empty" className="text-center text-neutral-500 py-8 text-sm">
                No verified {sport || ""} venues match.<br />
                <span className="text-[10px] font-mono uppercase">Type the location, try a different keyword, or use the free-text venue field outside this picker.</span>
              </div>
            )}
            {results.map((v) => (
              <button key={v.id} data-testid={`vp-result-${v.id}`}
                onClick={() => { onPick(v); onClose(); }}
                className="w-full text-left border border-white/10 rounded-sm bg-[#141414] hover:bg-black/40 p-3 flex items-center justify-between">
                <div>
                  <div className="font-semibold">{v.title}</div>
                  <div className="text-[11px] font-mono text-neutral-500 flex items-center gap-1.5">
                    <MapPin className="w-3 h-3" />{v.city}
                    {(v.sports || []).length > 0 && (
                      <>
                        <span className="text-neutral-700">·</span>
                        {(v.sports || []).slice(0, 3).join(" · ")}
                      </>
                    )}
                  </div>
                </div>
                <div className="font-mono text-[#84CC16] text-sm">{fmtPrice(v.price, v.currency)}/hr</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
