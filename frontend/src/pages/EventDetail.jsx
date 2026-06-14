import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { renderScore, sportColor } from "@/lib/sports";
import { useAuth } from "@/context/AuthContext";
import { Trophy, MapPin, Calendar, Wifi } from "lucide-react";
import LiveScorer from "@/components/LiveScorer";
import useFixtureSocket from "@/lib/useFixtureSocket";

export default function EventDetail() {
  const { id } = useParams();
  const { isAdmin } = useAuth();
  const [event, setEvent] = useState(null);
  const [teams, setTeams] = useState([]);
  const [fixtures, setFixtures] = useState([]);
  const [standings, setStandings] = useState([]);
  const [sponsors, setSponsors] = useState([]);
  const [scoringFixture, setScoringFixture] = useState(null);

  const loadAll = async () => {
    const [e, t, f, s] = await Promise.all([
      api.get(`/events/${id}`),
      api.get(`/teams?event_id=${id}`),
      api.get(`/events/${id}/fixtures`),
      api.get(`/events/${id}/standings`),
    ]);
    setEvent(e.data);
    setTeams(t.data);
    setFixtures(f.data);
    setStandings(s.data);
  };

  useEffect(() => { loadAll(); }, [id]);

  // Real-time updates: merge incoming fixture changes; refresh standings on completion.
  useFixtureSocket((payload) => {
    if (!payload || payload.event_id !== id) return;
    setFixtures((prev) => prev.map((f) => (f.id === payload.fixture.id ? payload.fixture : f)));
    if (payload.fixture.status === "completed") {
      api.get(`/events/${id}/standings`).then((r) => setStandings(r.data));
    }
  });

  const teamMap = useMemo(() => Object.fromEntries(teams.map((t) => [t.id, t])), [teams]);

  const generate = async () => {
    await api.post(`/events/${id}/generate-fixtures`);
    await loadAll();
  };

  if (!event) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      {/* HERO */}
      <section className="relative">
        <div className="absolute inset-0 h-72">
          <img src={event.banner_url} className="w-full h-full object-cover opacity-40" alt="" />
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#0a0a0a]/60 to-[#0a0a0a]" />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 pt-16 pb-10">
          <Link to="/events" className="text-xs font-mono text-neutral-400 hover:text-white">← All events</Link>
          <div className="flex items-center gap-2 mt-4">
            <span className="font-mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm border" style={{ borderColor: sportColor(event.sport), color: sportColor(event.sport) }}>{event.sport}</span>
            <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded-sm bg-white/5 text-neutral-300">{event.format.replace("_", " ")}</span>
            <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded-sm bg-white/5 text-neutral-300">{event.status}</span>
          </div>
          <h1 data-testid="event-title" className="font-display text-6xl tracking-wide mt-4">{event.name}</h1>
          <p className="text-neutral-400 mt-3 max-w-2xl">{event.description}</p>
          <div className="flex flex-wrap gap-4 mt-4 text-xs font-mono text-neutral-500">
            {event.venue && <span className="flex items-center gap-1.5"><MapPin className="w-3 h-3" /> {event.venue}</span>}
            {event.start_date && <span className="flex items-center gap-1.5"><Calendar className="w-3 h-3" /> {event.start_date}</span>}
            <span>{teams.length} teams · {fixtures.length} matches</span>
            <span data-testid="live-stream-indicator" className="flex items-center gap-1.5 text-[#84CC16]">
              <Wifi className="w-3 h-3" /> LIVE STREAM ON
            </span>
          </div>
          {isAdmin && (
            <div className="mt-6 flex gap-2">
              <Button data-testid="generate-fixtures-btn" onClick={generate} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
                Generate fixtures
              </Button>
            </div>
          )}
        </div>
      </section>

      <div className="max-w-7xl mx-auto px-6 pb-24">
        <Tabs defaultValue="fixtures">
          <TabsList data-testid="event-tabs" className="bg-[#141414] border border-white/10 rounded-sm">
            <TabsTrigger value="fixtures" data-testid="tab-fixtures" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Fixtures</TabsTrigger>
            <TabsTrigger value="standings" data-testid="tab-standings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Standings</TabsTrigger>
            <TabsTrigger value="teams" data-testid="tab-teams" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Teams</TabsTrigger>
            {event.format === "knockout" && <TabsTrigger value="bracket" data-testid="tab-bracket" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Bracket</TabsTrigger>}
            <TabsTrigger value="sponsors" data-testid="tab-sponsors" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Sponsors ({sponsors.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="fixtures" className="mt-6">
            <FixturesList fixtures={fixtures} event={event} teamMap={teamMap} isAdmin={isAdmin} onScore={(f) => setScoringFixture(f)} />
          </TabsContent>
          <TabsContent value="standings" className="mt-6">
            <StandingsTable standings={standings} />
          </TabsContent>
          <TabsContent value="teams" className="mt-6">
            <TeamsGrid teams={teams} />
          </TabsContent>
          {event.format === "knockout" && (
            <TabsContent value="bracket" className="mt-6">
              <Bracket fixtures={fixtures} teamMap={teamMap} event={event} />
            </TabsContent>
          )}
          <TabsContent value="sponsors" className="mt-6">
            <EventSponsors eventId={event.id} sponsors={sponsors} isAdmin={isAdmin} reload={loadAll} />
          </TabsContent>
        </Tabs>
      </div>

      {scoringFixture && (
        <LiveScorer
          fixture={scoringFixture}
          event={event}
          teamMap={teamMap}
          onClose={() => setScoringFixture(null)}
          onSaved={loadAll}
        />
      )}

      <Footer />
    </div>
  );
}

function FixturesList({ fixtures, event, teamMap, isAdmin, onScore }) {
  const grouped = fixtures.reduce((acc, f) => {
    (acc[f.round] = acc[f.round] || []).push(f);
    return acc;
  }, {});
  if (!fixtures.length) return <div className="text-neutral-500 text-center py-20">No fixtures yet. {isAdmin && "Generate them from above."}</div>;
  return (
    <div className="space-y-8">
      {Object.entries(grouped).map(([rnd, list]) => (
        <div key={rnd}>
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Round {rnd}</div>
          <div className="grid md:grid-cols-2 gap-3">
            {list.map((f) => (
              <FixtureCard key={f.id} fixture={f} event={event} teamMap={teamMap} isAdmin={isAdmin} onScore={onScore} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function FixtureCard({ fixture, event, teamMap, isAdmin, onScore }) {
  const a = teamMap[fixture.team_a_id];
  const b = teamMap[fixture.team_b_id];
  const isLive = fixture.status === "live";
  return (
    <div data-testid={`fixture-card-${fixture.id}`} className={`rounded-sm border bg-[#141414] p-5 hover-lift ${isLive ? "border-[#FF3B30]/50" : "border-white/10"}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-[10px] text-neutral-500 uppercase tracking-widest">Match #{fixture.match_number}</span>
        <StatusPill status={fixture.status} />
      </div>
      <TeamRow team={a} score={renderScore(event.sport, fixture.score?.team_a)} winner={fixture.winner_id === a?.id} />
      <div className="text-[10px] font-mono text-neutral-600 my-1.5 text-center">VS</div>
      <TeamRow team={b} score={renderScore(event.sport, fixture.score?.team_b)} winner={fixture.winner_id === b?.id} />
      {isAdmin && a && b && (
        <Button data-testid={`score-fixture-${fixture.id}`} size="sm" onClick={() => onScore(fixture)} className="mt-3 w-full bg-white/5 hover:bg-[#84CC16] text-white rounded-sm border border-white/10">
          Update score
        </Button>
      )}
    </div>
  );
}

function TeamRow({ team, score, winner }) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-3">
        <span className="w-2 h-6 rounded-sm" style={{ background: team?.color || "#333" }} />
        <span className={`text-sm ${winner ? "text-white font-semibold" : "text-neutral-300"}`}>{team?.name || "TBD"}</span>
        {winner && <Trophy className="w-3.5 h-3.5 text-[#F59E0B]" />}
      </div>
      <span className="font-mono text-lg">{score}</span>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    scheduled: { label: "SCHEDULED", color: "text-neutral-500 border-white/10" },
    live: { label: "● LIVE", color: "text-[#FF3B30] border-[#FF3B30]/40" },
    completed: { label: "FINAL", color: "text-emerald-400 border-emerald-500/40" },
  };
  const m = map[status] || map.scheduled;
  return <span className={`text-[10px] font-mono px-2 py-0.5 rounded-sm border ${m.color}`}>{m.label}</span>;
}

function StandingsTable({ standings }) {
  if (!standings.length) return <div className="text-neutral-500 text-center py-20">No standings yet.</div>;
  return (
    <div className="border border-white/10 rounded-sm overflow-hidden">
      <table data-testid="standings-table" className="w-full text-sm">
        <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
          <tr>
            <th className="text-left px-5 py-3">#</th>
            <th className="text-left px-5 py-3">Team</th>
            <th className="text-right px-3 py-3">P</th>
            <th className="text-right px-3 py-3">W</th>
            <th className="text-right px-3 py-3">D</th>
            <th className="text-right px-3 py-3">L</th>
            <th className="text-right px-5 py-3">PTS</th>
          </tr>
        </thead>
        <tbody>
          {standings.map((s, i) => (
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
              <td className="text-right px-5 font-mono text-[#84CC16] text-lg font-bold">{s.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TeamsGrid({ teams }) {
  if (!teams.length) return <div className="text-neutral-500 text-center py-20">No teams registered yet.</div>;
  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      {teams.map((t) => (
        <Link to={`/teams/${t.id}`} key={t.id} data-testid={`event-team-card-${t.id}`} className="border border-white/10 rounded-sm p-5 bg-[#141414] hover-lift">
          <div className="flex items-center gap-3">
            <span className="w-2 h-10 rounded-sm" style={{ background: t.color }} />
            <div>
              <div className="font-semibold">{t.name}</div>
              <div className="text-xs font-mono text-neutral-500 uppercase">{t.department}</div>
            </div>
          </div>
          {t.captain && <div className="mt-3 text-xs text-neutral-500">Captain · {t.captain}</div>}
        </Link>
      ))}
    </div>
  );
}

function Bracket({ fixtures, teamMap, event }) {
  const grouped = fixtures.reduce((acc, f) => { (acc[f.round] = acc[f.round] || []).push(f); return acc; }, {});
  const rounds = Object.keys(grouped).sort((a, b) => a - b);
  if (!rounds.length) return <div className="text-neutral-500 text-center py-20">Generate fixtures to view the bracket.</div>;
  return (
    <div className="overflow-x-auto scrollbar-thin">
      <div className="flex gap-10 min-w-max py-6">
        {rounds.map((r) => (
          <div key={r} className="flex flex-col justify-around gap-6 min-w-[240px]">
            <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Round {r}</div>
            {grouped[r].map((f) => (
              <div key={f.id} className="bracket-line border border-white/10 rounded-sm bg-[#141414] p-3">
                <BracketRow team={teamMap[f.team_a_id]} score={renderScore(event.sport, f.score?.team_a)} winner={f.winner_id === f.team_a_id} />
                <div className="h-px bg-white/10 my-1" />
                <BracketRow team={teamMap[f.team_b_id]} score={renderScore(event.sport, f.score?.team_b)} winner={f.winner_id === f.team_b_id} />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function BracketRow({ team, score, winner }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <div className="flex items-center gap-2">
        <span className="w-1.5 h-5 rounded-sm" style={{ background: team?.color || "#333" }} />
        <span className={`text-sm ${winner ? "text-white font-semibold" : "text-neutral-400"}`}>{team?.name || "TBD"}</span>
      </div>
      <span className="font-mono text-sm">{score}</span>
    </div>
  );
}

function EventSponsors({ eventId, sponsors, isAdmin, reload }) {
  const [form, setForm] = useState({ name: "", tier: "bronze", logo_url: "", website: "", description: "" });
  const tiers = ["title", "gold", "silver", "bronze"];
  const tierColor = { title: "#84CC16", gold: "#F59E0B", silver: "#A3A3A3", bronze: "#A16207" };

  const add = async (e) => {
    e.preventDefault();
    if (!form.name || !form.logo_url) return;
    await api.post("/sponsors", { ...form, event_id: eventId });
    setForm({ name: "", tier: "bronze", logo_url: "", website: "", description: "" });
    reload();
  };

  const remove = async (id) => {
    if (!window.confirm("Remove sponsor?")) return;
    await api.delete(`/sponsors/${id}`); reload();
  };

  return (
    <div className="space-y-6">
      {tiers.map((t) => {
        const list = sponsors.filter((s) => s.tier === t);
        if (list.length === 0) return null;
        return (
          <div key={t}>
            <div className="flex items-center gap-3 mb-3">
              <span className="w-8 h-1 rounded-full" style={{ background: tierColor[t] }} />
              <span className="font-mono text-xs uppercase tracking-[0.3em]" style={{ color: tierColor[t] }}>{t}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {list.map((s) => (
                <div key={s.id} data-testid={`event-sponsor-${s.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
                  <div className="flex items-center gap-3">
                    <img src={s.logo_url} alt={s.name} className="w-12 h-12 object-cover rounded-sm" />
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold truncate">{s.name}</div>
                      <div className="text-[10px] font-mono uppercase text-neutral-500">{s.tier}</div>
                    </div>
                  </div>
                  {s.description && <p className="text-xs text-neutral-400 mt-2 line-clamp-2">{s.description}</p>}
                  {isAdmin && (
                    <Button size="sm" variant="ghost" data-testid={`event-sponsor-del-${s.id}`} onClick={() => remove(s.id)} className="text-[#FF3B30] mt-2">Remove</Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
      {sponsors.length === 0 && <div className="text-neutral-500 text-center py-12 border border-dashed border-white/10 rounded-sm">No sponsors for this tournament yet.</div>}

      {isAdmin && (
        <form onSubmit={add} className="border border-white/10 rounded-sm bg-[#141414] p-5 mt-8 grid md:grid-cols-2 gap-3">
          <div className="md:col-span-2 font-display tracking-wider text-xl">ADD SPONSOR</div>
          <input data-testid="event-sponsor-name" placeholder="Sponsor name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-white text-sm" />
          <select data-testid="event-sponsor-tier" value={form.tier} onChange={(e) => setForm({ ...form, tier: e.target.value })} className="bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-white text-sm">
            {tiers.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <input data-testid="event-sponsor-logo" placeholder="Logo URL" value={form.logo_url} onChange={(e) => setForm({ ...form, logo_url: e.target.value })} className="md:col-span-2 bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-white text-sm" />
          <input placeholder="Website" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} className="bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-white text-sm" />
          <input placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="bg-black/40 border border-white/10 rounded-sm px-3 py-2 text-white text-sm" />
          <Button data-testid="event-sponsor-add" type="submit" className="md:col-span-2 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Add sponsor</Button>
        </form>
      )}
    </div>
  );
}
