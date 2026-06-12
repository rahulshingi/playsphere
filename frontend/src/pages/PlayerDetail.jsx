import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";

export default function PlayerDetail() {
  const { id } = useParams();
  const [player, setPlayer] = useState(null);
  const [team, setTeam] = useState(null);

  useEffect(() => {
    api.get(`/players/${id}`).then(async (r) => {
      setPlayer(r.data);
      if (r.data.team_id) {
        const t = await api.get(`/teams/${r.data.team_id}`);
        setTeam(t.data);
      }
    });
  }, [id]);

  if (!player) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      <div className="max-w-6xl mx-auto px-6 pt-16 pb-24">
        <Link to={team ? `/teams/${team.id}` : "/teams"} className="text-xs font-mono text-neutral-400 hover:text-white">← Back</Link>
        <div className="mt-8 grid md:grid-cols-2 gap-10">
          <div className="aspect-square border border-white/10 rounded-sm overflow-hidden relative">
            <img src={player.avatar_url || "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} alt="" className="w-full h-full object-cover" />
            {player.jersey_number != null && (
              <span className="absolute top-5 right-5 font-mono text-7xl text-white/90 drop-shadow">#{player.jersey_number}</span>
            )}
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black to-transparent p-6">
              <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-300">{team?.name}</div>
              <div className="font-display text-5xl tracking-wide">{player.name}</div>
            </div>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Player</div>
            <h1 data-testid="player-name" className="font-display text-6xl tracking-wide mt-2">{player.name}</h1>
            <div className="text-xl text-neutral-400 mt-2">{player.role}</div>
            <p className="mt-6 text-neutral-300 leading-relaxed">{player.bio || "A rising star in the PlaySphere arena. Stats unlock once the season starts."}</p>

            <div className="mt-10 grid grid-cols-3 gap-px bg-white/10 border border-white/10 rounded-sm overflow-hidden">
              {[
                { l: "JERSEY", v: player.jersey_number ?? "—" },
                { l: "ROLE", v: player.role || "—" },
                { l: "TEAM", v: team?.name?.split(" ")[0] || "—" },
              ].map((s, i) => (
                <div key={i} className="bg-[#0a0a0a] p-5">
                  <div className="font-mono text-2xl">{s.v}</div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mt-1">{s.l}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
