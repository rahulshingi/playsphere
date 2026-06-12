import { useEffect, useState } from "react";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";

export default function Standings() {
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.get("/events").then((r) => {
      setEvents(r.data);
      if (r.data.length) setSelected(r.data[0].id);
    });
  }, []);

  useEffect(() => {
    if (selected) api.get(`/events/${selected}/standings`).then((r) => setRows(r.data));
  }, [selected]);

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      <div className="max-w-6xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] tracking-[0.3em] text-[#007AFF] uppercase">/ Leaderboard</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">STANDINGS</h1>
        <p className="text-neutral-400 mt-3 max-w-xl">Every point counts. Filter by event to see who's hunting the trophy.</p>

        <div className="mt-10 flex gap-2 overflow-x-auto scrollbar-thin pb-2">
          {events.map((e) => (
            <button
              key={e.id}
              data-testid={`standings-event-${e.id}`}
              onClick={() => setSelected(e.id)}
              className={`px-4 py-2 text-sm rounded-sm border shrink-0 transition ${selected === e.id ? "bg-[#007AFF] border-[#007AFF] text-white" : "border-white/10 text-neutral-400 hover:text-white"}`}
            >
              {e.name}
            </button>
          ))}
        </div>

        <div className="mt-6 border border-white/10 rounded-sm overflow-hidden">
          <table data-testid="standings-table-global" className="w-full text-sm">
            <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
              <tr>
                <th className="text-left px-5 py-3">Rank</th>
                <th className="text-left px-5 py-3">Team</th>
                <th className="text-right px-3 py-3">P</th>
                <th className="text-right px-3 py-3">W</th>
                <th className="text-right px-3 py-3">D</th>
                <th className="text-right px-3 py-3">L</th>
                <th className="text-right px-5 py-3">PTS</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s, i) => (
                <tr key={s.team_id} className="border-t border-white/5 hover:bg-white/[0.02]">
                  <td className="px-5 py-4 font-mono text-neutral-500">{String(i + 1).padStart(2, "0")}</td>
                  <td className="px-5 py-4 flex items-center gap-3">
                    <span className="w-1.5 h-6 rounded-sm" style={{ background: s.color }} />
                    <span className="font-medium">{s.team_name}</span>
                  </td>
                  <td className="text-right px-3 font-mono">{s.played}</td>
                  <td className="text-right px-3 font-mono text-emerald-400">{s.won}</td>
                  <td className="text-right px-3 font-mono">{s.drawn}</td>
                  <td className="text-right px-3 font-mono text-[#FF3B30]">{s.lost}</td>
                  <td className="text-right px-5 font-mono text-[#007AFF] text-lg font-bold">{s.points}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={7} className="text-center py-16 text-neutral-500">No data available yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <Footer />
    </div>
  );
}
