import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import SponsorBanner from "@/components/SponsorBanner";
import { Button } from "@/components/ui/button";
import { ArrowRight, Users, CalendarDays, Activity, Trophy, Sparkles } from "lucide-react";
import { renderScore, sportColor } from "@/lib/sports";

export default function Home() {
  const [stats, setStats] = useState({ events: 0, teams: 0, players: 0, live: 0 });
  const [events, setEvents] = useState([]);
  const [liveFixtures, setLiveFixtures] = useState([]);
  const [teamMap, setTeamMap] = useState({});

  useEffect(() => {
    api.get("/stats").then((r) => setStats(r.data));
    api.get("/teams").then((r) => setTeamMap(Object.fromEntries(r.data.map((t) => [t.id, t]))));
    api.get("/events").then(async (r) => {
      setEvents(r.data.slice(0, 3));
      const all = await Promise.all(r.data.map((e) => api.get(`/events/${e.id}/fixtures`).then(res => res.data.map(f => ({ ...f, event: e })))));
      const live = all.flat().filter((f) => f.status === "live").slice(0, 3);
      setLiveFixtures(live);
    });
  }, []);

  return (
    <div className="App bg-[#0a0a0a] min-h-screen text-white">
      <Nav />

      {/* HERO */}
      <section data-testid="hero-section" className="relative overflow-hidden grain">
        <div className="absolute inset-0">
          <img
            src="https://images.pexels.com/photos/1657324/pexels-photo-1657324.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
            alt=""
            className="w-full h-full object-cover opacity-40"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-black via-black/80 to-black/20" />
          <div className="absolute inset-0 tactical-grid opacity-40" />
        </div>
        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-32">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-sm bg-white/5 border border-white/10">
            <span className="w-1.5 h-1.5 rounded-full bg-[#FF3B30] live-pulse" />
            <span className="font-mono text-[10px] tracking-[0.3em] uppercase text-neutral-300">
              {stats.live > 0 ? `${stats.live} match${stats.live > 1 ? "es" : ""} live now` : "Season in motion"}
            </span>
          </div>
          <h1 className="font-display text-6xl md:text-8xl lg:text-9xl mt-6 leading-[0.92] tracking-wide max-w-4xl">
            WHERE TEAMS<br />
            <span className="text-[#007AFF]">COMPETE,</span> CONNECT<br />
            &amp; GROW.
          </h1>
          <p className="mt-8 max-w-xl text-neutral-300 text-lg leading-relaxed">
            PlaySphere turns workplace tournaments into rituals — sports, quizzes, hackathons, all in one
            command center. Register a team, follow live scoring, climb the standings.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <Link to="/register-team">
              <Button data-testid="hero-register-btn" size="lg" className="bg-[#007AFF] hover:bg-[#0066d6] rounded-sm px-7 h-12">
                Register Your Team <ArrowRight className="ml-2 w-4 h-4" />
              </Button>
            </Link>
            <Link to="/events">
              <Button data-testid="hero-events-btn" size="lg" variant="outline" className="rounded-sm h-12 px-7 border-white/20 bg-white/0 hover:bg-white/5 text-white">
                Browse Events
              </Button>
            </Link>
          </div>

          {/* stat strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/10 mt-20 border border-white/10 rounded-sm overflow-hidden">
            {[
              { label: "Events", value: stats.events, icon: CalendarDays },
              { label: "Teams", value: stats.teams, icon: Users },
              { label: "Players", value: stats.players, icon: Trophy },
              { label: "Live Now", value: stats.live, icon: Activity, accent: true },
            ].map((s, i) => (
              <div key={i} className="bg-[#0a0a0a] p-6">
                <s.icon className={`w-4 h-4 ${s.accent ? "text-[#FF3B30]" : "text-neutral-500"}`} />
                <div className={`font-mono text-4xl mt-3 ${s.accent ? "text-[#FF3B30]" : "text-white"}`}>
                  {String(s.value).padStart(2, "0")}
                </div>
                <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-neutral-500 mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <SponsorBanner />

      {/* LIVE ZONE */}
      {liveFixtures.length > 0 && (
        <section className="max-w-7xl mx-auto px-6 py-20">
          <div className="flex items-end justify-between mb-8">
            <div>
              <div className="font-mono text-[10px] tracking-[0.3em] text-[#FF3B30] uppercase">● Live Zone</div>
              <h2 className="font-display text-5xl mt-2 tracking-wide">HAPPENING NOW</h2>
            </div>
            <Link to="/events" className="text-sm text-neutral-400 hover:text-[#007AFF]">View all →</Link>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {liveFixtures.map((f) => (
              <LiveCard key={f.id} fixture={f} teamMap={teamMap} />
            ))}
          </div>
        </section>
      )}

      {/* FEATURES Bento */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="font-mono text-[10px] tracking-[0.3em] text-[#007AFF] uppercase">/ Platform</div>
        <h2 className="font-display text-5xl mt-2 tracking-wide">EVERYTHING TO RUN THE SEASON</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-12">
          <FeatureCard icon={Users} title="TEAM REGISTRATION" desc="Captains register teams in under 60 seconds. Departments, colors, rosters all in one form." className="md:row-span-2" big />
          <FeatureCard icon={CalendarDays} title="FIXTURE GENERATION" desc="One click — round-robin or knockout bracket, automatically balanced." />
          <FeatureCard icon={Activity} title="LIVE SCORING" desc="Sport-specific scorecards: cricket overs, badminton sets, football goals." accent />
          <FeatureCard icon={Trophy} title="STANDINGS" desc="Real-time leaderboards. Points, win-loss, position swings." />
          <FeatureCard icon={Sparkles} title="PLAYER PROFILES" desc="Stats, jerseys and stories. Stars get the spotlight." />
        </div>
      </section>

      {/* UPCOMING EVENTS */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="font-mono text-[10px] tracking-[0.3em] text-neutral-500 uppercase">/ Calendar</div>
            <h2 className="font-display text-5xl mt-2 tracking-wide">UPCOMING EVENTS</h2>
          </div>
          <Link to="/events" className="text-sm text-neutral-400 hover:text-[#007AFF]" data-testid="home-view-all-events">View all →</Link>
        </div>
        <div className="grid md:grid-cols-3 gap-5">
          {events.map((e) => (
            <Link
              to={`/events/${e.id}`}
              key={e.id}
              data-testid={`home-event-card-${e.id}`}
              className="group relative overflow-hidden rounded-sm border border-white/10 bg-[#141414] hover-lift"
            >
              <div className="h-44 overflow-hidden">
                <img src={e.banner_url || "https://images.pexels.com/photos/1657324/pexels-photo-1657324.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 opacity-80" />
              </div>
              <div className="p-5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm border" style={{ borderColor: sportColor(e.sport), color: sportColor(e.sport) }}>
                    {e.sport}
                  </span>
                  <span className="font-mono text-[10px] uppercase text-neutral-500">{e.status}</span>
                </div>
                <h3 className="text-lg font-semibold mt-3 group-hover:text-[#007AFF] transition-colors">{e.name}</h3>
                <p className="text-sm text-neutral-400 mt-1 line-clamp-2">{e.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <Footer />
    </div>
  );
}

function FeatureCard({ icon: Icon, title, desc, accent, big, className = "" }) {
  return (
    <div className={`relative p-8 rounded-sm border border-white/10 bg-[#141414] hover-lift ${className} ${big ? "md:p-10" : ""}`}>
      <Icon className={`w-5 h-5 ${accent ? "text-[#FF3B30]" : "text-[#007AFF]"}`} />
      <div className="font-display tracking-wider text-2xl mt-4">{title}</div>
      <p className="text-sm text-neutral-400 mt-3 max-w-xs leading-relaxed">{desc}</p>
      {big && (
        <div className="absolute right-6 bottom-6 font-mono text-[10px] tracking-widest text-neutral-600">01 / 05</div>
      )}
    </div>
  );
}

function LiveCard({ fixture, teamMap }) {
  const f = fixture;
  const a = teamMap[f.team_a_id];
  const b = teamMap[f.team_b_id];
  return (
    <Link to={`/events/${f.event.id}`} className="block p-5 rounded-sm border border-[#FF3B30]/40 bg-[#141414] hover-lift">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#FF3B30] live-pulse" />
          <span className="font-mono text-[10px] text-[#FF3B30] tracking-widest uppercase">LIVE</span>
        </div>
        <span className="font-mono text-[10px] text-neutral-500 uppercase">{f.event.sport}</span>
      </div>
      <div className="mt-4 space-y-2 font-mono">
        <Row team={a} value={renderScore(f.event.sport, f.score?.team_a)} />
        <Row team={b} value={renderScore(f.event.sport, f.score?.team_b)} />
      </div>
      <div className="text-xs text-neutral-500 mt-4">{f.event.name}</div>
    </Link>
  );
}

function Row({ team, value }) {
  return (
    <div className="flex items-center justify-between border-b border-white/5 pb-1.5">
      <div className="flex items-center gap-2">
        <span className="w-1.5 h-5 rounded-sm" style={{ background: team?.color || "#333" }} />
        <span className="text-sm text-neutral-300">{team?.name || "TBD"}</span>
      </div>
      <span className="text-lg text-white">{value}</span>
    </div>
  );
}
