import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { sportColor } from "@/lib/sports";
import { useAuth } from "@/context/AuthContext";
import { Megaphone } from "lucide-react";

export default function Events() {
  const { ready, isCompanyAdmin, canSponsor } = useAuth();
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState("all");
  const [mineOnly, setMineOnly] = useState(false);
  const [sponsorshipOnly, setSponsorshipOnly] = useState(false);

  useEffect(() => { if (ready) setMineOnly(isCompanyAdmin); }, [ready, isCompanyAdmin]);

  useEffect(() => {
    const url = mineOnly && isCompanyAdmin ? "/events?scope=mine" : "/events";
    api.get(url).then((r) => setEvents(r.data));
  }, [mineOnly, isCompanyAdmin]);

  const filtered = useMemo(() => {
    let xs = filter === "all" ? events : events.filter((e) => e.status === filter);
    if (sponsorshipOnly) xs = xs.filter((e) => e.accept_sponsorships);
    return xs;
  }, [events, filter, sponsorshipOnly]);

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] tracking-[0.3em] text-[#84CC16] uppercase">/ Tournaments</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">{mineOnly && isCompanyAdmin ? "MY EVENTS" : "ALL EVENTS"}</h1>
        <p className="text-neutral-400 mt-3 max-w-2xl">Multi-sport, multi-format, multi-team — every season's lineup at a glance.</p>
        {isCompanyAdmin && (
          <div className="mt-6 flex gap-2">
            <button data-testid="events-scope-mine" onClick={() => setMineOnly(true)} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-widest rounded-sm border ${mineOnly ? "bg-[#84CC16] text-black border-[#84CC16]" : "text-neutral-400 border-white/10"}`}>My events</button>
            <button data-testid="events-scope-all" onClick={() => setMineOnly(false)} className={`px-3 py-1.5 text-xs font-mono uppercase tracking-widest rounded-sm border ${!mineOnly ? "bg-[#84CC16] text-black border-[#84CC16]" : "text-neutral-400 border-white/10"}`}>All events</button>
          </div>
        )}

        <div className="flex gap-2 mt-10 border-b border-white/10 pb-4 flex-wrap">
          {["all", "upcoming", "ongoing", "completed"].map((s) => (
            <button
              key={s}
              data-testid={`events-filter-${s}`}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 text-xs font-mono uppercase tracking-widest rounded-sm transition ${
                filter === s ? "bg-[#84CC16] text-black" : "text-neutral-400 hover:text-white"
              }`}
            >
              {s}
            </button>
          ))}
          <button
            data-testid="events-filter-sponsorship"
            onClick={() => setSponsorshipOnly((v) => !v)}
            title={canSponsor ? "Show only events accepting sponsors" : "Events accepting sponsors"}
            className={`ml-auto px-3 py-1.5 text-xs font-mono uppercase tracking-widest rounded-sm border flex items-center gap-1.5 transition ${
              sponsorshipOnly ? "bg-[#FACC15] text-black border-transparent" : "text-[#FACC15] border-[#FACC15]/40 hover:bg-[#FACC15]/10"
            }`}
          >
            <Megaphone className="w-3 h-3" /> Accepting sponsors
          </button>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mt-8">
          {filtered.map((e) => {
            const oppCount = (e.sponsorship_opportunities || []).length;
            const minPrice = oppCount > 0 ? Math.min(...e.sponsorship_opportunities.map((o) => o.price || 0).filter((p) => p > 0)) : 0;
            return (
              <Link
                to={`/events/${e.id}`}
                key={e.id}
                data-testid={`event-card-${e.id}`}
                className="group relative overflow-hidden rounded-sm border border-white/10 bg-[#141414] hover-lift"
              >
                <div className="h-44 relative">
                  <img src={e.banner_url || "https://images.pexels.com/photos/1657324/pexels-photo-1657324.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} className="w-full h-full object-cover opacity-70 group-hover:opacity-90" alt="" />
                  <div className="absolute top-3 left-3 flex gap-2 flex-wrap">
                    <span className="font-mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm border bg-black/60" style={{ borderColor: sportColor(e.sport), color: sportColor(e.sport) }}>
                      {e.sport}
                    </span>
                    <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded-sm bg-black/60 text-neutral-300">{e.format.replace("_", " ")}</span>
                    {e.accept_sponsorships && (
                      <span data-testid={`event-sponsorship-badge-${e.id}`} className="font-mono text-[10px] uppercase px-2 py-0.5 rounded-sm bg-[#FACC15] text-black flex items-center gap-1">
                        <Megaphone className="w-2.5 h-2.5" /> Sponsorship-ready
                      </span>
                    )}
                  </div>
                  {e.status === "ongoing" && (
                    <span className="absolute top-3 right-3 flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-[#FF3B30] text-white text-[10px] font-mono">
                      <span className="w-1.5 h-1.5 rounded-full bg-white live-pulse" /> LIVE
                    </span>
                  )}
                </div>
                <div className="p-5">
                  <h3 className="text-xl font-semibold group-hover:text-[#84CC16]">{e.name}</h3>
                  <p className="text-sm text-neutral-400 mt-2 line-clamp-2">{e.description}</p>
                  <div className="flex items-center justify-between mt-4 text-xs font-mono text-neutral-500 uppercase">
                    <span>{e.venue || "TBD"}</span>
                    <span>{e.status}</span>
                  </div>
                  {e.accept_sponsorships && oppCount > 0 && (
                    <div className="mt-3 pt-3 border-t border-white/10 text-[11px] font-mono text-[#FACC15] flex items-center justify-between">
                      <span>{oppCount} sponsorship{oppCount === 1 ? "" : "s"}</span>
                      {minPrice > 0 && <span>from ₹{minPrice.toLocaleString()}</span>}
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
          {filtered.length === 0 && (
            <div className="col-span-full text-center text-neutral-500 py-20">No events to show.</div>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
}
