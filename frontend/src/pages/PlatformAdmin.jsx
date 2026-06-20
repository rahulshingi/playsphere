import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { CURRENCIES, fmtPrice } from "@/lib/currency";
import { SPORTS } from "@/lib/sports";
import ImageUpload from "@/components/ImageUpload";
import DashboardPanel from "@/components/DashboardPanel";
import SportsManager from "@/components/SportsManager";
import { AdminReviewsQueue } from "@/components/Reviews";
import AdminTeam from "@/components/AdminTeam";

const INDIVIDUAL_SPORTS = new Set(["chess", "quiz", "hackathon"]);
const onSportChange = (current, value) => ({
  ...current,
  sport: value,
  format: INDIVIDUAL_SPORTS.has(value) ? "knockout" : current.format,
});

const CATEGORIES = ["streaming", "apparel", "merchandise", "awards", "venue", "equipment", "training", "other"];

export default function PlatformAdmin() {
  const { ready, isPlatformAdmin, isSuperAdmin, hasPermission } = useAuth();
  const nav = useNavigate();
  const [services, setServices] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [events, setEvents] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [listings, setListings] = useState([]);
  const [settings, setSettings] = useState({});
  const [about, setAbout] = useState({ company_description: "", mission: "", vision: "", founders: [], directors: [] });
  const [editing, setEditing] = useState(null);
  const blankEvent = { name: "", sport: "cricket", format: "round_robin", event_type: "playsphere_organized", description: "", venue: "", banner_url: "", stream_url: "" };
  const [newEvent, setNewEvent] = useState(blankEvent);

  const blankService = {
    name: "",
    category: "other",
    description: "",
    images: [""],
    base_price: 0,
    currency: "USD",
    price_unit: "per booking",
    config_fields: [],
    variants: [],
    allow_custom_text: false,
    custom_text_label: "Custom text",
    active: true,
  };

  const load = () => Promise.all([
    api.get("/services?include_inactive=true"),
    api.get("/companies"),
    api.get("/events"),
    api.get("/bookings"),
    api.get("/vendors"),
    api.get("/admin/listings"),
    api.get("/settings"),
    api.get("/about"),
  ]).then(([s, c, ev, b, v, l, st, ab]) => {
    setServices(s.data); setCompanies(c.data); setEvents(ev.data); setBookings(b.data);
    setVendors(v.data); setListings(l.data); setSettings(st.data);
    setAbout({ company_description: "", mission: "", vision: "", founders: [], directors: [], ...ab.data });
  });

  useEffect(() => {
    if (ready && !isPlatformAdmin) { nav("/login"); return; }
    if (ready) load();
  }, [ready, isPlatformAdmin]);

  const saveService = async () => {
    const payload = { ...editing };
    payload.base_price = Number(payload.base_price) || 0;
    payload.images = (payload.images || []).filter((x) => x && x.trim());
    try {
      if (payload.id) await api.patch(`/services/${payload.id}`, payload);
      else await api.post("/services", payload);
      toast.success("Saved");
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const deleteService = async (id) => {
    if (!window.confirm("Delete service?")) return;
    await api.delete(`/services/${id}`); load();
  };

  const createEvent = async (e) => {
    e.preventDefault();
    if (!newEvent.name) return toast.error("Event name required");
    try {
      await api.post("/events", newEvent);
      toast.success("Event created");
      setNewEvent(blankEvent);
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const deleteEvent = async (id, name) => {
    if (!window.confirm(`Delete ${name}? This will also delete its fixtures.`)) return;
    try {
      await api.delete(`/events/${id}`);
      toast.success("Deleted");
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FF3B30]">/ Kreeda Nation HQ</div>
        <div className="flex items-end justify-between">
          <h1 className="font-display text-6xl tracking-wide mt-3">PLATFORM ADMIN</h1>
          {isSuperAdmin && (
            <Button data-testid="platform-new-service" onClick={() => setEditing(blankService)} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
              <Plus className="w-4 h-4 mr-1" /> New service
            </Button>
          )}
        </div>

        <Tabs defaultValue="dashboard" className="mt-10">
          <TabsList className="bg-[#141414] border border-white/10 rounded-sm flex-wrap">
            <TabsTrigger value="dashboard" data-testid="pa-tab-dashboard" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Dashboard</TabsTrigger>
            <TabsTrigger value="services" data-testid="pa-tab-services" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Services ({services.length})</TabsTrigger>
            <TabsTrigger value="events" data-testid="pa-tab-events" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Events ({events.length})</TabsTrigger>
            <TabsTrigger value="sports" data-testid="pa-tab-sports" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Sports</TabsTrigger>
            <TabsTrigger value="companies" data-testid="pa-tab-companies" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Companies ({companies.length})</TabsTrigger>
            <TabsTrigger value="bookings" data-testid="pa-tab-bookings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Bookings ({bookings.length})</TabsTrigger>
            <TabsTrigger value="vendors" data-testid="pa-tab-vendors" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Vendors ({vendors.length})</TabsTrigger>
            <TabsTrigger value="listings" data-testid="pa-tab-listings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Listings ({listings.length})</TabsTrigger>
            <TabsTrigger value="settings" data-testid="pa-tab-settings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Settings</TabsTrigger>
            <TabsTrigger value="about" data-testid="pa-tab-about" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">About page</TabsTrigger>
            <TabsTrigger value="reviews" data-testid="pa-tab-reviews" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Reviews</TabsTrigger>
            <TabsTrigger value="accounts" data-testid="pa-tab-accounts" className="data-[state=active]:bg-[#FF3B30] data-[state=active]:text-white rounded-sm">Accounts</TabsTrigger>
            {isSuperAdmin && (
              <TabsTrigger value="team" data-testid="pa-tab-team" className="data-[state=active]:bg-[#FF3B30] data-[state=active]:text-white rounded-sm">Team</TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="dashboard" className="mt-6">
            <DashboardPanel role="admin" />
          </TabsContent>

          <TabsContent value="sports" className="mt-6">
            <SportsManager />
          </TabsContent>

          <TabsContent value="services" className="mt-6 space-y-2">
            {services.map((s) => (
              <div key={s.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <img src={s.images?.[0] || "https://placehold.co/80x80/141414/84CC16?text=PS"} className="w-12 h-12 object-cover rounded-sm" alt="" />
                  <div>
                    <div className="font-semibold">{s.name}{!s.active && <span className="ml-2 text-[10px] uppercase font-mono text-amber-400">INACTIVE</span>}</div>
                    <div className="text-xs font-mono text-neutral-500 uppercase">{s.category} · {fmtPrice(s.base_price, s.currency)} {s.price_unit}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  {isSuperAdmin && <Button size="sm" variant="ghost" data-testid={`pa-edit-${s.id}`} onClick={() => setEditing({ ...s, images: s.images?.length ? s.images : [""] })} className="text-[#84CC16]">Edit</Button>}
                  {isSuperAdmin && <Button size="sm" variant="ghost" data-testid={`pa-delete-${s.id}`} onClick={() => deleteService(s.id)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>}
                </div>
              </div>
            ))}
          </TabsContent>

          <TabsContent value="events" className="mt-6">
            <div className="grid md:grid-cols-2 gap-6">
              <form onSubmit={createEvent} className="border border-white/10 rounded-sm p-6 bg-[#141414] space-y-3">
                <div className="font-display tracking-wider text-2xl flex items-center gap-2"><Plus className="w-4 h-4 text-[#84CC16]" /> NEW EVENT</div>
                <Input data-testid="pa-event-name" placeholder="Event name (e.g. Kreeda Nation Cricket League 2026)" value={newEvent.name} onChange={(e) => setNewEvent({ ...newEvent, name: e.target.value })} required className="bg-black/40 border-white/10 text-white" />
                <Textarea data-testid="pa-event-desc" placeholder="Description" value={newEvent.description} onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <div className="grid grid-cols-2 gap-2">
                  <Select value={newEvent.sport} onValueChange={(v) => setNewEvent(onSportChange(newEvent, v))}>
                    <SelectTrigger data-testid="pa-event-sport" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      {SPORTS.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Select value={newEvent.format} onValueChange={(v) => setNewEvent({ ...newEvent, format: v })}>
                    <SelectTrigger data-testid="pa-event-format" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      <SelectItem value="round_robin">Round-robin</SelectItem>
                      <SelectItem value="knockout">Knockout</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {INDIVIDUAL_SPORTS.has(newEvent.sport) && (
                  <p data-testid="pa-event-format-hint" className="text-[11px] text-[#06B6D4]">
                    {newEvent.sport.charAt(0).toUpperCase() + newEvent.sport.slice(1)} is an individual sport — knockout selected by default. Switch to round-robin if you want everyone to play everyone.
                  </p>
                )}
                <Select value={newEvent.event_type} onValueChange={(v) => setNewEvent({ ...newEvent, event_type: v })}>
                  <SelectTrigger data-testid="pa-event-type" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    <SelectItem value="playsphere_organized">Kreeda Nation organized</SelectItem>
                    <SelectItem value="inter_company">Inter-company tournament</SelectItem>
                    <SelectItem value="single_company">Single company tournament</SelectItem>
                  </SelectContent>
                </Select>
                <Input data-testid="pa-event-venue" placeholder="Venue" value={newEvent.venue} onChange={(e) => setNewEvent({ ...newEvent, venue: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <ImageUpload value={newEvent.banner_url} onChange={(v) => setNewEvent({ ...newEvent, banner_url: v })} testid="pa-event-banner" placeholder="Banner image — paste URL or upload" />
                <Input data-testid="pa-event-stream" placeholder="Live stream URL (YouTube / Twitch / any)" value={newEvent.stream_url} onChange={(e) => setNewEvent({ ...newEvent, stream_url: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                <Button data-testid="pa-create-event-btn" type="submit" className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Create event</Button>
                <p className="text-[10px] text-neutral-500 leading-relaxed">Once created, click <strong>Open</strong> on the event to add teams, assign captains, attach participating companies (inter-company), and add players.</p>
              </form>

              <div className="space-y-2">
                {events.length === 0 && <div className="text-neutral-500 text-sm text-center py-12 border border-dashed border-white/10 rounded-sm">No events yet.</div>}
                {events.map((e) => (
                  <div key={e.id} data-testid={`pa-event-row-${e.id}`} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-semibold truncate">{e.name}</div>
                      <div className="text-[10px] font-mono text-neutral-500 uppercase tracking-widest mt-0.5">
                        {e.sport} · {e.format.replace("_", " ")} · {(e.event_type || "single_company").replace("_", " ")}
                        {e.stream_url && <span className="ml-2 text-[#FF3B30]">● LIVE LINK</span>}
                      </div>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <Button size="sm" variant="ghost" data-testid={`pa-event-open-${e.id}`} onClick={() => nav(`/events/${e.id}`)} className="text-[#84CC16]">Open</Button>
                      {hasPermission("manage_events") && <Button size="sm" variant="ghost" data-testid={`pa-event-del-${e.id}`} onClick={() => deleteEvent(e.id, e.name)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="companies" className="mt-6 space-y-2">
            {companies.map((c) => (
              <Link key={c.id} to={`/platform-admin/companies/${c.id}`} data-testid={`pa-company-${c.id}`}
                className="block border border-white/10 rounded-sm p-4 bg-[#141414] hover:border-[#84CC16] transition-colors">
                <div className="font-semibold">{c.name}</div>
                <div className="text-xs font-mono text-neutral-500">{c.contact_email} · {c.contact_phone || "—"} · /{c.slug}</div>
              </Link>
            ))}
          </TabsContent>

          <TabsContent value="bookings" className="mt-6">
            <Link to="/bookings" className="text-[#84CC16] hover:underline text-sm">→ Manage all bookings</Link>
            <div className="grid md:grid-cols-3 gap-3 mt-4">
              {bookings.slice(0, 12).map((b) => (
                <div key={b.id} className="border border-white/10 rounded-sm p-4 bg-[#141414]">
                  <div className="text-[10px] font-mono uppercase text-neutral-500">{b.company_name}</div>
                  <div className="font-semibold mt-1">{b.service_name}</div>
                  <div className="text-xs text-neutral-400 mt-1">qty {b.quantity} · {fmtPrice(b.total_price, b.currency)} · {b.status}</div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="vendors" className="mt-6 space-y-2">
            {vendors.map((v) => (
              <div key={v.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between hover:border-[#EC4899] transition-colors">
                <Link to={`/platform-admin/vendors/${v.id}`} data-testid={`pa-vendor-${v.id}`} className="flex-1 min-w-0">
                  <div className="font-semibold">{v.business_name} <span className="text-[10px] font-mono uppercase text-neutral-500 ml-2">{v.vendor_type}</span></div>
                  <div className="text-xs font-mono text-neutral-500">{v.contact_name} · {v.city} · {v.mobile} · {v.email}</div>
                </Link>
                <div className="flex items-center gap-2 ml-3">
                  <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${v.approved ? "text-[#84CC16] border-[#84CC16]/40" : "text-amber-400 border-amber-500/40"}`}>{v.approved ? "APPROVED" : "PENDING"}</span>
                  {hasPermission("manage_vendors") && (
                    <Button size="sm" data-testid={`pa-approve-vendor-${v.id}`} onClick={async () => { await api.patch(`/vendors/${v.id}/approve`, { approved: !v.approved }); load(); toast.success(v.approved ? "Revoked" : "Approved"); }}
                      className={v.approved ? "bg-white/10 hover:bg-white/20 text-white rounded-sm" : "bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"}>
                      {v.approved ? "Revoke" : "Approve"}
                    </Button>
                  )}
                </div>
              </div>
            ))}
            {vendors.length === 0 && <div className="text-neutral-500 text-sm text-center py-12">No vendors registered.</div>}
          </TabsContent>

          <TabsContent value="listings" className="mt-6 space-y-2">
            {listings.map((l) => (
              <div key={l.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {l.images?.[0] && <img src={l.images[0]} alt="" className="w-14 h-14 object-cover rounded-sm" />}
                  <div>
                    <div className="font-semibold">{l.title} <span className="text-[10px] font-mono uppercase text-neutral-500 ml-2">{l.vendor_type}</span></div>
                    <div className="text-xs font-mono text-neutral-500 uppercase">{l.city} · {fmtPrice(l.price, l.currency)} {l.price_unit}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${l.approved ? "text-[#84CC16] border-[#84CC16]/40" : "text-amber-400 border-amber-500/40"}`}>{l.approved ? "LIVE" : "PENDING"}</span>
                  {hasPermission("manage_listings") && (
                    <Button size="sm" data-testid={`pa-approve-listing-${l.id}`} onClick={async () => { await api.patch(`/admin/listings/${l.id}/approve`, { approved: !l.approved }); load(); toast.success(l.approved ? "Hidden" : "Approved"); }}
                      className={l.approved ? "bg-white/10 hover:bg-white/20 text-white rounded-sm" : "bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"}>
                      {l.approved ? "Unpublish" : "Approve"}
                    </Button>
                  )}
                </div>
              </div>
            ))}
            {listings.length === 0 && <div className="text-neutral-500 text-sm text-center py-12">No listings yet.</div>}
          </TabsContent>

          <TabsContent value="settings" className="mt-6">
            <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3">
              <div className="font-display tracking-wider text-2xl">SITE SETTINGS</div>
              <p className="text-xs text-neutral-500 font-mono">Social media links shown in footer.</p>
              {["facebook_url", "instagram_url", "linkedin_url", "twitter_url", "youtube_url"].map((k) => (
                <div key={k}>
                  <Label className="text-xs font-mono uppercase text-neutral-500">{k.replace("_url", "")}</Label>
                  <Input data-testid={`setting-${k}`} value={settings[k] || ""} onChange={(e) => setSettings({ ...settings, [k]: e.target.value })} placeholder={`https://${k.split("_")[0]}.com/playsphere`} className="mt-2 bg-black/40 border-white/10 text-white" />
                </div>
              ))}
              <Button data-testid="settings-save" onClick={async () => { await api.patch("/settings", settings); toast.success("Saved"); load(); }} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save settings</Button>
            </div>

            <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3 mt-6">
              <div className="font-display tracking-wider text-2xl">CONTACT DETAILS</div>
              <p className="text-xs text-neutral-500 font-mono">Shown on /contact and used as the default email for contact-form deliveries.</p>
              {[
                { k: "contact_email", label: "Email", placeholder: "contact@kreedanation.com" },
                { k: "contact_phone", label: "Phone", placeholder: "+91 ..." },
                { k: "contact_address", label: "Address", placeholder: "Office address", multiline: true },
                { k: "contact_hours", label: "Hours", placeholder: "Mon–Sat · 09:00 – 19:00 IST" },
                { k: "contact_map_url", label: "Google Maps embed URL", placeholder: "https://www.google.com/maps/embed?…" },
              ].map((f) => (
                <div key={f.k}>
                  <Label className="text-xs font-mono uppercase text-neutral-500">{f.label}</Label>
                  {f.multiline ? (
                    <Textarea data-testid={`setting-${f.k}`} rows={2} value={settings[f.k] || ""} onChange={(e) => setSettings({ ...settings, [f.k]: e.target.value })} placeholder={f.placeholder} className="mt-2 bg-black/40 border-white/10 text-white" />
                  ) : (
                    <Input data-testid={`setting-${f.k}`} value={settings[f.k] || ""} onChange={(e) => setSettings({ ...settings, [f.k]: e.target.value })} placeholder={f.placeholder} className="mt-2 bg-black/40 border-white/10 text-white" />
                  )}
                </div>
              ))}
              <Button data-testid="contact-save" onClick={async () => { await api.patch("/settings", settings); toast.success("Saved"); load(); }} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save contact details</Button>
            </div>

            <ContactInbox />
          </TabsContent>

          <TabsContent value="reviews" className="mt-6">
            <div className="border border-white/10 rounded-sm bg-[#141414] p-6">
              <div className="font-display tracking-wider text-2xl">REVIEW MODERATION QUEUE</div>
              <p className="text-xs text-neutral-400 mt-1">Vendor-approved reviews awaiting final publish, plus flagged items.</p>
              <div className="mt-5"><AdminReviewsQueue /></div>
            </div>
          </TabsContent>

          <TabsContent value="accounts" className="mt-6">
            <AccountsManager />
          </TabsContent>

          <TabsContent value="about" className="mt-6">
            <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-3xl space-y-3">
              <div className="font-display tracking-wider text-2xl">ABOUT PAGE CONTENT</div>
              <p className="text-xs text-neutral-500 font-mono">
                Press <kbd className="px-1 py-0.5 bg-black/40 border border-white/10 rounded-sm">Enter</kbd> for a line break and a blank line for a new paragraph — both are preserved on /about.
              </p>
              <Label className="text-xs font-mono uppercase text-neutral-500">Company description</Label>
              <Textarea data-testid="about-desc" rows={6} value={about.company_description} onChange={(e) => setAbout({ ...about, company_description: e.target.value })} className="bg-black/40 border-white/10 text-white" />
              <Label className="text-xs font-mono uppercase text-neutral-500">Mission</Label>
              <Textarea data-testid="about-mission" rows={4} value={about.mission} onChange={(e) => setAbout({ ...about, mission: e.target.value })} className="bg-black/40 border-white/10 text-white" />
              <Label className="text-xs font-mono uppercase text-neutral-500">Vision</Label>
              <Textarea data-testid="about-vision" rows={4} value={about.vision} onChange={(e) => setAbout({ ...about, vision: e.target.value })} className="bg-black/40 border-white/10 text-white" />

              <PeopleEditor label="Founders" testid="founders" people={about.founders || []} onChange={(p) => setAbout({ ...about, founders: p })} />
              <PeopleEditor label="Directors" testid="directors" people={about.directors || []} onChange={(p) => setAbout({ ...about, directors: p })} />

              <Button data-testid="about-save" onClick={async () => { await api.patch("/about", about); toast.success("About page updated"); load(); }} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save About page</Button>
            </div>
          </TabsContent>

          {isSuperAdmin && (
            <TabsContent value="team" className="mt-6">
              <AdminTeam />
            </TabsContent>
          )}
        </Tabs>
      </div>

      {editing && <ServiceEditor service={editing} setService={setEditing} onSave={saveService} onClose={() => setEditing(null)} />}

      <Footer />
    </div>
  );
}

function ServiceEditor({ service, setService, onSave, onClose }) {
  const upd = (patch) => setService({ ...service, ...patch });
  const addField = () => upd({ config_fields: [...(service.config_fields || []), { key: "", label: "", type: "number", required: false }] });
  const updField = (i, patch) => { const next = [...service.config_fields]; next[i] = { ...next[i], ...patch }; upd({ config_fields: next }); };
  const delField = (i) => upd({ config_fields: service.config_fields.filter((_, idx) => idx !== i) });
  const addVariant = () => upd({ variants: [...(service.variants || []), { id: `v-${Date.now()}`, name: "", image_url: "", extra_price: 0 }] });
  const updVariant = (i, patch) => { const next = [...service.variants]; next[i] = { ...next[i], ...patch }; upd({ variants: next }); };
  const delVariant = (i) => upd({ variants: service.variants.filter((_, idx) => idx !== i) });

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6">
      <div className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-3xl my-10 p-6 space-y-4 text-white">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-mono text-[10px] uppercase text-[#84CC16] tracking-widest">/ {service.id ? "Edit" : "New"} service</div>
            <h2 className="font-display text-3xl tracking-wider">{service.id ? service.name.toUpperCase() : "NEW SERVICE"}</h2>
          </div>
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Close</Button>
        </div>

        <div className="grid md:grid-cols-2 gap-3">
          <Field label="Name *"><Input data-testid="svc-name" value={service.name} onChange={(e) => upd({ name: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
          <Field label="Category">
            <Select value={service.category} onValueChange={(v) => upd({ category: v })}>
              <SelectTrigger data-testid="svc-category" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Currency">
            <Select value={service.currency || "USD"} onValueChange={(v) => upd({ currency: v })}>
              <SelectTrigger data-testid="svc-currency" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {CURRENCIES.map((c) => <SelectItem key={c.code} value={c.code}>{c.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field label={`Base price (${service.currency || "USD"})`}><Input data-testid="svc-price" type="number" min={0} value={service.base_price} onChange={(e) => upd({ base_price: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
          <Field label="Price unit"><Input data-testid="svc-unit" value={service.price_unit} onChange={(e) => upd({ price_unit: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
        </div>
        <Field label="Description"><Textarea data-testid="svc-desc" value={service.description} onChange={(e) => upd({ description: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
        <Field label="Main image">
          <ImageUpload value={service.images?.[0] || ""} onChange={(v) => upd({ images: [v] })} testid="svc-image" placeholder="https://… or upload image" />
        </Field>

        <div className="flex items-center gap-3">
          <input id="svc-allow-text" type="checkbox" checked={!!service.allow_custom_text} onChange={(e) => upd({ allow_custom_text: e.target.checked })} className="accent-[#84CC16]" />
          <label htmlFor="svc-allow-text" className="text-sm">Allow custom text input (e.g., trophy inscription)</label>
        </div>
        {service.allow_custom_text && (
          <Field label="Custom text label">
            <Input value={service.custom_text_label || ""} onChange={(e) => upd({ custom_text_label: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          </Field>
        )}

        <div className="flex items-center gap-3">
          <input id="svc-active" type="checkbox" checked={!!service.active} onChange={(e) => upd({ active: e.target.checked })} className="accent-[#84CC16]" />
          <label htmlFor="svc-active" className="text-sm">Active (visible in marketplace)</label>
        </div>

        {/* Config fields */}
        <div className="border border-white/10 rounded-sm p-4">
          <div className="flex items-center justify-between">
            <div className="font-mono text-[10px] uppercase text-neutral-500">/ Form fields shown to HR</div>
            <Button size="sm" variant="ghost" onClick={addField} className="text-[#84CC16]" data-testid="svc-add-field">+ Add field</Button>
          </div>
          <div className="space-y-2 mt-3">
            {(service.config_fields || []).map((f, i) => (
              <div key={`field-${f.key || "new"}-${i}`} className="grid grid-cols-12 gap-2 items-center">
                <Input placeholder="key" value={f.key} onChange={(e) => updField(i, { key: e.target.value })} className="col-span-3 bg-black/40 border-white/10 text-white" />
                <Input placeholder="Label" value={f.label} onChange={(e) => updField(i, { label: e.target.value })} className="col-span-4 bg-black/40 border-white/10 text-white" />
                <Select value={f.type} onValueChange={(v) => updField(i, { type: v })}>
                  <SelectTrigger className="col-span-2 bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    {["number", "text", "textarea", "select"].map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Input placeholder={f.type === "select" ? "opt1,opt2" : "default"} value={f.type === "select" ? (f.options || []).join(",") : (f.default || "")} onChange={(e) => updField(i, f.type === "select" ? { options: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) } : { default: e.target.value })} className="col-span-2 bg-black/40 border-white/10 text-white" />
                <Button size="sm" variant="ghost" onClick={() => delField(i)} className="col-span-1 text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
              </div>
            ))}
          </div>
        </div>

        {/* Variants */}
        <div className="border border-white/10 rounded-sm p-4">
          <div className="flex items-center justify-between">
            <div className="font-mono text-[10px] uppercase text-neutral-500">/ Variants (e.g., trophy designs)</div>
            <Button size="sm" variant="ghost" onClick={addVariant} className="text-[#84CC16]" data-testid="svc-add-variant">+ Add variant</Button>
          </div>
          <div className="space-y-2 mt-3">
            {(service.variants || []).map((v, i) => (
              <div key={`variant-${v.name || "new"}-${i}`} className="grid grid-cols-12 gap-2 items-center">
                <Input placeholder="Name" value={v.name} onChange={(e) => updVariant(i, { name: e.target.value })} className="col-span-3 bg-black/40 border-white/10 text-white" />
                <Input placeholder="Image URL" value={v.image_url} onChange={(e) => updVariant(i, { image_url: e.target.value })} className="col-span-6 bg-black/40 border-white/10 text-white" />
                <Input placeholder="±price" type="number" value={v.extra_price} onChange={(e) => updVariant(i, { extra_price: Number(e.target.value) || 0 })} className="col-span-2 bg-black/40 border-white/10 text-white" />
                <Button size="sm" variant="ghost" onClick={() => delVariant(i)} className="col-span-1 text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Cancel</Button>
          <Button data-testid="svc-save" onClick={onSave} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save service</Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <Label className="text-xs font-mono uppercase text-neutral-500">{label}</Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function PeopleEditor({ label, testid, people, onChange }) {
  const add = () => onChange([...people, { name: "", role: "", image_url: "", bio: "", linkedin_url: "", twitter_url: "" }]);
  const upd = (i, patch) => { const next = [...people]; next[i] = { ...next[i], ...patch }; onChange(next); };
  const del = (i) => onChange(people.filter((_, idx) => idx !== i));
  return (
    <div className="border border-white/10 rounded-sm p-3 mt-3">
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ {label} ({people.length})</div>
        <Button size="sm" variant="ghost" onClick={add} className="text-[#84CC16]" data-testid={`${testid}-add`}>+ Add</Button>
      </div>
      <div className="space-y-2 mt-2">
        {people.map((p, i) => (
          <div key={`person-${p.name || "new"}-${i}`} className="grid grid-cols-12 gap-2 items-center">
            <Input data-testid={`${testid}-${i}-name`} placeholder="Name" value={p.name} onChange={(e) => upd(i, { name: e.target.value })} className="col-span-3 bg-black/40 border-white/10 text-white" />
            <Input data-testid={`${testid}-${i}-role`} placeholder="Role" value={p.role} onChange={(e) => upd(i, { role: e.target.value })} className="col-span-3 bg-black/40 border-white/10 text-white" />
            <div className="col-span-4"><ImageUpload value={p.image_url} onChange={(v) => upd(i, { image_url: v })} testid={`${testid}-${i}-image`} placeholder="Image — paste URL or upload" /></div>
            <Input placeholder="LinkedIn" value={p.linkedin_url || ""} onChange={(e) => upd(i, { linkedin_url: e.target.value })} className="col-span-1 bg-black/40 border-white/10 text-white" />
            <Button size="sm" variant="ghost" onClick={() => del(i)} className="col-span-1 text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
            <Textarea data-testid={`${testid}-${i}-bio`} rows={1} placeholder="Bio" value={p.bio || ""} onChange={(e) => upd(i, { bio: e.target.value })} className="col-span-12 bg-black/40 border-white/10 text-white" />
          </div>
        ))}
      </div>
    </div>
  );
}

function ContactInbox() {
  const [items, setItems] = useState([]);
  const load = () => api.get("/contact-messages").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const markRead = async (id) => { await api.patch(`/contact-messages/${id}`, { read: true }); load(); };
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3 mt-6">
      <div className="font-display tracking-wider text-2xl">CONTACT INBOX ({items.filter((x) => !x.read).length} unread)</div>
      {items.length === 0 && <div className="text-xs text-neutral-500">No messages yet.</div>}
      <div className="space-y-2 max-h-[480px] overflow-auto">
        {items.map((m) => (
          <div key={m.id} data-testid={`contact-msg-${m.id}`} className={`border border-white/10 rounded-sm p-3 ${m.read ? "bg-black/20" : "bg-black/40"}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold">{m.name} <span className="text-[10px] font-mono text-neutral-500">{m.email}</span></div>
                <div className="text-[10px] font-mono text-neutral-600">{new Date(m.created_at).toLocaleString()} · phone: {m.phone || "—"}</div>
              </div>
              {!m.read && <Button size="sm" variant="ghost" onClick={() => markRead(m.id)} className="text-[#84CC16] text-xs">Mark read</Button>}
            </div>
            <div className="text-sm text-neutral-300 mt-2 whitespace-pre-wrap">{m.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
}


const ROLE_TABS = [
  { value: "organiser", label: "Organisers" },
  { value: "company_admin", label: "Company admins" },
  { value: "vendor", label: "Vendors" },
  { value: "player", label: "Players" },
];

function AccountsManager() {
  const [role, setRole] = useState("organiser");
  const [users, setUsers] = useState([]);
  const [showDisabled, setShowDisabled] = useState(true);
  const [q, setQ] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = (r = role) => api.get(`/admin/users?role=${r}`).then((res) => setUsers(res.data)).catch((e) => toast.error(e.response?.data?.detail || "Failed to load accounts"));
  useEffect(() => { load(role); }, [role]);

  const toggleDisabled = async (u) => {
    const next = !u.disabled;
    const verb = next ? "disable" : "enable";
    if (!window.confirm(`Are you sure you want to ${verb} ${u.email}?${next ? "\nThey will no longer be able to log in." : ""}`)) return;
    try {
      setBusyId(u.id);
      await api.patch(`/admin/users/${u.id}/disabled`, { disabled: next });
      toast.success(next ? "Account disabled" : "Account enabled");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally {
      setBusyId(null);
    }
  };

  const filtered = users.filter((u) => {
    if (!showDisabled && u.disabled) return false;
    if (!q.trim()) return true;
    const hay = `${u.email} ${u.name || ""} ${u.company_name || ""} ${u.vendor_business_name || ""}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  const counts = users.reduce((acc, u) => { acc.total++; if (u.disabled) acc.disabled++; return acc; }, { total: 0, disabled: 0 });

  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-6">
      <div className="font-display tracking-wider text-2xl">ACCOUNT SUSPENSION</div>
      <p className="text-xs text-neutral-400 mt-1">
        Disable any organiser, vendor, player, or company admin from logging in. Their data stays intact — they just see a contact-admin message at login until re-enabled.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        {ROLE_TABS.map((t) => (
          <Button
            key={t.value}
            data-testid={`accounts-role-${t.value}`}
            size="sm"
            onClick={() => setRole(t.value)}
            className={role === t.value ? "bg-[#FF3B30] hover:bg-[#dc2626] text-white rounded-sm" : "bg-white/5 hover:bg-white/10 text-white rounded-sm"}
          >
            {t.label}
          </Button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <Input
            data-testid="accounts-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search email, name, company…"
            className="bg-black/40 border-white/10 text-white text-sm w-64"
          />
          <label className="text-xs font-mono text-neutral-400 flex items-center gap-2">
            <input type="checkbox" data-testid="accounts-show-disabled" checked={showDisabled} onChange={(e) => setShowDisabled(e.target.checked)} className="accent-[#84CC16]" />
            Show disabled
          </label>
        </div>
      </div>

      <div className="text-[10px] font-mono uppercase text-neutral-500 mt-4">
        / {counts.total} total · {counts.disabled} disabled · showing {filtered.length}
      </div>

      <div className="mt-3 space-y-2">
        {filtered.length === 0 && <div className="text-neutral-500 text-sm text-center py-12 border border-dashed border-white/10 rounded-sm">No matching accounts.</div>}
        {filtered.map((u) => (
          <div
            key={u.id}
            data-testid={`account-row-${u.id}`}
            className={`border rounded-sm p-4 flex items-center justify-between gap-3 ${u.disabled ? "border-amber-500/30 bg-amber-500/5" : "border-white/10 bg-black/30"}`}
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="font-semibold truncate">{u.name || u.email}</div>
                {u.disabled && <span className="text-[10px] uppercase font-mono text-amber-400 border border-amber-500/40 rounded-sm px-1.5 py-0.5">DISABLED</span>}
                {u.role === "organiser" && <span className="text-[10px] uppercase font-mono text-[#06B6D4] border border-[#06B6D4]/40 rounded-sm px-1.5 py-0.5">ORGANISER</span>}
                {u.role === "company_admin" && <span className="text-[10px] uppercase font-mono text-[#84CC16] border border-[#84CC16]/40 rounded-sm px-1.5 py-0.5">COMPANY</span>}
                {u.role === "vendor" && <span className="text-[10px] uppercase font-mono text-[#EC4899] border border-[#EC4899]/40 rounded-sm px-1.5 py-0.5">VENDOR{u.vendor_approved ? "" : " · PENDING"}</span>}
                {u.role === "player" && <span className="text-[10px] uppercase font-mono text-[#FBBF24] border border-[#FBBF24]/40 rounded-sm px-1.5 py-0.5">PLAYER</span>}
              </div>
              <div className="text-xs font-mono text-neutral-500 mt-1 truncate">
                {u.email}
                {u.company_name && <> · {u.company_name}</>}
                {u.vendor_business_name && <> · {u.vendor_business_name} ({u.vendor_type})</>}
              </div>
              {u.disabled && u.disabled_at && (
                <div className="text-[10px] font-mono text-amber-300/80 mt-1">
                  disabled {new Date(u.disabled_at).toLocaleString()}{u.disabled_by ? ` by ${u.disabled_by}` : ""}
                </div>
              )}
            </div>
            <Button
              size="sm"
              data-testid={`account-toggle-${u.id}`}
              disabled={busyId === u.id}
              onClick={() => toggleDisabled(u)}
              className={u.disabled ? "bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm" : "bg-[#FF3B30] hover:bg-[#dc2626] text-white font-semibold rounded-sm"}
            >
              {busyId === u.id ? "…" : (u.disabled ? "Enable" : "Disable")}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
