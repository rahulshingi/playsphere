import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtPrice } from "@/lib/currency";
import { Pause, Play, Trash2, Plus, X, BadgeCheck } from "lucide-react";

const PLAN_TYPES = [
  { v: "monthly",     l: "Monthly access" },
  { v: "daily_pass",  l: "Daily pass" },
  { v: "gym",         l: "Gym membership" },
  { v: "weekend",     l: "Weekend-only" },
  { v: "fixed_slot",  l: "Fixed time slot (e.g. 6–7 AM Mon–Fri)" },
  { v: "open",        l: "Open — any slot (48 hr advance required)" },
];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]; // index = day_of_week
const SPORTS = ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"];

const BLANK = {
  title: "", description: "", plan_type: "monthly", sports: [], listing_ids: [],
  price: 0, currency: "INR", duration_days: 30, max_bookings: null,
  slot_days_of_week: [], slot_start_time: "", slot_end_time: "",
  advance_booking_hours: 48, cover_image_url: "",
};

/**
 * VendorMembershipsPanel — vendor-side CRUD for membership plans.
 * Drops into the VendorDashboard. Phase 1: define plans only. Phase 2 will add
 * Razorpay purchase + my-memberships consumption tracking once keys are wired.
 */
export default function VendorMembershipsPanel({ listings = [] }) {
  const [plans, setPlans] = useState([]);
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/memberships/mine").then((r) => setPlans(r.data || [])).catch(() => setPlans([]));
  useEffect(() => { load(); }, []);

  const startNew = () => { setEditing({ ...BLANK }); setShowForm(true); };
  const startEdit = (p) => { setEditing({ ...p, max_bookings: p.max_bookings ?? "" }); setShowForm(true); };
  const cancel = () => { setEditing(null); setShowForm(false); };

  const save = async () => {
    if (!editing.title.trim()) { toast.error("Title is required"); return; }
    if (editing.price <= 0) { toast.error("Price must be greater than 0"); return; }
    setBusy(true);
    try {
      const payload = {
        ...editing,
        max_bookings: editing.max_bookings === "" || editing.max_bookings == null ? null : Number(editing.max_bookings),
        price: Number(editing.price),
        duration_days: Number(editing.duration_days),
        advance_booking_hours: Number(editing.advance_booking_hours),
      };
      if (editing.id) {
        await api.patch(`/memberships/mine/${editing.id}`, payload);
        toast.success("Plan updated");
      } else {
        await api.post("/memberships/mine", payload);
        toast.success("Plan created");
      }
      cancel();
      await load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally { setBusy(false); }
  };

  const togglePause = async (p) => {
    try {
      await api.patch(`/memberships/mine/${p.id}`, { paused: !p.paused });
      toast.success(p.paused ? "Plan resumed" : "Plan paused");
      load();
    } catch { toast.error("Failed"); }
  };

  const remove = async (p) => {
    if (!window.confirm(`Delete '${p.title}'? Purchased memberships will be preserved.`)) return;
    try {
      const { data } = await api.delete(`/memberships/mine/${p.id}`);
      if (data.soft_deactivated) toast.message(`Plan deactivated — ${data.purchases} purchase(s) preserved`);
      else toast.success("Plan deleted");
      load();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="mt-12">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">
          / Membership plans ({plans.length}) <span className="text-[#FACC15]">· payment coming soon</span>
        </div>
        <Button data-testid="memb-new" onClick={startNew} className="bg-[#EC4899] hover:bg-[#db2777] text-white font-semibold rounded-sm">
          <Plus className="w-4 h-4 mr-1" /> New plan
        </Button>
      </div>

      {plans.length === 0 && !showForm && (
        <div data-testid="memb-empty" className="text-neutral-500 text-sm text-center py-12 border border-dashed border-white/10 rounded-sm">
          No membership plans yet. Click <b>New plan</b> to offer monthly / daily / gym / weekend / fixed-slot access.
        </div>
      )}

      {plans.length > 0 && (
        <div className="grid md:grid-cols-2 gap-3">
          {plans.map((p) => (
            <div key={p.id} data-testid={`memb-card-${p.id}`}
              className={`border rounded-sm bg-[#141414] p-4 ${p.paused ? "border-amber-500/40 opacity-70" : "border-white/10"}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold">{p.title}</span>
                    <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#EC4899]/15 text-[#EC4899] border border-[#EC4899]/40">
                      {(PLAN_TYPES.find((t) => t.v === p.plan_type)?.l || p.plan_type).split(" (")[0]}
                    </span>
                    {p.paused && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-amber-500/15 text-amber-300 border border-amber-500/40">Paused</span>}
                    {!p.active && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#FF3B30]/15 text-[#FF3B30] border border-[#FF3B30]/40">Inactive</span>}
                  </div>
                  <div className="font-mono text-[10px] text-neutral-500 uppercase mt-1">
                    {fmtPrice(p.price, p.currency)} · {p.duration_days}d
                    {p.max_bookings ? ` · ${p.max_bookings} bookings` : " · unlimited bookings"}
                    {p.plan_type === "fixed_slot" && p.slot_start_time && ` · ${p.slot_start_time}–${p.slot_end_time}`}
                    {p.advance_booking_hours ? ` · ${p.advance_booking_hours}h advance` : ""}
                  </div>
                  {p.sports?.length > 0 && (
                    <div className="text-[10px] font-mono text-neutral-400 mt-1">{p.sports.join(" · ")}</div>
                  )}
                </div>
                <div className="flex gap-1 shrink-0">
                  <Button size="sm" variant="ghost" data-testid={`memb-edit-${p.id}`} onClick={() => startEdit(p)} className="text-[#84CC16] text-xs">Edit</Button>
                  <Button size="sm" variant="ghost" data-testid={`memb-pause-${p.id}`} onClick={() => togglePause(p)} className="text-[#FACC15]" title={p.paused ? "Resume" : "Pause"}>
                    {p.paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                  </Button>
                  <Button size="sm" variant="ghost" data-testid={`memb-del-${p.id}`} onClick={() => remove(p)} className="text-[#FF3B30]">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && editing && (
        <PlanForm editing={editing} setEditing={setEditing} listings={listings} busy={busy} onSave={save} onCancel={cancel} />
      )}
    </div>
  );
}

function PlanForm({ editing, setEditing, listings, busy, onSave, onCancel }) {
  const u = (k, v) => setEditing({ ...editing, [k]: v });
  const toggleArr = (k, val) => {
    const cur = editing[k] || [];
    u(k, cur.includes(val) ? cur.filter((x) => x !== val) : [...cur, val]);
  };
  const isFixed = editing.plan_type === "fixed_slot";

  return (
    <div className="mt-4 border border-[#EC4899]/40 rounded-sm bg-[#141414] p-5 space-y-3" data-testid="memb-form">
      <div className="flex items-center justify-between">
        <div className="font-display text-xl tracking-wide">{editing.id ? "EDIT PLAN" : "NEW MEMBERSHIP PLAN"}</div>
        <button onClick={onCancel} className="text-neutral-400 hover:text-white"><X className="w-4 h-4" /></button>
      </div>

      <Row label="Plan title *">
        <Input data-testid="memb-form-title" value={editing.title} onChange={(e) => u("title", e.target.value)} placeholder="e.g. Premium Monthly Cricket Access" className="bg-black/40 border-white/10 text-white" />
      </Row>
      <Row label="Description">
        <Textarea data-testid="memb-form-desc" rows={2} value={editing.description || ""} onChange={(e) => u("description", e.target.value)} className="bg-black/40 border-white/10 text-white" />
      </Row>

      <div className="grid md:grid-cols-2 gap-3">
        <Row label="Plan type *">
          <Select value={editing.plan_type} onValueChange={(v) => u("plan_type", v)}>
            <SelectTrigger data-testid="memb-form-type" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              {PLAN_TYPES.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}
            </SelectContent>
          </Select>
        </Row>
        <Row label="Price (INR) *">
          <Input data-testid="memb-form-price" type="number" min="1" value={editing.price} onChange={(e) => u("price", e.target.value)} className="bg-black/40 border-white/10 text-white" />
        </Row>
        <Row label="Duration (days)">
          <Input data-testid="memb-form-duration" type="number" min="1" value={editing.duration_days} onChange={(e) => u("duration_days", e.target.value)} className="bg-black/40 border-white/10 text-white" />
        </Row>
        <Row label="Max bookings (blank = unlimited)">
          <Input data-testid="memb-form-max" type="number" min="1" value={editing.max_bookings ?? ""} onChange={(e) => u("max_bookings", e.target.value)} className="bg-black/40 border-white/10 text-white" />
        </Row>
        <Row label="Advance booking required (hours)">
          <Input data-testid="memb-form-advance" type="number" min="0" value={editing.advance_booking_hours} onChange={(e) => u("advance_booking_hours", e.target.value)} className="bg-black/40 border-white/10 text-white" />
        </Row>
      </div>

      {isFixed && (
        <div className="border border-[#FACC15]/30 bg-[#FACC15]/5 rounded-sm p-3 space-y-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15]">/ Fixed slot config</div>
          <div className="grid grid-cols-2 gap-3">
            <Row label="Start time">
              <Input data-testid="memb-form-start" type="time" value={editing.slot_start_time || ""} onChange={(e) => u("slot_start_time", e.target.value)} className="bg-black/40 border-white/10 text-white" />
            </Row>
            <Row label="End time">
              <Input data-testid="memb-form-end" type="time" value={editing.slot_end_time || ""} onChange={(e) => u("slot_end_time", e.target.value)} className="bg-black/40 border-white/10 text-white" />
            </Row>
          </div>
          <Row label="Days of week">
            <div className="flex flex-wrap gap-1.5">
              {DAYS.map((d, i) => (
                <button key={d} type="button" data-testid={`memb-form-dow-${i}`} onClick={() => toggleArr("slot_days_of_week", i)}
                  className={`text-[10px] font-mono uppercase px-2 py-1 rounded-sm border transition-colors ${
                    (editing.slot_days_of_week || []).includes(i)
                      ? "bg-[#FACC15] text-black border-transparent"
                      : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
                  }`}>{d}</button>
              ))}
            </div>
          </Row>
        </div>
      )}

      <Row label="Sports covered">
        <div className="flex flex-wrap gap-1.5">
          {SPORTS.map((s) => (
            <button key={s} type="button" data-testid={`memb-form-sport-${s}`} onClick={() => toggleArr("sports", s)}
              className={`text-[10px] font-mono uppercase px-2 py-1 rounded-sm border transition-colors ${
                (editing.sports || []).includes(s)
                  ? "bg-[#84CC16] text-black border-transparent"
                  : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
              }`}>{s}</button>
          ))}
        </div>
      </Row>

      <Row label="Usable at listings (leave empty for all)">
        <div className="flex flex-wrap gap-1.5 max-h-40 overflow-auto">
          {listings.length === 0 && <div className="text-xs text-neutral-500">You don&apos;t have any listings yet — create a venue first to scope this plan.</div>}
          {listings.map((L) => (
            <button key={L.id} type="button" data-testid={`memb-form-listing-${L.id}`} onClick={() => toggleArr("listing_ids", L.id)}
              className={`text-[10px] font-mono px-2 py-1 rounded-sm border transition-colors ${
                (editing.listing_ids || []).includes(L.id)
                  ? "bg-[#06B6D4] text-black border-transparent"
                  : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
              }`}>{L.title} <span className="text-[9px] uppercase opacity-75">· {L.city}</span></button>
          ))}
        </div>
      </Row>

      <div className="flex gap-2 pt-2">
        <Button data-testid="memb-form-save" onClick={onSave} disabled={busy} className="bg-[#EC4899] hover:bg-[#db2777] text-white font-semibold rounded-sm">
          <BadgeCheck className="w-4 h-4 mr-1.5" /> {busy ? "Saving…" : editing.id ? "Save changes" : "Create plan"}
        </Button>
        <Button variant="ghost" onClick={onCancel} className="text-neutral-300 hover:text-white">Cancel</Button>
      </div>
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</Label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}
