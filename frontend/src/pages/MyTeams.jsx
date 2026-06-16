import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";

export default function MyTeams() {
  const { ready, isCompanyAdmin } = useAuth();
  const nav = useNavigate();
  const [teams, setTeams] = useState([]);

  useEffect(() => {
    if (ready && !isCompanyAdmin) { nav("/login"); return; }
    if (ready) api.get("/my/teams").then((r) => setTeams(r.data)).catch(() => {});
  }, [ready, isCompanyAdmin, nav]);

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] tracking-[0.3em] text-[#84CC16] uppercase">/ Roster</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">MY TEAMS</h1>
        <p className="text-neutral-400 mt-3 max-w-2xl">Every team registered under your company across all your events.</p>

        <div data-testid="my-teams-grid" className="mt-10 grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {teams.length === 0 && <div className="col-span-full text-neutral-500 text-center py-12 border border-dashed border-white/10 rounded-sm">No teams yet. Create teams from any event's Teams tab.</div>}
          {teams.map((t) => (
            <Link key={t.id} to={t.event_id ? `/events/${t.event_id}` : "#"} data-testid={`my-team-${t.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-5 hover-lift">
              <div className="flex items-center gap-3">
                <span className="w-2 h-10 rounded-sm" style={{ background: t.color || "#84CC16" }} />
                <div>
                  <div className="font-semibold text-base">{t.name}</div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-widest">
                    {t.department || "team"} · {t.captain || "no captain"}
                  </div>
                </div>
              </div>
              <div className="mt-3 text-[10px] font-mono text-neutral-500">Members: {(t.members || []).length}</div>
            </Link>
          ))}
        </div>
      </div>
      <Footer />
    </div>
  );
}
