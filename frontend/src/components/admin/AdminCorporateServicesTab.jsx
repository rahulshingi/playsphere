import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2, Edit3, Save, X, Package, Tag, Sparkles } from "lucide-react";
import ImageUpload from "@/components/ImageUpload";

/**
 * AdminCorporateServicesTab — admin CRUD for the RFQ-based corporate services
 * catalogue (Phase 1). Four sub-tabs mirroring the domain: Categories,
 * Services, Add-ons, Packages. No pricing anywhere — quotations arrive in
 * Phase 3 as a separate admin surface.
 */
export default function AdminCorporateServicesTab() {
  return (
    <div data-testid="admin-cs-tab" className="space-y-6">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Corporate Services</div>
        <h2 className="text-2xl font-display tracking-wide mt-1">Catalogue admin</h2>
        <p className="text-sm text-neutral-500 mt-1">Configure categories, atomic services and add-ons — then compose them into HR-facing packages. No pricing lives here; pricing is set only when you send a quotation.</p>
      </div>

      <Tabs defaultValue="packages" className="mt-4">
        <TabsList className="bg-black/40 border border-white/10 rounded-sm p-1 flex-wrap">
          <TabsTrigger data-testid="cs-tab-packages" value="packages" className="data-[state=active]:bg-[#06B6D4] data-[state=active]:text-black rounded-sm"><Package className="w-3.5 h-3.5 mr-1.5" /> Packages</TabsTrigger>
          <TabsTrigger data-testid="cs-tab-categories" value="categories" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm"><Tag className="w-3.5 h-3.5 mr-1.5" /> Categories</TabsTrigger>
          <TabsTrigger data-testid="cs-tab-services" value="services" className="data-[state=active]:bg-[#FACC15] data-[state=active]:text-black rounded-sm">Services</TabsTrigger>
          <TabsTrigger data-testid="cs-tab-addons" value="addons" className="data-[state=active]:bg-[#EC4899] data-[state=active]:text-white rounded-sm"><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Add-ons</TabsTrigger>
        </TabsList>

        <TabsContent value="packages" className="mt-4"><PackagesPanel /></TabsContent>
        <TabsContent value="categories" className="mt-4"><CategoriesPanel /></TabsContent>
        <TabsContent value="services" className="mt-4"><ServicesPanel /></TabsContent>
        <TabsContent value="addons" className="mt-4"><AddonsPanel /></TabsContent>
      </Tabs>
    </div>
  );
}

