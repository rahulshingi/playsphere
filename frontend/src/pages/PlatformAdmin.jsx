import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { fmtPrice } from "@/lib/currency";
import DashboardPanel from "@/components/DashboardPanel";
import SportsManager from "@/components/SportsManager";
import SponsorshipMetricsCard from "@/components/sponsorship/SponsorshipMetricsCard";
import { AdminReviewsQueue } from "@/components/Reviews";
import AdminTeam from "@/components/AdminTeam";
import ServiceEditor from "@/components/admin/ServiceEditor";
import AccountsManager from "@/components/admin/AccountsManager";
import EventsTab from "@/components/admin/EventsTab";
import PendingApprovalsTab from "@/components/admin/PendingApprovalsTab";
import UsersTab from "@/components/admin/UsersTab";
import VendorsTab from "@/components/admin/VendorsTab";
import BookingsAnalyticsTab from "@/components/admin/BookingsAnalyticsTab";
import ListingsTab from "@/components/admin/ListingsTab";
import SettingsTab from "@/components/admin/SettingsTab";
import AboutTab from "@/components/admin/AboutTab";
import BusinessTab from "@/components/admin/BusinessTab";
import AdminCommissionsTab from "@/components/admin/AdminCommissionsTab";
import AdminCorporateServicesTab from "@/components/admin/AdminCorporateServicesTab";

