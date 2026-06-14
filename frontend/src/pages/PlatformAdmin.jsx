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

const CATEGORIES = ["streaming", "apparel", "merchandise", "awards", "venue", "equipment", "training", "other"];

export default function PlatformAdmin() {
  const { ready, isPlatformAdmin } = useAuth();
  const nav = useNavigate();
  const [services, setServices] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [listings, setListings] = useState([]);
  const [settings, setSettings] = useState({});
  const [editing, setEditing] = useState(null);

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
    api.get("/bookings"),
    api.get("/vendors"),
    api.get("/admin/listings"),
    api.get("/settings"),
  ]).then(([s, c, b, v, l, st]) => {
    setServices(s.data); setCompanies(c.data); setBookings(b.data);
    setVendors(v.data); setListings(l.data); setSettings(st.data);
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

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FF3B30]">/ PlaySphere HQ</div>
        <div className="flex items-end justify-between">
          <h1 className="font-display text-6xl tracking-wide mt-3">PLATFORM ADMIN</h1>
          <Button data-testid="platform-new-service" onClick={() => setEditing(blankService)} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
            <Plus className="w-4 h-4 mr-1" /> New service
          </Button>
        </div>

        <Tabs defaultValue="services" className="mt-10">
          <TabsList className="bg-[#141414] border border-white/10 rounded-sm flex-wrap">
            <TabsTrigger value="services" data-testid="pa-tab-services" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Services ({services.length})</TabsTrigger>
            <TabsTrigger value="companies" data-testid="pa-tab-companies" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Companies ({companies.length})</TabsTrigger>
            <TabsTrigger value="bookings" data-testid="pa-tab-bookings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Bookings ({bookings.length})</TabsTrigger>
            <TabsTrigger value="vendors" data-testid="pa-tab-vendors" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Vendors ({vendors.length})</TabsTrigger>
            <TabsTrigger value="listings" data-testid="pa-tab-listings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Listings ({listings.length})</TabsTrigger>
            <TabsTrigger value="settings" data-testid="pa-tab-settings" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Settings</TabsTrigger>
          </TabsList>

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
                  <Button size="sm" variant="ghost" data-testid={`pa-edit-${s.id}`} onClick={() => setEditing({ ...s, images: s.images?.length ? s.images : [""] })} className="text-[#84CC16]">Edit</Button>
                  <Button size="sm" variant="ghost" data-testid={`pa-delete-${s.id}`} onClick={() => deleteService(s.id)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                </div>
              </div>
            ))}
          </TabsContent>

          <TabsContent value="companies" className="mt-6 space-y-2">
            {companies.map((c) => (
              <div key={c.id} className="border border-white/10 rounded-sm p-4 bg-[#141414]">
                <div className="font-semibold">{c.name}</div>
                <div className="text-xs font-mono text-neutral-500">{c.contact_email} · {c.contact_phone || "—"} · /{c.slug}</div>
              </div>
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
              <div key={v.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between">
                <div>
                  <div className="font-semibold">{v.business_name} <span className="text-[10px] font-mono uppercase text-neutral-500 ml-2">{v.vendor_type}</span></div>
                  <div className="text-xs font-mono text-neutral-500">{v.contact_name} · {v.city} · {v.mobile} · {v.email}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${v.approved ? "text-[#84CC16] border-[#84CC16]/40" : "text-amber-400 border-amber-500/40"}`}>{v.approved ? "APPROVED" : "PENDING"}</span>
                  <Button size="sm" data-testid={`pa-approve-vendor-${v.id}`} onClick={async () => { await api.patch(`/vendors/${v.id}/approve`, { approved: !v.approved }); load(); toast.success(v.approved ? "Revoked" : "Approved"); }}
                    className={v.approved ? "bg-white/10 hover:bg-white/20 text-white rounded-sm" : "bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"}>
                    {v.approved ? "Revoke" : "Approve"}
                  </Button>
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
                  <Button size="sm" data-testid={`pa-approve-listing-${l.id}`} onClick={async () => { await api.patch(`/admin/listings/${l.id}/approve`, { approved: !l.approved }); load(); toast.success(l.approved ? "Hidden" : "Approved"); }}
                    className={l.approved ? "bg-white/10 hover:bg-white/20 text-white rounded-sm" : "bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"}>
                    {l.approved ? "Unpublish" : "Approve"}
                  </Button>
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
          </TabsContent>
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
        <Field label="Main image URL">
          <Input data-testid="svc-image" value={service.images?.[0] || ""} onChange={(e) => upd({ images: [e.target.value] })} className="bg-black/40 border-white/10 text-white" />
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
              <div key={i} className="grid grid-cols-12 gap-2 items-center">
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
              <div key={i} className="grid grid-cols-12 gap-2 items-center">
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
