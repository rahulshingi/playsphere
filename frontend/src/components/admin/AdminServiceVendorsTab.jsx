import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2, Edit3, Save, X, Star, MapPin, Receipt } from "lucide-react";

/**
 * AdminServiceVendorsTab — Internal Service Vendor Management.
 *
 * STRICT boundary vs. Venue Vendors:
 *   • This module has ZERO relationship with the existing /vendors table.
 *   • Service vendors have NO login and are never surfaced to HR.
 *   • Only used by admins on the RFQ workflow to compute internal cost.
 *
 * Two panels:
 *   1. Vendor ledger — add / edit / activate vendors with contact + city/state
 *      + preferred flag + services they cover.
 *   2. Rate cards — per (vendor, service) tuple, admin captures the internal
 *      unit rate + unit type. Auto-suggest engine ranks these on RFQ view.
 */
export default function AdminServiceVendorsTab() {
  const [vendors, setVendors] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);   // vendor being edited (or blank for new)
  const [ratesFor, setRatesFor] = useState(null); // vendor whose rate card is open
  const [q, setQ] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [v, s] = await Promise.all([
        api.get("/admin/service-vendors?include_inactive=true"),
        api.get("/corporate-services/services?include_inactive=true"),
      ]);
      setVendors(v.data || []);
      setServices(s.data || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return vendors;
    return vendors.filter((v) => (
      v.name?.toLowerCase().includes(needle) ||
      v.city?.toLowerCase().includes(needle) ||
      v.state?.toLowerCase().includes(needle) ||
      v.contact_person?.toLowerCase().includes(needle)
    ));
  }, [vendors, q]);

  const blank = {
    name: "", contact_person: "", contact_email: "", contact_phone: "",
    city: "", state: "", gst_number: "", address: "", notes: "",
    service_ids: [], preferred: false, active: true,
  };

  const save = async () => {
    if (!editing?.name) return toast.error("Vendor name required");
    try {
      if (editing.id) await api.patch(`/admin/service-vendors/${editing.id}`, editing);
      else await api.post("/admin/service-vendors", editing);
      toast.success("Saved"); setEditing(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this vendor? Rate cards will also be removed.")) return;
    try { await api.delete(`/admin/service-vendors/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div data-testid="admin-service-vendors" className="space-y-6">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#F59E0B]">/ Corporate Services · Internal Vendors</div>
        <h2 className="text-2xl font-display tracking-wide mt-1">Service Vendor Ledger</h2>
        <p className="text-sm text-neutral-500 mt-1 max-w-3xl">
          Internal-only procurement contacts. Map each vendor to the services they cover, capture per-service rate cards, and mark preferred partners.
          HR / Organisers <b>never</b> see this — it feeds the RFQ cost-sheet auto-suggest engine.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <Input
          data-testid="sv-search"
          value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search name / city / state / contact"
          className="max-w-sm bg-black/40 border-white/10 text-white"
        />
        <div className="text-[10px] font-mono uppercase text-neutral-500">/ {filtered.length} of {vendors.length}</div>
        <div className="ml-auto">
          <Button data-testid="sv-new" size="sm" onClick={() => setEditing({ ...blank })}
            className="bg-[#F59E0B] hover:bg-[#D97706] text-black rounded-sm">
            <Plus className="w-3 h-3 mr-1" /> New vendor
          </Button>
        </div>
      </div>

      {loading ? <div className="text-neutral-500 text-sm">Loading…</div> : (
        <div className="border border-white/10 rounded-sm bg-[#0f0f0f] overflow-hidden">
          {filtered.length === 0 && (
            <div className="text-neutral-500 text-sm p-8 text-center">
              {vendors.length === 0 ? "No service vendors yet." : "No matches."}
            </div>
          )}
          {filtered.map((v) => (
            <div key={v.id} data-testid={`sv-row-${v.id}`} className="border-b border-white/5 px-4 py-3 hover:bg-white/[0.02]">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-white font-semibold">{v.name}</span>
                    {v.preferred && (
                      <span className="inline-flex items-center gap-1 text-[9px] font-mono uppercase text-[#FACC15] border border-[#FACC15]/40 rounded px-1">
                        <Star className="w-2.5 h-2.5" /> preferred
                      </span>
                    )}
                    {!v.active && <span className="text-[9px] font-mono uppercase text-neutral-500 border border-white/10 rounded px-1">inactive</span>}
                  </div>
                  <div className="text-[10px] font-mono text-neutral-500 mt-1 flex items-center gap-3 flex-wrap">
                    {(v.city || v.state) && (
                      <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> {[v.city, v.state].filter(Boolean).join(", ")}</span>
                    )}
                    <span>{v.contact_person || "—"}</span>
                    <span>{v.contact_email || v.contact_phone || "—"}</span>
                    <span>{v.service_ids?.length || 0} services · {v.rate_count || 0} rates</span>
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button size="sm" variant="ghost" data-testid={`sv-rates-${v.id}`}
                    onClick={() => setRatesFor(v)} className="text-[#06B6D4]">
                    <Receipt className="w-3.5 h-3.5 mr-1" /> Rates
                  </Button>
                  <Button size="sm" variant="ghost" data-testid={`sv-edit-${v.id}`}
                    onClick={() => setEditing({ ...v })} className="text-[#84CC16]">
                    <Edit3 className="w-3.5 h-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" data-testid={`sv-del-${v.id}`}
                    onClick={() => remove(v.id)} className="text-[#FF3B30]">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <VendorEditor
          value={editing} setValue={setEditing}
          services={services}
          onSave={save} onCancel={() => setEditing(null)}
        />
      )}

      {ratesFor && (
        <RateCardEditor
          vendor={ratesFor}
          services={services}
          onClose={() => { setRatesFor(null); load(); }}
        />
      )}
    </div>
  );
}

// ─────────────── Editor ───────────────
function VendorEditor({ value, setValue, services, onSave, onCancel }) {
  const toggleSvc = (id) => {
    const has = value.service_ids?.includes(id);
    setValue({ ...value, service_ids: has ? value.service_ids.filter((x) => x !== id) : [...(value.service_ids || []), id] });
  };
  return (
    <div className="border border-[#F59E0B]/30 bg-[#141414] rounded-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#F59E0B]">{value.id ? "Edit vendor" : "New vendor"}</div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={onCancel} className="text-neutral-400"><X className="w-3.5 h-3.5 mr-1" /> Cancel</Button>
          <Button size="sm" data-testid="sv-save" onClick={onSave} className="bg-[#84CC16] hover:bg-[#65A30D] text-black"><Save className="w-3.5 h-3.5 mr-1" /> Save</Button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        <F label="Vendor name">
          <Input data-testid="sv-name" value={value.name} onChange={(e) => setValue({ ...value, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </F>
        <F label="Contact person">
          <Input value={value.contact_person} onChange={(e) => setValue({ ...value, contact_person: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </F>
        <F label="Contact email">
          <Input type="email" value={value.contact_email} onChange={(e) => setValue({ ...value, contact_email: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </F>
        <F label="Contact phone">
          <Input value={value.contact_phone} onChange={(e) => setValue({ ...value, contact_phone: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </F>
        <F label="City">
          <Input data-testid="sv-city" value={value.city} onChange={(e) => setValue({ ...value, city: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </F>
        <F label="State">
          <Input value={value.state} onChange={(e) => setValue({ ...value, state: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </F>
        <F label="GSTIN">
          <Input value={value.gst_number} onChange={(e) => setValue({ ...value, gst_number: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </F>
        <F label="Address">
          <Input value={value.address} onChange={(e) => setValue({ ...value, address: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </F>
      </div>

      <F label="Internal notes">
        <Textarea rows={2} value={value.notes} onChange={(e) => setValue({ ...value, notes: e.target.value })} className="bg-black/40 border-white/10 text-white text-sm" />
      </F>

      <div>
        <Label className="text-[10px] font-mono uppercase text-neutral-500">Services covered ({value.service_ids?.length || 0})</Label>
        <div className="mt-2 max-h-[200px] overflow-auto border border-white/10 rounded-sm bg-black/40 p-2 grid grid-cols-2 gap-1">
          {services.filter((s) => s.active).map((s) => {
            const on = value.service_ids?.includes(s.id);
            return (
              <button key={s.id} type="button" data-testid={`sv-svc-toggle-${s.id}`}
                onClick={() => toggleSvc(s.id)}
                className={`text-left px-2 py-1 rounded-sm text-xs ${on ? "bg-[#84CC16]/15 text-[#84CC16]" : "text-neutral-400 hover:bg-white/5"}`}>
                {on ? "✓ " : ""} {s.name}
              </button>
            );
          })}
          {services.length === 0 && <div className="text-neutral-500 text-xs">Add services first in Corporate Services → Services tab.</div>}
        </div>
      </div>

      <div className="flex gap-6">
        <label className="inline-flex items-center gap-2 text-sm text-neutral-300 cursor-pointer">
          <input data-testid="sv-preferred" type="checkbox" checked={!!value.preferred} onChange={(e) => setValue({ ...value, preferred: e.target.checked })} className="accent-[#FACC15]" />
          Preferred vendor
        </label>
        <label className="inline-flex items-center gap-2 text-sm text-neutral-300 cursor-pointer">
          <input type="checkbox" checked={!!value.active} onChange={(e) => setValue({ ...value, active: e.target.checked })} className="accent-[#84CC16]" />
          Active
        </label>
      </div>
    </div>
  );
}

// ─────────────── Rate Cards ───────────────
function RateCardEditor({ vendor, services, onClose }) {
  const [rates, setRates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState({ service_id: "", rate: 0, unit_type: "per event", min_quantity: 1, notes: "" });

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/admin/service-vendors/${vendor.id}/rates`);
      setRates(r.data || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [vendor.id]); // eslint-disable-line

  const UNITS = ["per event", "per person", "per team", "per match", "per hour", "per day"];

  const upsert = async () => {
    if (!draft.service_id) return toast.error("Pick a service");
    if (!draft.rate || draft.rate <= 0) return toast.error("Rate must be > 0");
    try {
      await api.post(`/admin/service-vendors/${vendor.id}/rates`, draft);
      toast.success("Rate saved"); setDraft({ ...draft, rate: 0, notes: "" }); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  const remove = async (rid) => {
    if (!window.confirm("Remove this rate?")) return;
    await api.delete(`/admin/service-vendors/${vendor.id}/rates/${rid}`);
    load();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-3xl max-h-[85vh] overflow-auto bg-[#0f0f0f] border border-[#06B6D4]/40 rounded-sm p-6">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4]">/ Rate Card · {vendor.name}</div>
            <div className="text-neutral-500 text-xs mt-1">{[vendor.city, vendor.state].filter(Boolean).join(", ") || "—"}</div>
          </div>
          <Button size="sm" variant="ghost" data-testid="sv-rates-close" onClick={onClose} className="text-neutral-400"><X className="w-4 h-4" /></Button>
        </div>

        <div className="border border-white/10 rounded-sm bg-black/40 p-4 space-y-3">
          <div className="font-mono text-[10px] uppercase text-neutral-500">/ Add / update rate</div>
          <div className="grid md:grid-cols-5 gap-2">
            <div className="md:col-span-2">
              <Select value={draft.service_id} onValueChange={(v) => setDraft({ ...draft, service_id: v })}>
                <SelectTrigger data-testid="sv-rate-service" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Service" /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  {services.filter((s) => s.active).map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Input data-testid="sv-rate-amt" type="number" min="0" step="0.01" value={draft.rate} onChange={(e) => setDraft({ ...draft, rate: Number(e.target.value) || 0 })} placeholder="Rate ₹" className="bg-black/40 border-white/10 text-white" />
            <Select value={draft.unit_type} onValueChange={(v) => setDraft({ ...draft, unit_type: v })}>
              <SelectTrigger className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {UNITS.map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button data-testid="sv-rate-save" onClick={upsert} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black">Save rate</Button>
          </div>
          <Input value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} placeholder="Notes (optional)" className="bg-black/40 border-white/10 text-white text-sm" />
        </div>

        <div className="mt-4">
          <div className="font-mono text-[10px] uppercase text-neutral-500 mb-2">/ {rates.length} rates on file</div>
          {loading ? <div className="text-neutral-500 text-sm">Loading…</div> : (
            <div className="border border-white/10 rounded-sm">
              {rates.length === 0 && <div className="text-neutral-500 text-sm p-6 text-center">No rates yet. Add the first one above.</div>}
              {rates.map((r) => (
                <div key={r.id} data-testid={`sv-rate-row-${r.id}`} className="flex items-center justify-between px-3 py-2 border-b border-white/5">
                  <div>
                    <div className="text-white text-sm">{r.service_name}</div>
                    <div className="text-[10px] font-mono text-neutral-500">
                      ₹ {r.rate.toFixed(2)} · {r.unit_type} · min qty {r.min_quantity}
                    </div>
                    {r.notes && <div className="text-[10px] text-neutral-500 italic mt-0.5">{r.notes}</div>}
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => remove(r.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function F({ label, children }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase text-neutral-500">{label}</Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
