import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { sportColor } from "@/lib/sports";
import { useAuth } from "@/context/AuthContext";

export default function Events() {
  const { ready, isCompanyAdmin } = useAuth();
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState("all");
  const [mineOnly, setMineOnly] = useState(false);

  useEffect(() => { if (ready) setMineOnly(isCompanyAdmin); }, [ready, isCompanyAdmin]);

  useEffect(() => {
    const url = mineOnly && isCompanyAdmin ? "/events?scope=mine" : "/events";
    api.get(url).then((r) => setEvents(r.data));
  }, [mineOnly, isCompanyAdmin]);

  const filtered = filter === "all" ? events : events.filter((e) => e.status === filter);

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

        <div className="flex gap-2 mt-10 border-b border-white/10 pb-4">
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
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mt-8">
          {filtered.map((e) => (
            <Link
              to={`/events/${e.id}`}
              key={e.id}
              data-testid={`event-card-${e.id}`}
              className="group relative overflow-hidden rounded-sm border border-white/10 bg-[#141414] hover-lift"
            >
              <div className="h-44 relative">
                <img src={e.banner_url || "https://images.pexels.com/photos/1657324/pexels-photo-1657324.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} className="w-full h-full object-cover opacity-70 group-hover:opacity-90" alt="" />
                <div className="absolute top-3 left-3 flex gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm border bg-black/60" style={{ borderColor: sportColor(e.sport), color: sportColor(e.sport) }}>
                    {e.sport}
                  </span>
                  <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded-sm bg-black/60 text-neutral-300">{e.format.replace("_", " ")}</span>
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
              </div>
            </Link>
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full text-center text-neutral-500 py-20">No events to show.</div>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
}
