import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Megaphone, MapPin, IndianRupee, Users } from "lucide-react";
import { SPORTS } from "@/lib/sports";

const EVENT_TYPES = ["", "single_company", "inter_company", "playsphere_organized"];
const PRICE_BUCKETS = [
  { v: "__any__", label: "Any budget" },
  { v: "10000", label: "≤ ₹10,000" },
  { v: "50000", label: "≤ ₹50,000" },
  { v: "100000", label: "≤ ₹1,00,000" },
  { v: "500000", label: "≤ ₹5,00,000" },
];

export default function SponsorshipMarketplace() {
  const { ready, canSponsor } = useAuth();
  const [events, setEvents] = useState([]);
  const [filters, setFilters] = useState({ sport: "", location: "", event_type: "", price_max: "", min_reach: "" });
  const [busy, setBusy] = useState(false);

  const load = () => {
    setBusy(true);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    const qs = params.toString();
    api.get(qs ? `/sponsorships/marketplace?${qs}` : "/sponsorships/marketplace")
      .then((r) => setEvents(r.data))
      .finally(() => setBusy(false));
  };

  useEffect(() => { if (ready) load(); }, [ready]);

  const update = (patch) => setFilters({ ...filters, ...patch });

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FACC15] flex items-center gap-2">
          <Megaphone className="w-3 h-3" /> Sponsorship Marketplace
        </div>
        <h1 className="font-display text-5xl tracking-wide mt-2">BROWSE EVENTS</h1>
        <p className="text-neutral-400 text-sm mt-2 max-w-2xl">
          Live tournaments looking for sponsors. Filter by audience, budget &amp; brand fit — click into any
          event to see opportunities and express interest in one click.
        </p>

        {!canSponsor && (
          <div className="mt-6 border border-amber-500/40 bg-amber-500/10 rounded-sm p-4 text-sm">
            You can browse here without an account.{" "}
            <Link to="/sponsor/signup" className="text-[#FACC15] underline">Sign up as a sponsor</Link>{" "}
            or{" "}
            <Link to="/login" className="text-[#FACC15] underline">sign in</Link>{" "}
            to express interest in any opportunity.
          </div>
        )}

        {/* Filters */}
        <form onSubmit={(e) => { e.preventDefault(); load(); }} className="mt-8 border border-white/10 rounded-sm bg-[#141414] p-4">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-2">
            <Select value={filters.sport || "__any__"} onValueChange={(v) => update({ sport: v === "__any__" ? "" : v })}>
              <SelectTrigger data-testid="mkt-sport" className="bg-black/40 border-white/10 text-white text-sm"><SelectValue placeholder="Sport" /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                <SelectItem value="__any__">Any sport</SelectItem>
                {SPORTS.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Input data-testid="mkt-location" placeholder="Location (Bangalore…)" value={filters.location} onChange={(e) => update({ location: e.target.value })}
              className="bg-black/40 border-white/10 text-white text-sm" />
            <Select value={filters.event_type || "__any__"} onValueChange={(v) => update({ event_type: v === "__any__" ? "" : v })}>
              <SelectTrigger data-testid="mkt-event-type" className="bg-black/40 border-white/10 text-white text-sm"><SelectValue placeholder="Event type" /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                <SelectItem value="__any__">Any event type</SelectItem>
                {EVENT_TYPES.filter(Boolean).map((t) => <SelectItem key={t} value={t}>{t.replace(/_/g, " ")}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={filters.price_max || "__any__"} onValueChange={(v) => update({ price_max: v === "__any__" ? "" : v })}>
              <SelectTrigger data-testid="mkt-price" className="bg-black/40 border-white/10 text-white text-sm"><SelectValue placeholder="Budget" /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {PRICE_BUCKETS.map((b) => <SelectItem key={b.v} value={b.v}>{b.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Input data-testid="mkt-min-reach" type="number" placeholder="Min reach" value={filters.min_reach} onChange={(e) => update({ min_reach: e.target.value })}
              className="bg-black/40 border-white/10 text-white text-sm" />
            <Button data-testid="mkt-search" type="submit" disabled={busy} className="bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm">
              {busy ? "Searching…" : "Search"}
            </Button>
          </div>
        </form>

        <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mt-4">
          / {events.length} event{events.length === 1 ? "" : "s"} accepting sponsors
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
          {events.map((e) => <MarketCard key={e.id} ev={e} />)}
          {events.length === 0 && (
            <div className="col-span-full text-center text-neutral-500 py-20">No events match your filters.</div>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
}

function MarketCard({ ev }) {
  const reqs = ev.sponsorship_requirements || {};
  return (
    <Link to={`/events/${ev.id}`} data-testid={`mkt-card-${ev.id}`}
      className="border border-white/10 rounded-sm bg-[#141414] overflow-hidden hover-lift block">
      <div className="h-32 relative">
        <img src={ev.banner_url || "https://images.pexels.com/photos/1657324/pexels-photo-1657324.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} className="w-full h-full object-cover opacity-70" alt="" />
        <span className="absolute top-2 left-2 font-mono text-[10px] uppercase px-2 py-0.5 rounded-sm bg-[#FACC15] text-black flex items-center gap-1">
          <Megaphone className="w-2.5 h-2.5" /> Sponsorship-ready
        </span>
      </div>
      <div className="p-4 space-y-2">
        <div className="font-semibold">{ev.name}</div>
        <div className="text-xs font-mono text-neutral-500 uppercase">{ev.sport} · {(ev.event_type || "").replace(/_/g, " ")}</div>
        <div className="text-xs text-neutral-400 grid grid-cols-2 gap-1">
          <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {reqs.venue_location || ev.venue || "—"}</span>
          <span className="flex items-center gap-1"><Users className="w-3 h-3" /> {reqs.expected_participants ? `${reqs.expected_participants} players` : "—"}</span>
        </div>
        {reqs.expected_reach && (
          <div className="text-[10px] font-mono uppercase text-neutral-500">
            reach {Number(reqs.expected_reach).toLocaleString()} · livestream {Number(reqs.livestream_views || 0).toLocaleString()}
          </div>
        )}
        <div className="border-t border-white/10 pt-2 flex items-center justify-between">
          <span className="text-[11px] font-mono text-[#FACC15]">{ev.available_slots} open / {(ev.opportunities || []).length} opp{(ev.opportunities || []).length === 1 ? "" : "s"}</span>
          {ev.min_price > 0 && (
            <span className="text-xs font-display flex items-center gap-0.5"><IndianRupee className="w-3 h-3" />from {ev.min_price.toLocaleString()}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
