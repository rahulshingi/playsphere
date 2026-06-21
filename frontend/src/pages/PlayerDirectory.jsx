import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Eye, MapPin, ExternalLink } from "lucide-react";
import { SPORT_SCHEMAS } from "@/lib/sportProfileSchema";

export function PlayerSearch() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);

  const load = () => {
    const url = q ? `/players/profiles?q=${encodeURIComponent(q)}` : "/players/profiles";
    api.get(url).then((r) => setItems(r.data));
  };

  useEffect(() => {
    if (ready && !user) { nav("/players/login"); return; }
    if (ready) load();
  }, [ready, user]);

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-6xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Players</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">FIND PLAYERS</h1>
        <p className="text-neutral-400 mt-2 text-sm">Search across every player registered on Kreeda Nation.</p>

        <form onSubmit={(e) => { e.preventDefault(); load(); }} className="mt-8 flex gap-2 max-w-xl">
          <Input data-testid="player-search-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, city or mobile" className="bg-[#141414] border-white/10 text-white" />
          <Button data-testid="player-search-btn" type="submit" className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Search</Button>
        </form>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-8">
          {items.map((p) => (
            <Link key={p.id} to={`/players/profiles/${p.id}`} data-testid={`player-search-card-${p.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4 hover-lift block">
              <div className="flex items-center gap-3">
                <img src={p.photo_url || "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} className="w-14 h-14 rounded-sm object-cover" alt="" />
                <div className="flex-1 min-w-0">
                  <div className="font-semibold truncate">{p.name}</div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500 truncate">{p.role || "any"} · {p.city || "—"}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm text-[#84CC16]">{p.view_count || 0}</div>
                  <div className="text-[10px] font-mono text-neutral-500 uppercase flex items-center gap-1 justify-end"><Eye className="w-3 h-3" /> views</div>
                </div>
              </div>
              {p.company_name && <div className="text-[10px] font-mono text-neutral-400 mt-2 uppercase tracking-widest">@ {p.company_name}</div>}
            </Link>
          ))}
          {items.length === 0 && <div className="col-span-full text-center text-neutral-500 py-20">No players match.</div>}
        </div>
      </div>
      <Footer />
    </div>
  );
}

export function PlayerProfileView() {
  const { id } = useParams();
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [p, setP] = useState(null);

  useEffect(() => {
    if (ready && !user) { nav("/players/login"); return; }
    if (ready) api.get(`/players/profiles/${id}`).then((r) => setP(r.data));
  }, [ready, user, id]);

  if (!p) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-5xl mx-auto px-6 pt-12 pb-24">
        <Link to="/players/profiles" className="text-xs font-mono text-neutral-400 hover:text-white">← Back to players</Link>

        <div className="mt-6 grid md:grid-cols-2 gap-10">
          <div className="border border-white/10 rounded-sm overflow-hidden bg-[#141414] aspect-square relative">
            <img src={p.photo_url || "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} alt="" className="w-full h-full object-cover" />
            {p.jersey_number != null && <span className="absolute top-5 right-5 font-mono text-7xl text-white/90">#{p.jersey_number}</span>}
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black to-transparent p-6">
              <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-300">{p.company_name || "Independent"}</div>
              <div className="font-display text-4xl tracking-wide">{p.name}</div>
            </div>
          </div>

          <div>
            <div className="flex items-end justify-between">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16]">/ Player</div>
                <h1 data-testid="player-profile-name" className="font-display text-5xl tracking-wide mt-2">{p.name}</h1>
              </div>
              <div className="text-right">
                <div className="font-display text-4xl text-[#84CC16]" data-testid="player-profile-views">{p.view_count || 0}</div>
                <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-widest flex items-center gap-1 justify-end"><Eye className="w-3 h-3" /> Views</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-px bg-white/10 mt-8 border border-white/10 rounded-sm overflow-hidden">
              {[
                ["JERSEY", p.jersey_number ?? "—"],
                ["CITY", p.city || "—"],
                ["MOBILE", p.mobile_masked || p.mobile || "—"],
                ["DOB", p.dob || "—"],
              ].map(([l, v]) => (
                <div key={l} className="bg-[#0a0a0a] p-4">
                  <div className="font-mono text-sm">{v}</div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mt-1">{l}</div>
                </div>
              ))}
            </div>

            {/* Sport-specific cards — one per interested sport */}
            <SportCards p={p} />

            {p.bio && <p className="mt-6 text-neutral-300 leading-relaxed">{p.bio}</p>}

            {p.cricheroes_url && (
              <a href={p.cricheroes_url} target="_blank" rel="noopener noreferrer" data-testid="player-cricheroes-link"
                className="mt-6 inline-flex items-center gap-2 px-4 py-2 rounded-sm border border-[#84CC16]/40 text-[#84CC16] hover:bg-[#84CC16]/10 text-sm font-mono uppercase tracking-widest">
                <ExternalLink className="w-4 h-4" /> Cric Heroes profile
              </a>
            )}
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

/** Renders one card per sport the player is interested in. Falls back to legacy
 * cricket fields for players who haven't migrated to multi-sport yet. */
function SportCards({ p }) {
  const interested = p.interested_sports?.length ? p.interested_sports : ["cricket"];
  const sportProfiles = p.sport_profiles || {};

  // Legacy fallback so old cricket-only profiles still render meaningfully.
  const legacyCricket = {
    role: p.role || "any",
    batting_hand: p.batting_hand || "right",
    bowling_style: p.bowling_style || "none",
    jersey_number: p.jersey_number,
    cricheroes_url: p.cricheroes_url,
  };

  return (
    <div className="mt-6 space-y-3" data-testid="player-sport-cards">
      {interested.map((sport) => {
        const schema = SPORT_SCHEMAS[sport];
        if (!schema) return null;
        const sp = (sport === "cricket" && !sportProfiles.cricket) ? legacyCricket : (sportProfiles[sport] || {});
        const rows = schema.fields
          .filter((f) => sp[f.key] !== undefined && sp[f.key] !== null && sp[f.key] !== "")
          .map((f) => [f.label.toUpperCase(), String(sp[f.key]).replace(/-/g, " ")]);
        return (
          <div key={sport} data-testid={`player-card-${sport}`} className="border border-white/10 rounded-sm bg-black/30 p-4">
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: schema.color }} />
              <div className="font-display tracking-wider text-lg">{schema.label.toUpperCase()}</div>
            </div>
            {rows.length === 0 ? (
              <div className="text-xs font-mono text-neutral-500 mt-2">No details yet.</div>
            ) : (
              <div className="grid grid-cols-2 gap-px bg-white/5 mt-3 border border-white/10 rounded-sm overflow-hidden">
                {rows.map(([l, v]) => (
                  <div key={l} className="bg-[#0a0a0a] p-3">
                    <div className="font-mono text-sm">{v}</div>
                    <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mt-1">{l}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

