import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";

export default function TeamDetail() {
  const { id } = useParams();
  const [team, setTeam] = useState(null);
  const [players, setPlayers] = useState([]);

  useEffect(() => {
    api.get(`/teams/${id}`).then((r) => setTeam(r.data));
    api.get(`/players?team_id=${id}`).then((r) => setPlayers(r.data));
  }, [id]);

  if (!team) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-24">
        <Link to="/teams" className="text-xs font-mono text-neutral-400 hover:text-white">← All teams</Link>
        <div className="mt-6 flex items-center gap-6">
          <span className="w-3 h-24 rounded-sm" style={{ background: team.color }} />
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Team</div>
            <h1 data-testid="team-name" className="font-display text-6xl tracking-wide">{team.name}</h1>
            <div className="text-sm text-neutral-400 mt-1">{team.department} {team.captain ? `· Captain ${team.captain}` : ""}</div>
          </div>
        </div>

        <div className="mt-12">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Roster</div>
          <h2 className="font-display text-3xl tracking-wider mt-2 mb-6">PLAYERS</h2>
          {players.length === 0 ? (
            <div className="text-neutral-500 text-center py-12 border border-dashed border-white/10 rounded-sm">No players added yet.</div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {players.map((p) => (
                <Link to={`/team-players/${p.id}`} key={p.id} data-testid={`player-card-${p.id}`} className="border border-white/10 rounded-sm bg-[#141414] overflow-hidden hover-lift">
                  <div className="aspect-[4/3] relative">
                    <img src={p.avatar_url || "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} alt="" className="w-full h-full object-cover opacity-80" />
                    <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-transparent" />
                    {p.jersey_number != null && (
                      <span className="absolute top-3 right-3 font-mono text-3xl text-white/90">#{p.jersey_number}</span>
                    )}
                  </div>
                  <div className="p-4">
                    <div className="text-lg font-semibold">{p.name}</div>
                    <div className="text-xs font-mono text-neutral-500 uppercase mt-1">{p.role}</div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
}
