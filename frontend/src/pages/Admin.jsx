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
import { SPORTS } from "@/lib/sports";
import { toast } from "sonner";
import { Trash2, Plus } from "lucide-react";

export default function Admin() {
  const { user, ready, isAdmin, isPlatformAdmin, companyId } = useAuth();
  const nav = useNavigate();
  const [stats, setStats] = useState({});
  const [events, setEvents] = useState([]);
  const [teams, setTeams] = useState([]);
  const [sponsors, setSponsors] = useState([]);
  const [newEvent, setNewEvent] = useState({ name: "", sport: "football", format: "round_robin", event_type: "single_company", description: "", venue: "", banner_url: "", stream_url: "" });
  const [newSponsor, setNewSponsor] = useState({ name: "", tier: "bronze", logo_url: "", website: "", description: "", show_in_banner: true });

  const loadAll = async () => {
    const eventsUrl = companyId ? `/events?company_id=${companyId}` : "/events";
    const statsUrl = companyId ? "/stats/company" : "/stats";
    const [s, e, t, sp] = await Promise.all([api.get(statsUrl), api.get(eventsUrl), api.get("/teams"), api.get("/sponsors")]);
    setStats(s.data); setEvents(e.data); setTeams(t.data); setSponsors(sp.data);
  };

  useEffect(() => {
    if (ready && !isAdmin) nav("/login");
    else if (ready) loadAll();
  }, [ready, isAdmin, isPlatformAdmin, companyId]);

  if (!ready) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  const createEvent = async (e) => {
    e.preventDefault();
    try {
      await api.post("/events", newEvent);
      toast.success("Event created");
      setNewEvent({ name: "", sport: "football", format: "round_robin", event_type: "single_company", description: "", venue: "", banner_url: "", stream_url: "" });
      loadAll();
    } catch (err) { toast.error("Failed to create event"); }
  };

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
                  <Select value={newEvent.sport} onValueChange={(v) => setNewEvent({ ...newEvent, sport: v })}>
                    <SelectTrigger data-testid="admin-event-sport" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      {SPORTS.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
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
                <Input data-testid="admin-event-venue" placeholder="Venue" value={newEvent.venue} onChange={(e) => setNewEvent({ ...newEvent, venue: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <Input data-testid="admin-event-banner" placeholder="Banner image URL" value={newEvent.banner_url} onChange={(e) => setNewEvent({ ...newEvent, banner_url: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <Input data-testid="admin-event-stream" placeholder="Live stream URL (YouTube / Twitch / any)" value={newEvent.stream_url} onChange={(e) => setNewEvent({ ...newEvent, stream_url: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                {isPlatformAdmin && (
                  <Select value={newEvent.event_type} onValueChange={(v) => setNewEvent({ ...newEvent, event_type: v })}>
                    <SelectTrigger data-testid="admin-event-type" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Event type" /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      <SelectItem value="single_company">Single company tournament</SelectItem>
                      <SelectItem value="inter_company">Inter-company tournament</SelectItem>
                      <SelectItem value="playsphere_organized">PlaySphere organized</SelectItem>
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
    </div>
  );
}
