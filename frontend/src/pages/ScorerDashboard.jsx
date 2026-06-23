import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";
import { Navigate } from "react-router-dom";
import { Trophy, Calendar, MapPin, Pencil } from "lucide-react";

/**
 * Scorer dashboard: lists every event + fixture the current `scorer` user has
 * been assigned to. Clicking through opens the EventDetail page where the
 * existing scoring UI is already gated by the same backend permissions.
 */
export default function ScorerDashboard() {
  const { isScorer, ready } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ready || !isScorer) return;
    api.get("/scorers/me/events").then((r) => {
      setItems(r.data?.events || []);
    }).finally(() => setLoading(false));
  }, [ready, isScorer]);

  if (ready && !isScorer) return <Navigate to="/login" replace />;

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Scorer console</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">YOUR ASSIGNMENTS</h1>
        <p className="text-neutral-400 text-sm mt-2 max-w-2xl">
          You can update live scores for any event and match listed below. Reach out to the event
          organiser to be added to additional matches.
        </p>

        {loading && <div className="text-neutral-500 text-center py-20" data-testid="scorer-loading">Loading…</div>}
        {!loading && items.length === 0 && (
          <div data-testid="scorer-empty" className="text-neutral-500 text-center py-20 border border-dashed border-white/10 rounded-sm mt-10">
            You haven&apos;t been assigned to any matches yet.
          </div>
        )}

        <div className="mt-10 space-y-8">
          {items.map((it) => (
            <div key={it.assignment_id} data-testid={`scorer-event-${it.event.id}`}
              className="border border-white/10 rounded-sm bg-[#141414] p-5">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16]">{it.event.sport}</div>
                  <h2 className="font-display text-3xl tracking-wide mt-1">{it.event.name}</h2>
                  <div className="flex flex-wrap gap-4 mt-2 text-xs font-mono text-neutral-500">
                    {it.event.venue && <span className="flex items-center gap-1.5"><MapPin className="w-3 h-3" /> {it.event.venue}</span>}
                    {it.event.start_date && <span className="flex items-center gap-1.5"><Calendar className="w-3 h-3" /> {it.event.start_date}</span>}
                    <span className="flex items-center gap-1.5"><Trophy className="w-3 h-3" /> {it.scope === "all" ? "All fixtures" : `${it.fixtures.length} specific fixture(s)`}</span>
                  </div>
                </div>
                <Link to={`/events/${it.event.id}`} data-testid={`scorer-open-event-${it.event.id}`}
                  className="text-xs font-mono uppercase tracking-widest px-3 py-2 bg-[#06B6D4] text-black rounded-sm hover:bg-[#0891B2]">
                  Open event →
                </Link>
              </div>

              <div className="mt-5 grid md:grid-cols-2 gap-2">
                {it.fixtures.map((f) => (
                  <Link key={f.id} to={`/events/${it.event.id}`} data-testid={`scorer-fx-${f.id}`}
                    className="border border-white/10 rounded-sm bg-black/30 p-3 hover:border-[#06B6D4] transition-colors flex items-center justify-between">
                    <div>
                      <div className="font-mono text-[10px] text-neutral-500 uppercase tracking-widest">Match #{f.match_number} · R{f.round}</div>
                      <div className="text-sm mt-1">{f.team_a_id ? "" : "TBD"} <StatusPill status={f.status} /></div>
                    </div>
                    <Pencil className="w-4 h-4 text-[#06B6D4]" />
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      <Footer />
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    scheduled: "text-neutral-400 border-white/10",
    live: "text-[#FF3B30] border-[#FF3B30]/40",
    completed: "text-[#84CC16] border-[#84CC16]/40",
  };
  return (
    <span className={`ml-2 text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-sm border ${map[status] || map.scheduled}`}>
      {status}
    </span>
  );
}