// ─────────────── Reusable CRUD helper hook ───────────────
function useCrudList(fetchPath) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const reload = () => {
    setLoading(true);
    api.get(fetchPath).then((r) => setRows(r.data || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };
  useEffect(reload, [fetchPath]);
  return { rows, loading, reload };
}

// ─────────────── Categories ───────────────
function CategoriesPanel() {
  const { rows, loading, reload } = useCrudList("/corporate-services/categories?include_inactive=true");
  const [editing, setEditing] = useState(null);
  const blank = { name: "", description: "", icon_url: "", cover_url: "", active: true, sort_order: 0 };

  const save = async () => {
    try {
      if (editing.id) await api.patch(`/admin/corporate-services/categories/${editing.id}`, editing);
      else await api.post("/admin/corporate-services/categories", editing);
      toast.success("Saved"); setEditing(null); reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this category?")) return;
    try { await api.delete(`/admin/corporate-services/categories/${id}`); toast.success("Deleted"); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <div className="text-[10px] font-mono uppercase text-neutral-500">/ Categories ({rows.length})</div>
        <Button data-testid="cs-cat-new" size="sm" onClick={() => setEditing({ ...blank })} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm"><Plus className="w-3 h-3 mr-1" /> New category</Button>
      </div>
      {loading ? <Loading /> : (
        <div className="border border-white/10 rounded-sm bg-[#0f0f0f] overflow-hidden">
          {rows.length === 0 && <Empty msg="No categories yet." />}
          {rows.map((r) => (
            <div key={r.id} data-testid={`cs-cat-row-${r.id}`} className="flex items-center justify-between px-4 py-3 border-b border-white/5">
              <div>
                <div className="text-white flex items-center gap-2">
                  {r.name}
                  {!r.active && <span className="text-[9px] font-mono uppercase text-neutral-500 border border-white/10 rounded px-1">inactive</span>}
                </div>
                <div className="text-[10px] text-neutral-500 mt-0.5">{r.description || "—"}</div>
              </div>
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" data-testid={`cs-cat-edit-${r.id}`} onClick={() => setEditing({ ...r })} className="text-[#84CC16]"><Edit3 className="w-3.5 h-3.5" /></Button>
                <Button size="sm" variant="ghost" data-testid={`cs-cat-del-${r.id}`} onClick={() => remove(r.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></Button>
              </div>
            </div>
          ))}
        </div>
      )}
      {editing && (
        <EditorCard title={editing.id ? "Edit category" : "New category"} onCancel={() => setEditing(null)} onSave={save}>
          <TextField label="Name" value={editing.name} onChange={(v) => setEditing({ ...editing, name: v })} testid="cs-cat-name" />
          <TextField label="Description" value={editing.description} onChange={(v) => setEditing({ ...editing, description: v })} textarea />
          <TextField label="Sort order" value={editing.sort_order} onChange={(v) => setEditing({ ...editing, sort_order: Number(v) || 0 })} />
          <BoolField label="Active" value={editing.active} onChange={(v) => setEditing({ ...editing, active: v })} />
        </EditorCard>
      )}
    </div>
  );
}

// ─────────────── Services (atomic inclusions) ───────────────
function ServicesPanel() {
  const { rows, loading, reload } = useCrudList("/corporate-services/services?include_inactive=true");
  const [editing, setEditing] = useState(null);
  const blank = { name: "", description: "", unit_type: "per event", active: true };
  const UNITS = ["per event", "per person", "per team", "per match", "per hour", "per day"];

  const save = async () => {
    try {
      if (editing.id) await api.patch(`/admin/corporate-services/services/${editing.id}`, editing);
      else await api.post("/admin/corporate-services/services", editing);
      toast.success("Saved"); setEditing(null); reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this service? It will also be removed from all packages.")) return;
    try { await api.delete(`/admin/corporate-services/services/${id}`); toast.success("Deleted"); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <div className="text-[10px] font-mono uppercase text-neutral-500">/ Services ({rows.length})</div>
        <Button data-testid="cs-svc-new" size="sm" onClick={() => setEditing({ ...blank })} className="bg-[#FACC15] hover:bg-[#EAB308] text-black rounded-sm"><Plus className="w-3 h-3 mr-1" /> New service</Button>
      </div>
      {loading ? <Loading /> : (
        <div className="grid md:grid-cols-2 gap-2">
          {rows.length === 0 && <Empty msg="No services defined." />}
          {rows.map((r) => (
            <div key={r.id} data-testid={`cs-svc-row-${r.id}`} className="border border-white/10 rounded-sm bg-[#0f0f0f] p-3 flex justify-between items-center">
              <div>
                <div className="text-white text-sm flex items-center gap-2">
                  {r.name}
                  <span className="text-[9px] font-mono uppercase text-[#FACC15] border border-[#FACC15]/40 rounded px-1">{r.unit_type}</span>
                  {!r.active && <span className="text-[9px] font-mono uppercase text-neutral-500 border border-white/10 rounded px-1">inactive</span>}
                </div>
                {r.description && <div className="text-[10px] text-neutral-500 mt-0.5">{r.description}</div>}
              </div>
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" data-testid={`cs-svc-edit-${r.id}`} onClick={() => setEditing({ ...r })} className="text-[#84CC16]"><Edit3 className="w-3.5 h-3.5" /></Button>
                <Button size="sm" variant="ghost" data-testid={`cs-svc-del-${r.id}`} onClick={() => remove(r.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></Button>
              </div>
            </div>
          ))}
        </div>
      )}
      {editing && (
        <EditorCard title={editing.id ? "Edit service" : "New service"} onCancel={() => setEditing(null)} onSave={save}>
          <TextField label="Name" value={editing.name} onChange={(v) => setEditing({ ...editing, name: v })} testid="cs-svc-name" />
          <TextField label="Description" value={editing.description} onChange={(v) => setEditing({ ...editing, description: v })} textarea />
          <SelectField label="Unit type" value={editing.unit_type} onChange={(v) => setEditing({ ...editing, unit_type: v })} options={UNITS} />
          <BoolField label="Active" value={editing.active} onChange={(v) => setEditing({ ...editing, active: v })} />
        </EditorCard>
      )}
    </div>
  );
}

// ─────────────── Add-ons (optional line items) ───────────────
function AddonsPanel() {
  const { rows, loading, reload } = useCrudList("/corporate-services/addons?include_inactive=true");
  const [editing, setEditing] = useState(null);
  const blank = { name: "", description: "", unit_type: "per event", custom_quantity_enabled: true, active: true };
  const UNITS = ["per event", "per person", "per team", "per match", "per hour", "per day", "per trophy"];

  const save = async () => {
    try {
      if (editing.id) await api.patch(`/admin/corporate-services/addons/${editing.id}`, editing);
      else await api.post("/admin/corporate-services/addons", editing);
      toast.success("Saved"); setEditing(null); reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this add-on? It will also be removed from all packages.")) return;
    try { await api.delete(`/admin/corporate-services/addons/${id}`); toast.success("Deleted"); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <div className="text-[10px] font-mono uppercase text-neutral-500">/ Add-ons ({rows.length})</div>
        <Button data-testid="cs-add-new" size="sm" onClick={() => setEditing({ ...blank })} className="bg-[#EC4899] hover:bg-[#db2777] text-white rounded-sm"><Plus className="w-3 h-3 mr-1" /> New add-on</Button>
      </div>
      {loading ? <Loading /> : (
        <div className="grid md:grid-cols-2 gap-2">
          {rows.length === 0 && <Empty msg="No add-ons defined." />}
          {rows.map((r) => (
            <div key={r.id} data-testid={`cs-add-row-${r.id}`} className="border border-white/10 rounded-sm bg-[#0f0f0f] p-3 flex justify-between items-center">
              <div>
                <div className="text-white text-sm flex items-center gap-2">
                  {r.name}
                  <span className="text-[9px] font-mono uppercase text-[#EC4899] border border-[#EC4899]/40 rounded px-1">{r.unit_type}</span>
                  {!r.custom_quantity_enabled && <span className="text-[9px] font-mono uppercase text-neutral-500 border border-white/10 rounded px-1">fixed qty</span>}
                  {!r.active && <span className="text-[9px] font-mono uppercase text-neutral-500 border border-white/10 rounded px-1">inactive</span>}
                </div>
                {r.description && <div className="text-[10px] text-neutral-500 mt-0.5">{r.description}</div>}
              </div>
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" data-testid={`cs-add-edit-${r.id}`} onClick={() => setEditing({ ...r })} className="text-[#84CC16]"><Edit3 className="w-3.5 h-3.5" /></Button>
                <Button size="sm" variant="ghost" data-testid={`cs-add-del-${r.id}`} onClick={() => remove(r.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></Button>
              </div>
            </div>
          ))}
        </div>
      )}
      {editing && (
        <EditorCard title={editing.id ? "Edit add-on" : "New add-on"} onCancel={() => setEditing(null)} onSave={save}>
          <TextField label="Name" value={editing.name} onChange={(v) => setEditing({ ...editing, name: v })} testid="cs-add-name" />
          <TextField label="Description" value={editing.description} onChange={(v) => setEditing({ ...editing, description: v })} textarea />
          <SelectField label="Unit type" value={editing.unit_type} onChange={(v) => setEditing({ ...editing, unit_type: v })} options={UNITS} />
          <BoolField label="Custom quantity" value={editing.custom_quantity_enabled} onChange={(v) => setEditing({ ...editing, custom_quantity_enabled: v })} />
          <BoolField label="Active" value={editing.active} onChange={(v) => setEditing({ ...editing, active: v })} />
        </EditorCard>
      )}
    </div>
  );
}

// ─────────────── Packages (compose services + addons) ───────────────
function PackagesPanel() {
  const { rows: packages, loading, reload } = useCrudList("/corporate-services/packages?include_inactive=true");
  const { rows: categories } = useCrudList("/corporate-services/categories?include_inactive=true");
  const { rows: services } = useCrudList("/corporate-services/services?include_inactive=true");
  const { rows: addons } = useCrudList("/corporate-services/addons?include_inactive=true");
  const [editing, setEditing] = useState(null);
  const blank = { category_id: "", name: "", description: "", tier: "standard", banner_url: "", gallery: [], included_service_ids: [], optional_addon_ids: [], active: true, sort_order: 0 };
  const TIERS = ["starter", "standard", "premium", "enterprise"];

  const save = async () => {
    try {
      if (!editing.category_id) return toast.error("Pick a category first");
      if (editing.id) await api.patch(`/admin/corporate-services/packages/${editing.id}`, editing);
      else await api.post("/admin/corporate-services/packages", editing);
      toast.success("Saved"); setEditing(null); reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this package?")) return;
    try { await api.delete(`/admin/corporate-services/packages/${id}`); toast.success("Deleted"); reload(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };
  const toggle = (arr, id) => arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id];

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <div className="text-[10px] font-mono uppercase text-neutral-500">/ Packages ({packages.length})</div>
        <Button data-testid="cs-pkg-new" size="sm" onClick={() => setEditing({ ...blank })} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black rounded-sm"><Plus className="w-3 h-3 mr-1" /> New package</Button>
      </div>
      {loading ? <Loading /> : (
        <div className="grid md:grid-cols-2 gap-3">
          {packages.length === 0 && <Empty msg="No packages yet — create categories & services first, then compose a package." />}
          {packages.map((p) => (
            <div key={p.id} data-testid={`cs-pkg-row-${p.id}`} className="border border-white/10 rounded-sm bg-[#0f0f0f] p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-white font-semibold">{p.name}</span>
                    <span className="text-[9px] font-mono uppercase text-[#06B6D4] border border-[#06B6D4]/40 rounded px-1">{p.tier}</span>
                    {!p.active && <span className="text-[9px] font-mono uppercase text-neutral-500 border border-white/10 rounded px-1">inactive</span>}
                  </div>
                  <div className="text-[10px] text-neutral-500 mt-1">
                    {categories.find((c) => c.id === p.category_id)?.name || "—"} · {p.included_service_ids?.length || 0} services · {p.optional_addon_ids?.length || 0} addons
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button size="sm" variant="ghost" data-testid={`cs-pkg-edit-${p.id}`} onClick={() => setEditing({ ...p })} className="text-[#84CC16]"><Edit3 className="w-3.5 h-3.5" /></Button>
                  <Button size="sm" variant="ghost" data-testid={`cs-pkg-del-${p.id}`} onClick={() => remove(p.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {editing && (
        <EditorCard title={editing.id ? "Edit package" : "New package"} onCancel={() => setEditing(null)} onSave={save}>
          <div className="grid md:grid-cols-2 gap-3">
            <SelectField label="Category" value={editing.category_id} onChange={(v) => setEditing({ ...editing, category_id: v })} options={categories.map((c) => ({ value: c.id, label: c.name }))} />
            <SelectField label="Tier" value={editing.tier} onChange={(v) => setEditing({ ...editing, tier: v })} options={TIERS} />
            <TextField label="Name" value={editing.name} onChange={(v) => setEditing({ ...editing, name: v })} testid="cs-pkg-name" />
            <TextField label="Sort order" value={editing.sort_order} onChange={(v) => setEditing({ ...editing, sort_order: Number(v) || 0 })} />
          </div>
          <TextField label="Description" value={editing.description} onChange={(v) => setEditing({ ...editing, description: v })} textarea />

          <div>
            <Label className="text-[10px] font-mono uppercase text-neutral-500">Banner image</Label>
            <div className="mt-2">
              <ImageUpload value={editing.banner_url} onChange={(url) => setEditing({ ...editing, banner_url: url })} />
            </div>
          </div>

          <div>
            <Label className="text-[10px] font-mono uppercase text-neutral-500">Included services ({editing.included_service_ids.length}) — tap to toggle</Label>
            <div className="mt-2 max-h-[220px] overflow-auto border border-white/10 rounded-sm bg-black/40 p-2 space-y-1">
              {services.filter((s) => s.active).map((s) => (
                <button key={s.id} type="button" data-testid={`cs-pkg-toggle-svc-${s.id}`}
                  onClick={() => setEditing({ ...editing, included_service_ids: toggle(editing.included_service_ids, s.id) })}
                  className={`w-full text-left px-2 py-1 rounded-sm text-xs flex justify-between items-center ${editing.included_service_ids.includes(s.id) ? "bg-[#84CC16]/15 text-[#84CC16]" : "text-neutral-400 hover:bg-white/5"}`}>
                  <span>{s.name} <span className="text-[9px] font-mono uppercase text-neutral-500">{s.unit_type}</span></span>
                  {editing.included_service_ids.includes(s.id) && <span className="text-[10px] font-mono">✓ in</span>}
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label className="text-[10px] font-mono uppercase text-neutral-500">Optional add-ons ({editing.optional_addon_ids.length}) — tap to toggle</Label>
            <div className="mt-2 max-h-[220px] overflow-auto border border-white/10 rounded-sm bg-black/40 p-2 space-y-1">
              {addons.filter((a) => a.active).map((a) => (
                <button key={a.id} type="button" data-testid={`cs-pkg-toggle-addon-${a.id}`}
                  onClick={() => setEditing({ ...editing, optional_addon_ids: toggle(editing.optional_addon_ids, a.id) })}
                  className={`w-full text-left px-2 py-1 rounded-sm text-xs flex justify-between items-center ${editing.optional_addon_ids.includes(a.id) ? "bg-[#EC4899]/15 text-[#EC4899]" : "text-neutral-400 hover:bg-white/5"}`}>
                  <span>{a.name} <span className="text-[9px] font-mono uppercase text-neutral-500">{a.unit_type}</span></span>
                  {editing.optional_addon_ids.includes(a.id) && <span className="text-[10px] font-mono">✓ in</span>}
                </button>
              ))}
            </div>
          </div>

          <BoolField label="Active" value={editing.active} onChange={(v) => setEditing({ ...editing, active: v })} />
        </EditorCard>
      )}
    </div>
  );
}

// ─────────────── Small helpers ───────────────
function EditorCard({ title, children, onSave, onCancel }) {
  return (
    <div className="mt-4 border border-white/10 rounded-sm bg-[#141414] p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4]">{title}</div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={onCancel} className="text-neutral-400"><X className="w-3.5 h-3.5 mr-1" /> Cancel</Button>
          <Button size="sm" data-testid="cs-editor-save" onClick={onSave} className="bg-[#84CC16] hover:bg-[#65A30D] text-black"><Save className="w-3.5 h-3.5 mr-1" /> Save</Button>
        </div>
      </div>
      {children}
    </div>
  );
}
function TextField({ label, value, onChange, textarea, testid }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase text-neutral-500">{label}</Label>
      {textarea ? (
        <Textarea data-testid={testid} value={value ?? ""} onChange={(e) => onChange(e.target.value)} rows={2} className="mt-1 bg-black/40 border-white/10 text-white text-sm" />
      ) : (
        <Input data-testid={testid} value={value ?? ""} onChange={(e) => onChange(e.target.value)} className="mt-1 bg-black/40 border-white/10 text-white" />
      )}
    </div>
  );
}
function BoolField({ label, value, onChange }) {
  return (
    <label className="inline-flex items-center gap-2 text-sm text-neutral-300 mt-1 cursor-pointer">
      <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} className="accent-[#84CC16]" />
      {label}
    </label>
  );
}
function SelectField({ label, value, onChange, options }) {
  const opts = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase text-neutral-500">{label}</Label>
      <Select value={value || ""} onValueChange={onChange}>
        <SelectTrigger className="mt-1 bg-black/40 border-white/10 text-white"><SelectValue placeholder="—" /></SelectTrigger>
        <SelectContent className="bg-[#141414] text-white border-white/10">
          {opts.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}
function Loading() { return <div className="text-neutral-500 text-sm p-6 text-center">Loading…</div>; }
function Empty({ msg }) { return <div className="text-neutral-500 text-sm p-6 text-center">{msg}</div>; }
