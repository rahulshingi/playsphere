import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useSports, getPlayerFormat } from "@/hooks/useSports";
import { toast } from "sonner";
import { Trash2, Plus } from "lucide-react";
import VenuePicker from "@/components/VenuePicker";
import SuggestVenueButton from "@/components/event/SuggestVenueButton";

const INDIVIDUAL_SPORTS = new Set(["chess", "quiz", "hackathon"]);

export default function Admin() {
  const { user, ready, isAdmin, isPlatformAdmin, isPlayer, companyId } = useAuth();
  const { sports } = useSports();
  const onSportChange = (current, value) => {
    const fmt = getPlayerFormat(sports, value);
    return {
      ...current,
      sport: value,
      format: INDIVIDUAL_SPORTS.has(value) ? "knockout" : current.format,
      player_format: fmt === "both" ? "singles" : "",
    };
  };
  const nav = useNavigate();
  const [stats, setStats] = useState({});
  const [events, setEvents] = useState([]);
  const [venuePickerOpen, setVenuePickerOpen] = useState(false);
  const [teams, setTeams] = useState([]);
  const [sponsors, setSponsors] = useState([]);
  const [newEvent, setNewEvent] = useState({ name: "", sport: "football", format: "round_robin", event_type: "single_company", description: "", venue: "", banner_url: "", stream_url: "", player_format: "", contact_name: "", contact_email: "", contact_phone: "", listed_publicly: true });
  const [newSponsor, setNewSponsor] = useState({ name: "", tier: "bronze", logo_url: "", website: "", description: "", show_in_banner: true });
  const currentPF = getPlayerFormat(sports, newEvent.sport);

  // Player-hosted local matches: no admin dashboard, no teams/sponsors CRUD.
  // Just the create-event form + list of "MY LOCAL MATCHES" they've hosted.
  const playerHost = isPlayer && !isAdmin;

  const loadAll = async () => {
    if (playerHost) {
      // Only fetch events the player created (their local matches).
      const e = await api.get("/events?scope=hosted");
      setEvents(e.data);
      return;
    }
    const eventsUrl = companyId ? `/events?company_id=${companyId}` : "/events";
    const statsUrl = companyId ? "/stats/company" : "/stats";
    const [s, e, t, sp] = await Promise.all([api.get(statsUrl), api.get(eventsUrl), api.get("/teams"), api.get("/sponsors")]);
    setStats(s.data); setEvents(e.data); setTeams(t.data); setSponsors(sp.data);
  };

  useEffect(() => {
    if (ready && !isAdmin && !isPlayer) nav("/login");
    else if (ready) loadAll();
  }, [ready, isAdmin, isPlatformAdmin, isPlayer, companyId]);

  if (!ready) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  const createEvent = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...newEvent };
      if (currentPF !== "both") delete payload.player_format;
      const { data } = await api.post("/events", payload);
      toast.success(playerHost ? "Local match created — set up teams next" : "Event created");
      setNewEvent({ name: "", sport: "football", format: "round_robin", event_type: "single_company", description: "", venue: "", banner_url: "", stream_url: "", player_format: "", contact_name: "", contact_email: "", contact_phone: "", listed_publicly: true });
      // For players, jump straight to the event so they can add teams + members.
      if (playerHost && data?.id) {
        nav(`/events/${data.id}`);
        return;
      }
      loadAll();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed to create event"); }
  };

  // ---- Player-host view: simplified "Host a local match" flow. ----
  if (playerHost) {
    return (
      <div className="bg-[#0a0a0a] min-h-screen text-white">
        <Nav />
        <div className="max-w-5xl mx-auto px-6 pt-12 pb-24">
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Player · Local matches</div>
          <h1 className="font-display text-6xl tracking-wide mt-3">HOST A LOCAL MATCH</h1>
          <p className="text-neutral-400 mt-2 max-w-2xl">Set up a friendly neighborhood tournament. Add teams, invite players, run live scoring — everything you get on a corporate event, no approval needed.</p>

          <div className="grid md:grid-cols-2 gap-6 mt-10">
            <form onSubmit={createEvent} className="border border-white/10 rounded-sm p-6 bg-[#141414] space-y-3" data-testid="player-create-form">
              <div className="font-display tracking-wider text-2xl flex items-center gap-2"><Plus className="w-4 h-4 text-[#84CC16]" /> NEW LOCAL MATCH</div>
              <Input data-testid="player-event-name" placeholder="Match name (e.g. Sunday Cup 2026)" value={newEvent.name} onChange={(e) => setNewEvent({ ...newEvent, name: e.target.value })} required className="bg-black/40 border-white/10 text-white" />
              <Textarea data-testid="player-event-desc" placeholder="One-line description (optional)" value={newEvent.description} onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })} className="bg-black/40 border-white/10 text-white" />
              <div className="grid grid-cols-2 gap-2">
                <Select value={newEvent.sport} onValueChange={(v) => setNewEvent(onSportChange(newEvent, v))}>
                  <SelectTrigger data-testid="player-event-sport" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    {sports.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Select value={newEvent.format} onValueChange={(v) => setNewEvent({ ...newEvent, format: v })}>
                  <SelectTrigger data-testid="player-event-format" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    <SelectItem value="round_robin">Round-robin</SelectItem>
                    <SelectItem value="knockout">Knockout</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {currentPF === "both" && (
                <div data-testid="player-event-pf-wrap">
                  <div className="text-[10px] font-mono uppercase text-neutral-500 mb-1">/ Player format · {newEvent.sport}</div>
                  <Select value={newEvent.player_format || "singles"} onValueChange={(v) => setNewEvent({ ...newEvent, player_format: v })}>
                    <SelectTrigger data-testid="player-event-player-format" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      <SelectItem value="singles">Singles (1 vs 1)</SelectItem>
                      <SelectItem value="doubles">Doubles (2 vs 2)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              <Input data-testid="player-event-venue" placeholder="Venue (ground, court, backyard…)" value={newEvent.venue} onChange={(e) => setNewEvent({ ...newEvent, venue: e.target.value })} className="bg-black/40 border-white/10 text-white" />
              <Input data-testid="player-event-banner" placeholder="Banner image URL (optional)" value={newEvent.banner_url} onChange={(e) => setNewEvent({ ...newEvent, banner_url: e.target.value })} className="bg-black/40 border-white/10 text-white" />

              <label className="flex items-start gap-3 border border-white/10 rounded-sm bg-black/30 p-3 cursor-pointer" data-testid="player-event-public-wrap">
                <input
                  type="checkbox"
                  data-testid="player-event-listed-publicly"
                  checked={!!newEvent.listed_publicly}
                  onChange={(e) => setNewEvent({ ...newEvent, listed_publicly: e.target.checked })}
                  className="mt-1 accent-[#84CC16]"
                />
                <div>
                  <div className="text-sm text-white">Show on the public events page</div>
                  <div className="text-[11px] text-neutral-400">
                    On → your match appears on <span className="text-[#84CC16]">/events</span> with a <b>LOCAL MATCH</b> badge. Off → only reachable via direct link + your profile.
                  </div>
                </div>
              </label>

              <Button data-testid="player-create-event-btn" type="submit" className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Create local match</Button>
            </form>

            <div className="space-y-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-neutral-500">/ My local matches ({events.length})</div>
              {events.length === 0 && (
                <div data-testid="player-empty" className="border border-dashed border-white/10 rounded-sm p-6 text-center text-sm text-neutral-500 bg-[#0f0f0f]">
                  No local matches yet. Fill the form on the left to host your first one.
                </div>
              )}
              {events.map((e) => (
                <div key={e.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between" data-testid={`player-event-row-${e.id}`}>
                  <div>
                    <div className="font-semibold">{e.name}</div>
                    <div className="text-xs font-mono text-neutral-500 uppercase mt-0.5">{e.sport} · {(e.format || "").replace("_", " ")}</div>
                    <div className="flex gap-1.5 mt-1.5">
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-sm bg-[#84CC16]/15 text-[#84CC16] border border-[#84CC16]/30">LOCAL MATCH</span>
                      <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-sm border ${e.listed_publicly === false ? "bg-neutral-500/10 text-neutral-400 border-neutral-500/30" : "bg-[#06B6D4]/10 text-[#06B6D4] border-[#06B6D4]/30"}`}>
                        {e.listed_publicly === false ? "HIDDEN" : "PUBLIC"}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" data-testid={`player-open-event-${e.id}`} onClick={() => nav(`/events/${e.id}`)} className="text-[#84CC16]">Open</Button>
                    <Button size="sm" variant="ghost" data-testid={`player-delete-event-${e.id}`} onClick={async () => {
                      if (window.confirm(`Delete ${e.name}?`)) { await api.delete(`/events/${e.id}`); loadAll(); toast.success("Deleted"); }
                    }} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  const createSponsor = async (e) => {
    e.preventDefault();
    if (!newSponsor.name || !newSponsor.logo_url) return toast.error("Name and logo URL required");
    try {
      await api.post("/sponsors", newSponsor);
      toast.success("Sponsor added");
      setNewSponsor({ name: "", tier: "bronze", logo_url: "", website: "", description: "", show_in_banner: true });
      loadAll();
    } catch (err) { toast.error("Failed"); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FF3B30]">/ Control Room</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">ADMIN</h1>
        <p className="text-neutral-400 mt-2">Manage tournaments, teams and sponsors.</p>

        <div className="grid grid-cols-2 md:grid-cols-6 gap-px bg-white/10 mt-8 border border-white/10 rounded-sm overflow-hidden">
          {[
            ["Events", stats.events], ["Teams", stats.teams], ["Players", stats.players],
            ["Fixtures", stats.fixtures], ["Live", stats.live], ["Bookings", stats.bookings ?? stats.sponsors],
          ].map(([l, v]) => (
            <div key={l} className="bg-[#0a0a0a] p-4">
              <div className={`font-mono text-2xl ${l === "Live" ? "text-[#FF3B30]" : "text-white"}`}>{String(v ?? 0).padStart(2, "0")}</div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{l}</div>
            </div>
          ))}
        </div>

        <Tabs defaultValue="events" className="mt-10">
          <TabsList className="bg-[#141414] border border-white/10 rounded-sm">
            <TabsTrigger value="events" data-testid="admin-tab-events" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Events</TabsTrigger>
            <TabsTrigger value="teams" data-testid="admin-tab-teams" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Teams</TabsTrigger>
            <TabsTrigger value="sponsors" data-testid="admin-tab-sponsors" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Sponsors</TabsTrigger>
          </TabsList>

          <TabsContent value="events" className="mt-6">
            <div className="grid md:grid-cols-2 gap-6">
              <form onSubmit={createEvent} className="border border-white/10 rounded-sm p-6 bg-[#141414] space-y-3">
                <div className="font-display tracking-wider text-2xl flex items-center gap-2"><Plus className="w-4 h-4 text-[#84CC16]" /> NEW EVENT</div>
                <Input data-testid="admin-event-name" placeholder="Name" value={newEvent.name} onChange={(e) => setNewEvent({ ...newEvent, name: e.target.value })} required className="bg-black/40 border-white/10 text-white" />
                <Textarea data-testid="admin-event-desc" placeholder="Description" value={newEvent.description} onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <div className="grid grid-cols-2 gap-2">
                  <Select value={newEvent.sport} onValueChange={(v) => setNewEvent(onSportChange(newEvent, v))}>
                    <SelectTrigger data-testid="admin-event-sport" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      {sports.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Select value={newEvent.format} onValueChange={(v) => setNewEvent({ ...newEvent, format: v })}>
                    <SelectTrigger data-testid="admin-event-format" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      <SelectItem value="round_robin">Round-robin</SelectItem>
                      <SelectItem value="knockout">Knockout</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {currentPF === "both" && (
                  <div data-testid="admin-event-pf-wrap">
                    <div className="text-[10px] font-mono uppercase text-neutral-500 mb-1">/ Player format · {newEvent.sport}</div>
                    <Select value={newEvent.player_format || "singles"} onValueChange={(v) => setNewEvent({ ...newEvent, player_format: v })}>
                      <SelectTrigger data-testid="admin-event-player-format" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-[#141414] text-white border-white/10">
                        <SelectItem value="singles">Singles (1 vs 1)</SelectItem>
                        <SelectItem value="doubles">Doubles (2 vs 2)</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[10px] text-[#06B6D4] mt-1">
                      Racket sport — pick tournament format. Scoring uses the set-based racket template.
                    </p>
                  </div>
                )}
                {INDIVIDUAL_SPORTS.has(newEvent.sport) && (
                  <p data-testid="admin-event-format-hint" className="text-[11px] text-[#06B6D4]">
                    {newEvent.sport.charAt(0).toUpperCase() + newEvent.sport.slice(1)} is an individual sport — knockout selected by default. Switch to round-robin if you want everyone to play everyone.
                  </p>
                )}
                <div className="flex gap-2 flex-wrap">
                  <Input data-testid="admin-event-venue" placeholder="Venue" value={newEvent.venue} onChange={(e) => setNewEvent({ ...newEvent, venue: e.target.value })} className="bg-black/40 border-white/10 text-white flex-1 min-w-[200px]" />
                  <Button type="button" data-testid="admin-event-venue-pick" variant="outline" onClick={() => setVenuePickerOpen(true)} className="rounded-sm border-white/10 text-white whitespace-nowrap">Pick verified venue</Button>
                  <SuggestVenueButton onPick={(label) => setNewEvent({ ...newEvent, venue: label })} />
                </div>
                <div className="text-[10px] font-mono text-neutral-500 -mt-1">Can&apos;t find your venue? Click <span className="text-[#84CC16]">Suggest new venue</span> — Kreeda Nation admin will reach out to onboard it.</div>
                <Input data-testid="admin-event-banner" placeholder="Banner image URL" value={newEvent.banner_url} onChange={(e) => setNewEvent({ ...newEvent, banner_url: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <Input data-testid="admin-event-stream" placeholder="Live stream URL (YouTube / Twitch / any)" value={newEvent.stream_url} onChange={(e) => setNewEvent({ ...newEvent, stream_url: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <div className="border border-white/10 rounded-sm bg-black/30 p-3 space-y-2">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-[#EC4899]">/ Organiser contact (public on event page)</div>
                  <p className="text-[10px] text-neutral-400">Interested teams see these so they can reach you to participate. All three are optional; leave blank to keep private.</p>
                  <div className="grid grid-cols-2 gap-2">
                    <Input data-testid="admin-event-contact-name" placeholder="Contact person" value={newEvent.contact_name} onChange={(e) => setNewEvent({ ...newEvent, contact_name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                    <Input data-testid="admin-event-contact-phone" placeholder="Phone / WhatsApp" value={newEvent.contact_phone} onChange={(e) => setNewEvent({ ...newEvent, contact_phone: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                  </div>
                  <Input data-testid="admin-event-contact-email" placeholder="Contact email" value={newEvent.contact_email} onChange={(e) => setNewEvent({ ...newEvent, contact_email: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                </div>
                {isPlatformAdmin && (
                  <Select value={newEvent.event_type} onValueChange={(v) => setNewEvent({ ...newEvent, event_type: v })}>
                    <SelectTrigger data-testid="admin-event-type" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Event type" /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      <SelectItem value="single_company">Single company tournament</SelectItem>
                      <SelectItem value="inter_company">Inter-company tournament</SelectItem>
                      <SelectItem value="playsphere_organized">Kreeda Nation organized</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                <Button data-testid="admin-create-event-btn" type="submit" className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Create</Button>
              </form>

              <div className="space-y-2">
                {events.map((e) => (
                  <div key={e.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between">
                    <div>
                      <div className="font-semibold">{e.name}</div>
                      <div className="text-xs font-mono text-neutral-500 uppercase">{e.sport} · {e.format.replace("_", " ")}</div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => nav(`/events/${e.id}`)} className="text-[#84CC16]">Open</Button>
                      <Button size="sm" variant="ghost" data-testid={`admin-delete-event-${e.id}`} onClick={async () => {
                        if (window.confirm(`Delete ${e.name}?`)) { await api.delete(`/events/${e.id}`); loadAll(); toast.success("Deleted"); }
                      }} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="teams" className="mt-6">
            <div className="space-y-2">
              {teams.map((t) => (
                <div key={t.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-2 h-8 rounded-sm" style={{ background: t.color }} />
                    <div>
                      <div className="font-semibold">{t.name}</div>
                      <div className="text-xs font-mono text-neutral-500 uppercase">{t.department || "—"}</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" onClick={() => nav(`/teams/${t.id}`)} className="text-[#84CC16]">View</Button>
                    <Button size="sm" variant="ghost" data-testid={`admin-delete-team-${t.id}`} onClick={async () => {
                      if (window.confirm(`Delete ${t.name}?`)) { await api.delete(`/teams/${t.id}`); loadAll(); toast.success("Deleted"); }
                    }} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="sponsors" className="mt-6">
            <div className="grid md:grid-cols-2 gap-6">
              <form onSubmit={createSponsor} className="border border-white/10 rounded-sm p-6 bg-[#141414] space-y-3">
                <div className="font-display tracking-wider text-2xl flex items-center gap-2"><Plus className="w-4 h-4 text-[#84CC16]" /> NEW SPONSOR</div>
                <Input data-testid="admin-sponsor-name" placeholder="Name" value={newSponsor.name} onChange={(e) => setNewSponsor({ ...newSponsor, name: e.target.value })} required className="bg-black/40 border-white/10 text-white" />
                <Input data-testid="admin-sponsor-logo" placeholder="Logo URL" value={newSponsor.logo_url} onChange={(e) => setNewSponsor({ ...newSponsor, logo_url: e.target.value })} required className="bg-black/40 border-white/10 text-white" />
                <Input data-testid="admin-sponsor-website" placeholder="Website" value={newSponsor.website} onChange={(e) => setNewSponsor({ ...newSponsor, website: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <Select value={newSponsor.tier} onValueChange={(v) => setNewSponsor({ ...newSponsor, tier: v })}>
                  <SelectTrigger data-testid="admin-sponsor-tier" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    <SelectItem value="title">Title</SelectItem>
                    <SelectItem value="gold">Gold</SelectItem>
                    <SelectItem value="silver">Silver</SelectItem>
                    <SelectItem value="bronze">Bronze</SelectItem>
                  </SelectContent>
                </Select>
                <Textarea data-testid="admin-sponsor-desc" placeholder="Description" value={newSponsor.description} onChange={(e) => setNewSponsor({ ...newSponsor, description: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <Button data-testid="admin-create-sponsor-btn" type="submit" className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Add sponsor</Button>
              </form>

              <div className="space-y-2">
                {sponsors.map((s) => (
                  <div key={s.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <img src={s.logo_url} alt={s.name} className="w-10 h-10 object-cover rounded-sm" />
                      <div>
                        <div className="font-semibold">{s.name}</div>
                        <div className="text-xs font-mono text-neutral-500 uppercase">{s.tier}</div>
                      </div>
                    </div>
                    <Button size="sm" variant="ghost" data-testid={`admin-delete-sponsor-${s.id}`} onClick={async () => {
                      if (window.confirm(`Delete ${s.name}?`)) { await api.delete(`/sponsors/${s.id}`); loadAll(); toast.success("Deleted"); }
                    }} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
      <Footer />
      <VenuePicker open={venuePickerOpen} onClose={() => setVenuePickerOpen(false)} sport={newEvent.sport} onPick={(v) => setNewEvent({ ...newEvent, venue: `${v.title} · ${v.city}` })} />
    </div>
  );
}