const BLANK_SERVICE = {
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

const ABOUT_DEFAULTS = { company_description: "", mission: "", vision: "", founders: [], directors: [] };

export default function PlatformAdmin() {
  const { ready, isPlatformAdmin, isSuperAdmin, hasPermission } = useAuth();
  const nav = useNavigate();
  // Persist the active tab in the URL so the browser's back button (and "Open in new tab")
  // restore the right view — e.g. clicking "View profile" from the Users tab and pressing
  // Back returns the admin to /platform-admin?tab=users, not the default Dashboard.
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") || "dashboard";
  const setActiveTab = (next) => {
    const sp = new URLSearchParams(searchParams);
    if (next === "dashboard") sp.delete("tab"); else sp.set("tab", next);
    setSearchParams(sp, { replace: true });
  };
  const [services, setServices] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [events, setEvents] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [listings, setListings] = useState([]);
  const [settings, setSettings] = useState({});
  const [about, setAbout] = useState(ABOUT_DEFAULTS);
  const [editing, setEditing] = useState(null);
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [businessQueueCount, setBusinessQueueCount] = useState(0);

  const load = () => Promise.all([
    api.get("/services?include_inactive=true"),
    api.get("/companies"),
    api.get("/events"),
    api.get("/bookings"),
    api.get("/vendors"),
    api.get("/admin/listings"),
    api.get("/settings"),
    api.get("/about"),
    api.get("/events/pending-approval"),
    api.get("/admin/offline-subscriptions?status=pending_payment").catch(() => ({ data: [] })),
    api.get("/admin/venue-leads?status=open").catch(() => ({ data: [] })),
  ]).then(([s, c, ev, b, v, l, st, ab, pa, os, vl]) => {
    setServices(s.data); setCompanies(c.data); setEvents(ev.data); setBookings(b.data);
    setVendors(v.data); setListings(l.data); setSettings(st.data);
    setAbout({ ...ABOUT_DEFAULTS, ...ab.data });
    setPendingApprovals(pa.data || []);
    setBusinessQueueCount((os.data?.length || 0) + (vl.data?.length || 0));
  });

  useEffect(() => {
    if (ready && !isPlatformAdmin) { nav("/login"); return; }
    if (ready) load();
  }, [ready, isPlatformAdmin]);

  const corporateCompanies = useMemo(() => companies.filter((c) => c.org_type !== "organiser"), [companies]);
  const organiserCompanies = useMemo(() => companies.filter((c) => c.org_type === "organiser"), [companies]);

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

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-[1600px] mx-auto px-6 pt-10 pb-24">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FF3B30]">/ Kreeda Nation HQ</div>
            <h1 className="font-display text-4xl tracking-wide mt-2">PLATFORM ADMIN</h1>
            <p className="text-sm text-neutral-500 mt-1">Manage services, vendors, bookings, and everything in between.</p>
          </div>
          {isSuperAdmin && (
            <Button data-testid="platform-new-service" onClick={() => setEditing(BLANK_SERVICE)} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
              <Plus className="w-4 h-4 mr-1" /> New service
            </Button>
          )}
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-8">
          <TabsList className="bg-[#141414] border border-white/10 rounded-lg flex-wrap p-1">
            <TabsTrigger value="dashboard" data-testid="pa-tab-dashboard" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Dashboard</TabsTrigger>
            <TabsTrigger value="services" data-testid="pa-tab-services" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Services ({services.length})</TabsTrigger>
            <TabsTrigger value="events" data-testid="pa-tab-events" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Events ({events.length})</TabsTrigger>
            <TabsTrigger value="approvals" data-testid="pa-tab-approvals" className={`data-[state=active]:bg-[#FACC15] data-[state=active]:text-black rounded-sm ${pendingApprovals.length > 0 ? "text-[#FACC15]" : ""}`}>Approvals ({pendingApprovals.length})</TabsTrigger>
            <TabsTrigger value="users" data-testid="pa-tab-users" className="data-[state=active]:bg-[#06B6D4] data-[state=active]:text-black rounded-sm">Users</TabsTrigger>
            <TabsTrigger value="sports" data-testid="pa-tab-sports" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Sports</TabsTrigger>
            <TabsTrigger value="companies" data-testid="pa-tab-companies" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Companies ({corporateCompanies.length})</TabsTrigger>
            <TabsTrigger value="organisers" data-testid="pa-tab-organisers" className="data-[state=active]:bg-[#06B6D4] data-[state=active]:text-black rounded-sm">Organisers ({organiserCompanies.length})</TabsTrigger>
            <TabsTrigger value="bookings" data-testid="pa-tab-bookings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Bookings ({bookings.length})</TabsTrigger>
            <TabsTrigger value="vendors" data-testid="pa-tab-vendors" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Vendors ({vendors.length})</TabsTrigger>
            <TabsTrigger value="listings" data-testid="pa-tab-listings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Listings ({listings.length})</TabsTrigger>
            <TabsTrigger value="business" data-testid="pa-tab-business" className={`data-[state=active]:bg-[#EC4899] data-[state=active]:text-white rounded-sm ${businessQueueCount > 0 ? "text-[#EC4899]" : ""}`}>Business{businessQueueCount > 0 ? ` (${businessQueueCount})` : ""}</TabsTrigger>
            <TabsTrigger value="commissions" data-testid="pa-tab-commissions" className="data-[state=active]:bg-[#F59E0B] data-[state=active]:text-black rounded-sm">Commissions</TabsTrigger>
            <TabsTrigger value="corporate-services" data-testid="pa-tab-cs" className="data-[state=active]:bg-[#06B6D4] data-[state=active]:text-black rounded-sm">Corporate Services</TabsTrigger>
            <TabsTrigger value="settings" data-testid="pa-tab-settings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Settings</TabsTrigger>
            <TabsTrigger value="about" data-testid="pa-tab-about" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">About page</TabsTrigger>
            <TabsTrigger value="reviews" data-testid="pa-tab-reviews" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Reviews</TabsTrigger>
            <TabsTrigger value="accounts" data-testid="pa-tab-accounts" className="data-[state=active]:bg-[#FF3B30] data-[state=active]:text-white rounded-sm">Accounts</TabsTrigger>
            {isSuperAdmin && (
              <TabsTrigger value="team" data-testid="pa-tab-team" className="data-[state=active]:bg-[#FF3B30] data-[state=active]:text-white rounded-sm">Team</TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="dashboard" className="mt-6"><DashboardPanel role="admin" /><SponsorshipMetricsCard /></TabsContent>
          <TabsContent value="sports" className="mt-6"><SportsManager /></TabsContent>

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
                  {isSuperAdmin && (
                    <Button size="sm" variant="ghost" data-testid={`pa-toggle-${s.id}`}
                      onClick={async () => { await api.patch(`/services/${s.id}`, { active: !s.active }); load(); }}
                      className={s.active ? "text-amber-400" : "text-[#84CC16]"}>
                      {s.active ? "Disable" : "Enable"}
                    </Button>
                  )}
                  {isSuperAdmin && <Button size="sm" variant="ghost" data-testid={`pa-edit-${s.id}`} onClick={() => setEditing({ ...s, images: s.images?.length ? s.images : [""] })} className="text-[#84CC16]">Edit</Button>}
                  {isSuperAdmin && <Button size="sm" variant="ghost" data-testid={`pa-delete-${s.id}`} onClick={() => deleteService(s.id)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>}
                </div>
              </div>
            ))}
          </TabsContent>

          <TabsContent value="events" className="mt-6">
            <EventsTab events={events} companies={companies} reload={load} canManage={hasPermission("manage_events")} />
          </TabsContent>

          <TabsContent value="approvals" className="mt-6">
            <PendingApprovalsTab pending={pendingApprovals} companies={companies} reload={load} />
          </TabsContent>

          <TabsContent value="users" className="mt-6">
            <UsersTab />
          </TabsContent>

          <TabsContent value="companies" className="mt-6 space-y-2">
            {corporateCompanies.map((c) => (
              <Link key={c.id} to={`/platform-admin/companies/${c.id}`} data-testid={`pa-company-${c.id}`}
                className="block border border-white/10 rounded-sm p-4 bg-[#141414] hover:border-[#84CC16] transition-colors">
                <div className="font-semibold">{c.name}</div>
                <div className="text-xs font-mono text-neutral-500">{c.contact_email} · {c.contact_phone || "—"} · /{c.slug}</div>
              </Link>
            ))}
            {corporateCompanies.length === 0 && (
              <div className="text-neutral-500 text-sm text-center py-12 border border-dashed border-white/10 rounded-sm">No companies registered yet.</div>
            )}
          </TabsContent>

          <TabsContent value="organisers" className="mt-6 space-y-2">
            <p className="text-xs font-mono uppercase tracking-widest text-[#06B6D4] mb-2">/ Independent tournament organisers</p>
            {organiserCompanies.map((c) => (
              <Link key={c.id} to={`/platform-admin/companies/${c.id}`} data-testid={`pa-organiser-${c.id}`}
                className="block border border-white/10 rounded-sm p-4 bg-[#141414] hover:border-[#06B6D4] transition-colors">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="font-semibold">{c.name}</div>
                  <span className="text-[10px] uppercase font-mono text-[#06B6D4] border border-[#06B6D4]/40 rounded-sm px-1.5 py-0.5">ORGANISER</span>
                </div>
                <div className="text-xs font-mono text-neutral-500 mt-1">{c.contact_email} · {c.contact_phone || "—"} · /{c.slug}</div>
              </Link>
            ))}
            {organiserCompanies.length === 0 && (
              <div className="text-neutral-500 text-sm text-center py-12 border border-dashed border-white/10 rounded-sm">No organisers registered yet.</div>
            )}
          </TabsContent>

          <TabsContent value="bookings" className="mt-6">
            <BookingsAnalyticsTab />
          </TabsContent>

          <TabsContent value="vendors" className="mt-6">
            <VendorsTab vendors={vendors} reload={load} canManage={hasPermission("manage_vendors")} />
          </TabsContent>

          <TabsContent value="listings" className="mt-6">
            <ListingsTab listings={listings} reload={load} canManage={hasPermission("manage_listings")} />
          </TabsContent>

          <TabsContent value="business" className="mt-6">
            <BusinessTab onQueueChange={load} />
          </TabsContent>

          <TabsContent value="commissions" className="mt-6">
            <AdminCommissionsTab />
          </TabsContent>

          <TabsContent value="corporate-services" className="mt-6">
            <AdminCorporateServicesTab />
          </TabsContent>

          <TabsContent value="settings" className="mt-6">
            <SettingsTab settings={settings} setSettings={setSettings} reload={load} />
          </TabsContent>

          <TabsContent value="reviews" className="mt-6">
            <div className="border border-white/10 rounded-sm bg-[#141414] p-6">
              <div className="font-display tracking-wider text-2xl">REVIEW MODERATION QUEUE</div>
              <p className="text-xs text-neutral-400 mt-1">Vendor-approved reviews awaiting final publish, plus flagged items.</p>
              <div className="mt-5"><AdminReviewsQueue /></div>
            </div>
          </TabsContent>

          <TabsContent value="accounts" className="mt-6"><AccountsManager /></TabsContent>

          <TabsContent value="about" className="mt-6">
            <AboutTab about={about} setAbout={setAbout} reload={load} />
          </TabsContent>

          {isSuperAdmin && (
            <TabsContent value="team" className="mt-6"><AdminTeam /></TabsContent>
          )}
        </Tabs>
      </div>

      {editing && <ServiceEditor service={editing} setService={setEditing} onSave={saveService} onClose={() => setEditing(null)} />}
      <Footer />
    </div>
  );
}
