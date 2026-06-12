import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";

export default function Teams() {
  const [teams, setTeams] = useState([]);
  useEffect(() => { api.get("/teams").then((r) => setTeams(r.data)); }, []);

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-24">
        <div className="flex items-end justify-between">
          <div>
            <div className="font-mono text-[10px] tracking-[0.3em] text-[#007AFF] uppercase">/ Roster</div>
            <h1 className="font-display text-6xl tracking-wide mt-3">REGISTERED TEAMS</h1>
            <p className="text-neutral-400 mt-3 max-w-2xl">Every squad on the leaderboard. Click into any team for player profiles and stats.</p>
          </div>
          <Link to="/register-team">
            <Button data-testid="teams-register-btn" className="bg-[#007AFF] hover:bg-[#0066d6] rounded-sm">+ Register team</Button>
          </Link>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-10">
          {teams.map((t) => (
            <Link key={t.id} to={`/teams/${t.id}`} data-testid={`team-card-${t.id}`} className="border border-white/10 rounded-sm p-6 bg-[#141414] hover-lift">
              <div className="flex items-center gap-4">
                <span className="w-2 h-14 rounded-sm" style={{ background: t.color }} />
                <div className="flex-1">
                  <div className="text-xl font-semibold">{t.name}</div>
                  <div className="text-xs font-mono uppercase text-neutral-500 mt-1">{t.department || "Open"}</div>
                </div>
              </div>
              {t.captain && <div className="mt-4 text-sm text-neutral-400">Captain · <span className="text-white">{t.captain}</span></div>}
            </Link>
          ))}
          {!teams.length && <div className="col-span-full text-neutral-500 text-center py-20">No teams yet. Be the first to register.</div>}
        </div>
      </div>
      <Footer />
    </div>
  );
}
