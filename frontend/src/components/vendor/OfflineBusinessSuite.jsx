import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  LayoutDashboard, GraduationCap, Users2, Package, Wallet, BarChart3, ShieldCheck,
  Ban, Plus, Trash2, QrCode, MessageCircle, IndianRupee,
} from "lucide-react";
import DatePicker from "@/components/ui/DatePicker";
import { fmtPrice } from "@/lib/currency";
import PrivateBookingsPanel from "@/components/vendor/PrivateBookingsPanel";

/**
 * OfflineBusinessSuite — the umbrella UI on the Offline business tab that
 * bundles the 12 P0 offline-business capabilities:
 * Dashboard, Bookings/Calendar (PrivateBookingsPanel), Coaches, Batches,
 * Inventory, Expenses, Reports, Staff, Slot blocks and QR check-in.
 * Each capability is a small self-contained sub-view — no shared state — so it
 * lints cleanly and stays under 50 lines of intent per feature.
 */
export default function OfflineBusinessSuite({ vendor, listings }) {
  return (
    <div>
      <Tabs defaultValue="dashboard">
        <TabsList data-testid="obs-tabs" className="bg-black/40 border border-white/10 rounded-sm flex-wrap h-auto">
          <TabsTrigger value="dashboard" data-testid="obs-tab-dashboard" className="data-[state=active]:bg-[#FACC15] data-[state=active]:text-black rounded-sm"><LayoutDashboard className="w-3.5 h-3.5 mr-1" /> Dashboard</TabsTrigger>
          <TabsTrigger value="bookings" data-testid="obs-tab-bookings" className="data-[state=active]:bg-[#06B6D4] data-[state=active]:text-black rounded-sm">Bookings &amp; calendar</TabsTrigger>
          <TabsTrigger value="coaches" data-testid="obs-tab-coaches" className="data-[state=active]:bg-[#EC4899] data-[state=active]:text-white rounded-sm"><GraduationCap className="w-3.5 h-3.5 mr-1" /> Coaches &amp; batches</TabsTrigger>
          <TabsTrigger value="slots" data-testid="obs-tab-slots" className="data-[state=active]:bg-[#A855F7] data-[state=active]:text-white rounded-sm"><Ban className="w-3.5 h-3.5 mr-1" /> Slot blocks</TabsTrigger>
          <TabsTrigger value="inventory" data-testid="obs-tab-inventory" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm"><Package className="w-3.5 h-3.5 mr-1" /> Inventory</TabsTrigger>
          <TabsTrigger value="expenses" data-testid="obs-tab-expenses" className="data-[state=active]:bg-[#FF9500] data-[state=active]:text-black rounded-sm"><Wallet className="w-3.5 h-3.5 mr-1" /> Expenses</TabsTrigger>
          <TabsTrigger value="reports" data-testid="obs-tab-reports" className="data-[state=active]:bg-[#06B6D4] data-[state=active]:text-black rounded-sm"><BarChart3 className="w-3.5 h-3.5 mr-1" /> Reports</TabsTrigger>
          <TabsTrigger value="staff" data-testid="obs-tab-staff" className="data-[state=active]:bg-[#FF3B30] data-[state=active]:text-white rounded-sm"><ShieldCheck className="w-3.5 h-3.5 mr-1" /> Staff</TabsTrigger>
          <TabsTrigger value="checkin" data-testid="obs-tab-checkin" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm"><QrCode className="w-3.5 h-3.5 mr-1" /> Check-in</TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" className="mt-4"><DashboardKPIs vendor={vendor} /></TabsContent>
        <TabsContent value="bookings" className="mt-4"><PrivateBookingsPanel vendor={vendor} listings={listings} /></TabsContent>
        <TabsContent value="coaches" className="mt-4"><CoachesAndBatches vendor={vendor} listings={listings} /></TabsContent>
        <TabsContent value="slots" className="mt-4"><SlotBlocks vendor={vendor} listings={listings} /></TabsContent>
        <TabsContent value="inventory" className="mt-4"><Inventory /></TabsContent>
        <TabsContent value="expenses" className="mt-4"><Expenses /></TabsContent>
        <TabsContent value="reports" className="mt-4"><Reports /></TabsContent>
        <TabsContent value="staff" className="mt-4"><Staff /></TabsContent>
        <TabsContent value="checkin" className="mt-4"><CheckIn vendor={vendor} /></TabsContent>
      </Tabs>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Business dashboard — 8 KPI cards + today's schedule
// ─────────────────────────────────────────────────────────────
function DashboardKPIs({ vendor }) {
  const [d, setD] = useState(null);
  useEffect(() => {
    api.get("/vendor/dashboard-stats").then((r) => setD(r.data)).catch(() => setD(null));
  }, []);
  if (!d) return <div className="text-neutral-500">Loading…</div>;
  const cards = [
    { label: "Today's revenue", val: fmtPrice(d.today_revenue, "INR"), tone: "bg-[#84CC16]/10 border-[#84CC16]/40 text-[#84CC16]" },
    { label: "Today's bookings", val: d.today_bookings, tone: "bg-[#06B6D4]/10 border-[#06B6D4]/40 text-[#06B6D4]" },
    { label: "Walk-in customers", val: d.walk_in_customers, tone: "bg-[#EC4899]/10 border-[#EC4899]/40 text-[#EC4899]" },
    { label: "Platform customers", val: d.online_customers, tone: "bg-[#FACC15]/10 border-[#FACC15]/40 text-[#FACC15]" },
    { label: "Active members", val: d.active_members, tone: "bg-[#A855F7]/10 border-[#A855F7]/40 text-[#A855F7]" },
    { label: "Court utilisation", val: `${d.court_utilisation_percent}%`, tone: "bg-[#FF9500]/10 border-[#FF9500]/40 text-[#FF9500]" },
    { label: "Pending payments", val: fmtPrice(d.pending_payment_amount, "INR"), sub: `${d.pending_payment_count} invoice(s)`, tone: "bg-[#FF3B30]/10 border-[#FF3B30]/40 text-[#FF3B30]" },
    { label: "Fresh leads (7d)", val: d.new_leads_count, tone: "bg-[#84CC16]/10 border-[#84CC16]/40 text-[#84CC16]" },
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map((c) => (
          <div key={c.label} data-testid={`kpi-${c.label.toLowerCase().replace(/[^a-z]+/g, '-')}`}
            className={`border rounded-sm p-3 ${c.tone}`}>
            <div className="text-[10px] font-mono uppercase tracking-widest opacity-70">{c.label}</div>
            <div className="text-2xl font-display mt-1">{c.val}</div>
            {c.sub && <div className="text-[10px] font-mono opacity-70">{c.sub}</div>}
          </div>
        ))}
      </div>
      <div className="border border-white/10 rounded-sm bg-[#141414] p-4">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-2">/ Today's schedule</div>
        {d.todays_schedule.length === 0
          ? <div className="text-neutral-500 text-sm">Nothing on the books today.</div>
          : (
            <div className="space-y-1">
              {d.todays_schedule.map((s) => (
                <div key={s.id} className="flex items-center gap-3 text-sm font-mono">
                  <span className="text-[#06B6D4] w-24">{s.start_time}–{s.end_time}</span>
                  <span className="text-[9px] uppercase px-1 rounded-sm border border-white/10 text-neutral-400">{s.kind}</span>
                  <span className="text-white">{s.who}</span>
                </div>
              ))}
            </div>
          )}
      </div>

      {/* Top customers by lifetime spend */}
      <div data-testid="kpi-top-customers" className="border border-[#FACC15]/40 bg-[#FACC15]/5 rounded-sm p-4">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15] mb-2">/ Top customers · lifetime value</div>
        {(d.top_customers || []).length === 0
          ? <div className="text-neutral-500 text-sm">Once you have paid invoices, your top 20 customers will show here — perfect for personalised offers.</div>
          : (
            <div className="grid md:grid-cols-2 gap-2">
              {d.top_customers.map((c, i) => (
                <div key={c.id} data-testid={`top-cust-${c.id}`} className="flex items-center justify-between border border-white/10 rounded-sm bg-black/40 p-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-mono text-[10px] w-6 text-center text-[#FACC15]">#{i + 1}</span>
                    <div className="min-w-0">
                      <div className="text-sm truncate">{c.name}</div>
                      <div className="text-[10px] font-mono text-neutral-500">{c.phone || "—"} · {c.invoices} inv</div>
                    </div>
                  </div>
                  <div className="font-mono text-sm text-[#84CC16] shrink-0">{fmtPrice(c.total_spent, "INR")}</div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Coaches & Batches — CRUD, enrol students, view roster, full notification
// ─────────────────────────────────────────────────────────────
function CoachesAndBatches({ vendor, listings }) {
  const [coaches, setCoaches] = useState([]);
  const [batches, setBatches] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [editingCoach, setEditingCoach] = useState(null); // null | {…}
  const [editingBatch, setEditingBatch] = useState(null);
  const [rosterBatch, setRosterBatch] = useState(null);

  const load = () => {
    api.get("/vendor/coaches").then((r) => setCoaches(r.data || []));
    api.get("/vendor/batches").then((r) => setBatches(r.data || []));
    api.get("/vendor/customers").then((r) => setCustomers(r.data || [])).catch(() => {});
  };
  useEffect(load, []);

  const saveCoach = async (form) => {
    try {
      if (form.id) {
        await api.patch(`/vendor/coaches/${form.id}`, form);
        toast.success("Coach updated");
      } else {
        await api.post("/vendor/coaches", form);
        toast.success("Coach added");
      }
      setEditingCoach(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const saveBatch = async (form) => {
    try {
      if (form.id) {
        await api.patch(`/vendor/batches/${form.id}`, form);
        toast.success("Batch updated");
      } else {
        await api.post("/vendor/batches", form);
        toast.success("Batch added");
      }
      setEditingBatch(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {/* Coaches column */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Coaches ({coaches.length})</div>
          <Button size="sm" data-testid="obs-coach-add" onClick={() => setEditingCoach({ name: "", phone: "", email: "", sports: "", hourly_rate: 0 })} className="bg-[#EC4899] hover:bg-[#DB2777] text-white rounded-sm h-7"><Plus className="w-3 h-3 mr-1" /> New</Button>
        </div>
        <div className="space-y-1">
          {coaches.map((c) => (
            <div key={c.id} data-testid={`coach-${c.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-2 flex justify-between items-center">
              <div>
                <div className="text-sm">{c.name}</div>
                <div className="text-[10px] font-mono text-neutral-500">{c.phone} · {(c.sports || []).join(", ")} · {fmtPrice(c.hourly_rate, "INR")}/h</div>
              </div>
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" data-testid={`coach-edit-${c.id}`} onClick={() => setEditingCoach({ ...c, sports: (c.sports || []).join(", ") })} className="text-[#06B6D4] h-7 px-2 text-[11px]">Edit</Button>
                <Button size="sm" variant="ghost" onClick={async () => { if (!window.confirm(`Delete coach ${c.name}?`)) return; await api.delete(`/vendor/coaches/${c.id}`); load(); }} className="text-[#FF3B30] h-7 px-2"><Trash2 className="w-3 h-3" /></Button>
              </div>
            </div>
          ))}
          {coaches.length === 0 && <div className="text-neutral-500 text-xs">No coaches yet.</div>}
        </div>
      </div>

      {/* Batches column */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Batches ({batches.length})</div>
          <Button size="sm" data-testid="obs-batch-add" onClick={() => setEditingBatch({ name: "", sport: "", coach_id: coaches[0]?.id || "", listing_id: listings[0]?.id || "", start_time: "06:00", end_time: "07:00", capacity: 20, monthly_fee: 2000 })} disabled={coaches.length === 0} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black rounded-sm h-7"><Plus className="w-3 h-3 mr-1" /> New</Button>
        </div>
        <div className="space-y-1">
          {batches.map((b) => {
            const coachName = coaches.find((c) => c.id === b.coach_id)?.name || "—";
            const enrolled = b.student_ids?.length || 0;
            const isFull = b.capacity && enrolled >= b.capacity;
            return (
              <div key={b.id} data-testid={`batch-${b.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm flex items-center gap-2">
                      {b.name}
                      {isFull && <span data-testid={`batch-full-${b.id}`} className="text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-sm bg-[#FF3B30]/20 text-[#FF3B30] border border-[#FF3B30]/40">FULL</span>}
                    </div>
                    <div className="text-[10px] font-mono text-neutral-500">{b.start_time}–{b.end_time} · coach {coachName} · {enrolled}/{b.capacity} · {fmtPrice(b.monthly_fee, "INR")}/mo</div>
                  </div>
                  <div className="flex gap-1">
                    <Button size="sm" variant="ghost" data-testid={`batch-roster-${b.id}`} onClick={() => setRosterBatch(b)} className="text-[#84CC16] h-7 px-2 text-[11px]">Roster</Button>
                    <Button size="sm" variant="ghost" data-testid={`batch-edit-${b.id}`} onClick={() => setEditingBatch(b)} className="text-[#06B6D4] h-7 px-2 text-[11px]">Edit</Button>
                    <Button size="sm" variant="ghost" onClick={async () => { if (!window.confirm(`Delete batch ${b.name}?`)) return; await api.delete(`/vendor/batches/${b.id}`); load(); }} className="text-[#FF3B30] h-7 px-2"><Trash2 className="w-3 h-3" /></Button>
                  </div>
                </div>
              </div>
            );
          })}
          {batches.length === 0 && <div className="text-neutral-500 text-xs">No batches yet — add a coach first.</div>}
        </div>
      </div>

      <CoachDialog open={!!editingCoach} initial={editingCoach} onClose={() => setEditingCoach(null)} onSave={saveCoach} />
      <BatchDialog open={!!editingBatch} initial={editingBatch} onClose={() => setEditingBatch(null)} onSave={saveBatch} coaches={coaches} listings={listings} />
      <BatchRosterDialog open={!!rosterBatch} batch={rosterBatch} customers={customers} onClose={() => { setRosterBatch(null); load(); }} />
    </div>
  );
}

function CoachDialog({ open, initial, onClose, onSave }) {
  const [f, setF] = useState({});
  useEffect(() => { setF(initial || {}); }, [initial]);
  if (!open) return null;
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-[#0c0c0c] border-white/10 text-white">
        <DialogHeader><DialogTitle>{f.id ? "Edit coach" : "New coach"}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Input data-testid="coach-form-name" placeholder="Full name" value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="coach-form-phone" placeholder="Phone" value={f.phone || ""} onChange={(e) => setF({ ...f, phone: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="coach-form-email" placeholder="Email" value={f.email || ""} onChange={(e) => setF({ ...f, email: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="coach-form-sports" placeholder="Sports (comma-separated: cricket, football)" value={f.sports || ""} onChange={(e) => setF({ ...f, sports: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="coach-form-rate" placeholder="Hourly rate (INR)" type="number" value={f.hourly_rate ?? 0} onChange={(e) => setF({ ...f, hourly_rate: Number(e.target.value) })} className="bg-black/40 border-white/10 text-white" />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button data-testid="coach-form-save" onClick={() => onSave({ ...f, sports: typeof f.sports === "string" ? f.sports.split(",").map((s) => s.trim()).filter(Boolean) : (f.sports || []) })} className="bg-[#EC4899] hover:bg-[#DB2777] text-white">Save</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function BatchDialog({ open, initial, onClose, onSave, coaches, listings }) {
  const [f, setF] = useState({});
  useEffect(() => { setF(initial || {}); }, [initial]);
  if (!open) return null;
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-[#0c0c0c] border-white/10 text-white">
        <DialogHeader><DialogTitle>{f.id ? "Edit batch" : "New batch"}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Input data-testid="batch-form-name" placeholder="Batch name (Morning batch, U-14 …)" value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="batch-form-sport" placeholder="Sport" value={f.sport || ""} onChange={(e) => setF({ ...f, sport: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Select value={f.coach_id || ""} onValueChange={(v) => setF({ ...f, coach_id: v })}>
            <SelectTrigger data-testid="batch-form-coach" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Assign coach" /></SelectTrigger>
            <SelectContent className="bg-[#0c0c0c] text-white border-white/10">
              {coaches.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={f.listing_id || ""} onValueChange={(v) => setF({ ...f, listing_id: v })}>
            <SelectTrigger data-testid="batch-form-listing" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Attach to listing (optional)" /></SelectTrigger>
            <SelectContent className="bg-[#0c0c0c] text-white border-white/10">
              {listings.map((l) => <SelectItem key={l.id} value={l.id}>{l.title}</SelectItem>)}
            </SelectContent>
          </Select>
          <div className="grid grid-cols-2 gap-2">
            <Input data-testid="batch-form-start" placeholder="Start (06:00)" value={f.start_time || ""} onChange={(e) => setF({ ...f, start_time: e.target.value })} className="bg-black/40 border-white/10 text-white" />
            <Input data-testid="batch-form-end" placeholder="End (07:00)" value={f.end_time || ""} onChange={(e) => setF({ ...f, end_time: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Input data-testid="batch-form-capacity" type="number" placeholder="Capacity" value={f.capacity ?? 20} onChange={(e) => setF({ ...f, capacity: Number(e.target.value) })} className="bg-black/40 border-white/10 text-white" />
            <Input data-testid="batch-form-fee" type="number" placeholder="Monthly fee (INR)" value={f.monthly_fee ?? 0} onChange={(e) => setF({ ...f, monthly_fee: Number(e.target.value) })} className="bg-black/40 border-white/10 text-white" />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button data-testid="batch-form-save" onClick={() => onSave(f)} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black">Save</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function BatchRosterDialog({ open, batch, customers, onClose }) {
  const [roster, setRoster] = useState([]);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = async () => {
    if (!batch?.id) return;
    const { data } = await api.get(`/vendor/batches/${batch.id}/roster`);
    setRoster(data.students || []);
  };
  useEffect(() => { if (open && batch?.id) reload(); /* eslint-disable-next-line */ }, [open, batch?.id]);

  if (!open || !batch) return null;
  const capacity = batch.capacity || 0;
  const isFull = capacity && roster.length >= capacity;

  const enrol = async () => {
    if (!pick) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/vendor/batches/${batch.id}/enrol`, { customer_id: pick });
      if (data.full) toast.info("Batch is now full — you may want to open a waitlist");
      else toast.success("Enrolled");
      setPick(""); reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  const unenrol = async (cid) => {
    if (!window.confirm("Remove this student from the batch?")) return;
    await api.post(`/vendor/batches/${batch.id}/unenrol`, { customer_id: cid });
    toast.success("Removed"); reload();
  };
  const available = customers.filter((c) => !roster.some((r) => r.id === c.id));

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-[#0c0c0c] border-white/10 text-white max-w-lg">
        <DialogHeader><DialogTitle>{batch.name} · Roster</DialogTitle></DialogHeader>
        <div className="text-[10px] font-mono uppercase text-neutral-500">{roster.length}/{capacity} enrolled {isFull && <span className="text-[#FF3B30]">· FULL</span>}</div>

        <div className="mt-3 border border-white/10 rounded-sm max-h-64 overflow-auto divide-y divide-white/5">
          {roster.length === 0 && <div className="p-3 text-neutral-500 text-xs">No students enrolled yet.</div>}
          {roster.map((s) => (
            <div key={s.id} data-testid={`roster-row-${s.id}`} className="p-2 flex items-center justify-between">
              <div>
                <div className="text-sm">{s.name}</div>
                <div className="text-[10px] font-mono text-neutral-500">{s.phone}</div>
              </div>
              <Button size="sm" variant="ghost" onClick={() => unenrol(s.id)} className="text-[#FF3B30] h-7 px-2"><Trash2 className="w-3 h-3" /></Button>
            </div>
          ))}
        </div>

        {!isFull && (
          <div className="mt-3 flex items-end gap-2">
            <div className="flex-1">
              <div className="font-mono text-[10px] uppercase text-neutral-500 mb-1">/ Enrol a customer</div>
              <Select value={pick} onValueChange={setPick}>
                <SelectTrigger data-testid="roster-pick" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Pick from your directory" /></SelectTrigger>
                <SelectContent className="bg-[#0c0c0c] text-white border-white/10 max-h-64">
                  {available.map((c) => <SelectItem key={c.id} value={c.id}>{c.name} — {c.phone}</SelectItem>)}
                  {available.length === 0 && <div className="p-2 text-neutral-500 text-xs">No more customers to enrol.</div>}
                </SelectContent>
              </Select>
            </div>
            <Button data-testid="roster-enrol" disabled={!pick || busy} onClick={enrol} className="bg-[#84CC16] hover:bg-[#65A30D] text-black">Enrol</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}


// ─────────────────────────────────────────────────────────────
// Slot blocks
// ─────────────────────────────────────────────────────────────
function SlotBlocks({ listings }) {
  const [blocks, setBlocks] = useState([]);
  const [f, setF] = useState({ listing_id: listings[0]?.id || "", date: "", start_time: "10:00", end_time: "11:00", reason: "maintenance", notes: "" });
  const load = () => api.get("/vendor/slot-blocks").then((r) => setBlocks(r.data || []));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = async () => {
    if (!f.listing_id || !f.date) return toast.error("Listing + date required");
    try {
      await api.post("/vendor/slot-blocks", f);
      toast.success("Slot blocked"); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  return (
    <div className="space-y-3">
      <div className="border border-white/10 rounded-sm bg-[#141414] p-3">
        <div className="grid md:grid-cols-6 gap-2">
          <Select value={f.listing_id} onValueChange={(v) => setF({ ...f, listing_id: v })}>
            <SelectTrigger data-testid="sb-listing" className="bg-black/40 border-white/10 text-white h-9 text-xs"><SelectValue placeholder="Listing" /></SelectTrigger>
            <SelectContent className="bg-[#141414] border-white/10 text-white">
              {listings.map((L) => <SelectItem key={L.id} value={L.id}>{L.title}</SelectItem>)}
            </SelectContent>
          </Select>
          <DatePicker data-testid="sb-date" value={f.date} onChange={(v) => setF({ ...f, date: v })} minDate={new Date()} placeholder="Date" />
          <Input data-testid="sb-start" type="time" value={f.start_time} onChange={(e) => setF({ ...f, start_time: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="sb-end" type="time" value={f.end_time} onChange={(e) => setF({ ...f, end_time: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Select value={f.reason} onValueChange={(v) => setF({ ...f, reason: v })}>
            <SelectTrigger data-testid="sb-reason" className="bg-black/40 border-white/10 text-white h-9 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#141414] border-white/10 text-white">
              <SelectItem value="maintenance">Maintenance</SelectItem>
              <SelectItem value="tournament">Tournament</SelectItem>
              <SelectItem value="private">Private booking</SelectItem>
              <SelectItem value="staff_practice">Staff practice</SelectItem>
            </SelectContent>
          </Select>
          <Button data-testid="sb-submit" onClick={submit} className="bg-[#A855F7] hover:bg-[#9333EA] text-white rounded-sm"><Ban className="w-4 h-4 mr-1" /> Block slot</Button>
        </div>
      </div>
      <div className="space-y-1">
        {blocks.map((b) => (
          <div key={b.id} data-testid={`sb-${b.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-2 flex justify-between items-center">
            <div className="text-sm">
              <span className="text-[#A855F7] font-mono text-[10px] uppercase mr-2">{b.reason}</span>
              {b.date} · {b.start_time}–{b.end_time}
            </div>
            <Button size="sm" variant="ghost" onClick={async () => { await api.delete(`/vendor/slot-blocks/${b.id}`); load(); }} className="text-[#FF3B30]"><Trash2 className="w-3 h-3" /></Button>
          </div>
        ))}
        {blocks.length === 0 && <div className="text-neutral-500 text-xs">No slot blocks — the whole schedule is open.</div>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Inventory
// ─────────────────────────────────────────────────────────────
function Inventory() {
  const [items, setItems] = useState([]);
  const load = () => api.get("/vendor/inventory").then((r) => setItems(r.data || []));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const add = async () => {
    const name = prompt("Item name?"); if (!name) return;
    await api.post("/vendor/inventory", { name, category: prompt("Category (shuttle/ball/jersey/equipment)?", "other") || "other", quantity: Number(prompt("Qty?", "0") || 0), low_stock_threshold: Number(prompt("Low-stock threshold?", "5") || 5), cost_price: Number(prompt("Cost price?", "0") || 0), sale_price: Number(prompt("Sale price?", "0") || 0) });
    load();
  };
  const adjust = async (it, delta) => {
    await api.patch(`/vendor/inventory/${it.id}`, { quantity: Math.max(0, it.quantity + delta) });
    load();
  };
  return (
    <div className="space-y-2">
      <Button data-testid="inv-add" onClick={add} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm"><Plus className="w-4 h-4 mr-1" /> New item</Button>
      <div className="space-y-1">
        {items.map((it) => (
          <div key={it.id} data-testid={`inv-${it.id}`} className={`border rounded-sm p-2 flex justify-between items-center ${it.quantity <= it.low_stock_threshold ? "border-[#FF3B30]/50 bg-[#FF3B30]/5" : "border-white/10 bg-[#141414]"}`}>
            <div>
              <div className="text-sm">{it.name} <span className="text-[10px] font-mono uppercase text-neutral-500 ml-1">{it.category}</span></div>
              <div className="text-[10px] font-mono text-neutral-500">Cost {fmtPrice(it.cost_price, "INR")} · Sale {fmtPrice(it.sale_price, "INR")}</div>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => adjust(it, -1)} className="border-white/10 text-white bg-transparent h-7 w-7 p-0">−</Button>
              <span className={`font-mono w-8 text-center ${it.quantity <= it.low_stock_threshold ? "text-[#FF3B30]" : "text-white"}`}>{it.quantity}</span>
              <Button size="sm" variant="outline" onClick={() => adjust(it, +1)} className="border-white/10 text-white bg-transparent h-7 w-7 p-0">+</Button>
              <Button size="sm" variant="ghost" onClick={async () => { await api.delete(`/vendor/inventory/${it.id}`); load(); }} className="text-[#FF3B30]"><Trash2 className="w-3 h-3" /></Button>
            </div>
          </div>
        ))}
        {items.length === 0 && <div className="text-neutral-500 text-xs">No items yet.</div>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Expenses
// ─────────────────────────────────────────────────────────────
function Expenses() {
  const [rows, setRows] = useState([]);
  const [f, setF] = useState({ date: new Date().toISOString().slice(0, 10), category: "rent", amount: 0, notes: "" });
  const load = () => api.get("/vendor/expenses").then((r) => setRows(r.data || []));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const total = rows.reduce((s, r) => s + Number(r.amount || 0), 0);
  const submit = async () => {
    if (!f.amount) return toast.error("Amount required");
    await api.post("/vendor/expenses", f); toast.success("Expense logged"); load();
  };
  return (
    <div className="space-y-2">
      <div className="border border-white/10 rounded-sm bg-[#141414] p-3 grid md:grid-cols-5 gap-2">
        <DatePicker data-testid="exp-date" value={f.date} onChange={(v) => setF({ ...f, date: v })} placeholder="Date" />
        <Select value={f.category} onValueChange={(v) => setF({ ...f, category: v })}>
          <SelectTrigger data-testid="exp-cat" className="bg-black/40 border-white/10 text-white h-9 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-[#141414] border-white/10 text-white">
            {["rent", "electricity", "water", "salary", "equipment", "maintenance", "misc"].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input data-testid="exp-amount" type="number" placeholder="Amount" value={f.amount} onChange={(e) => setF({ ...f, amount: Number(e.target.value) })} className="bg-black/40 border-white/10 text-white" />
        <Input data-testid="exp-notes" placeholder="Notes" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        <Button data-testid="exp-submit" onClick={submit} className="bg-[#FF9500] hover:bg-[#E88900] text-black rounded-sm"><Plus className="w-4 h-4 mr-1" /> Log</Button>
      </div>
      <div className="flex items-center gap-3 text-sm text-neutral-300">Total for shown period: <span className="text-[#FF9500] font-mono">{fmtPrice(total, "INR")}</span></div>
      <div className="space-y-1">
        {rows.map((r) => (
          <div key={r.id} className="border border-white/10 rounded-sm bg-[#141414] p-2 flex justify-between text-sm">
            <div>
              <span className="font-mono text-[10px] uppercase text-neutral-500 mr-2">{r.date}</span>
              <span className="text-[#FF9500] font-mono text-[10px] uppercase mr-2">{r.category}</span>
              {r.notes}
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[#FF9500]">{fmtPrice(r.amount, r.currency)}</span>
              <Button size="sm" variant="ghost" onClick={async () => { await api.delete(`/vendor/expenses/${r.id}`); load(); }} className="text-[#FF3B30]"><Trash2 className="w-3 h-3" /></Button>
            </div>
          </div>
        ))}
        {rows.length === 0 && <div className="text-neutral-500 text-xs">No expenses logged yet.</div>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Reports
// ─────────────────────────────────────────────────────────────
function Reports() {
  const [range, setRange] = useState("monthly");
  const [d, setD] = useState(null);
  useEffect(() => { api.get(`/vendor/reports?range=${range}`).then((r) => setD(r.data)); }, [range]);
  if (!d) return <div className="text-neutral-500">Loading…</div>;
  return (
    <div className="space-y-3">
      <div className="flex gap-2 items-center">
        {["daily", "weekly", "monthly"].map((r) => (
          <Button key={r} data-testid={`rep-range-${r}`} onClick={() => setRange(r)}
            className={`rounded-sm ${range === r ? "bg-[#06B6D4] text-black" : "bg-transparent border border-white/10 text-white"}`}>{r}</Button>
        ))}
      </div>
      <div className="grid md:grid-cols-3 gap-3">
        <Card label="Revenue" val={fmtPrice(d.revenue, "INR")} tone="text-[#84CC16] border-[#84CC16]/40 bg-[#84CC16]/10" />
        <Card label="Expenses" val={fmtPrice(d.expenses, "INR")} tone="text-[#FF9500] border-[#FF9500]/40 bg-[#FF9500]/10" />
        <Card label="Profit" val={fmtPrice(d.profit, "INR")} tone="text-[#06B6D4] border-[#06B6D4]/40 bg-[#06B6D4]/10" />
        <Card label="Bookings" val={`${d.bookings.total} (${d.bookings.private} priv · ${d.bookings.online} online)`} tone="text-[#EC4899] border-[#EC4899]/40 bg-[#EC4899]/10" />
        <Card label="Membership sales" val={d.membership_sales} tone="text-[#A855F7] border-[#A855F7]/40 bg-[#A855F7]/10" />
        <Card label="Top customer" val={d.top_customers?.[0]?.name || "—"} sub={d.top_customers?.[0]?.spent ? fmtPrice(d.top_customers[0].spent, "INR") : ""} tone="text-[#FACC15] border-[#FACC15]/40 bg-[#FACC15]/10" />
      </div>
      {d.peak_hours?.some((h) => h > 0) && (
        <div className="border border-white/10 rounded-sm bg-[#141414] p-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-2">/ Peak hours</div>
          <div className="flex items-end gap-0.5 h-16">
            {d.peak_hours.map((c, i) => {
              const max = Math.max(...d.peak_hours) || 1;
              return <div key={i} title={`${i}:00 — ${c} booking(s)`} className="flex-1 bg-[#06B6D4]" style={{ height: `${(c / max) * 100}%`, minHeight: c ? 2 : 0 }} />;
            })}
          </div>
          <div className="flex justify-between text-[9px] font-mono text-neutral-500 mt-1"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div>
        </div>
      )}
    </div>
  );
}
function Card({ label, val, sub, tone }) {
  return (
    <div className={`border rounded-sm p-3 ${tone}`}>
      <div className="text-[10px] font-mono uppercase tracking-widest opacity-70">{label}</div>
      <div className="text-2xl font-display mt-1">{val}</div>
      {sub && <div className="text-[10px] font-mono opacity-70">{sub}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Staff
// ─────────────────────────────────────────────────────────────
function Staff() {
  const [rows, setRows] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [f, setF] = useState({ name: "", email: "", password: "", role: "receptionist" });
  const load = () => api.get("/vendor/staff").then((r) => setRows(r.data || []));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = async () => {
    if (!f.email || !f.password) return toast.error("Email + password required");
    try { await api.post("/vendor/staff", f); toast.success("Staff added"); setShowAdd(false); setF({ name: "", email: "", password: "", role: "receptionist" }); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  return (
    <div className="space-y-2">
      <Button data-testid="staff-add" onClick={() => setShowAdd(true)} className="bg-[#FF3B30] hover:bg-[#E82C22] text-white rounded-sm"><Plus className="w-4 h-4 mr-1" /> New staff</Button>
      <div className="space-y-1">
        {rows.map((s) => (
          <div key={s.id} data-testid={`staff-${s.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-2 flex justify-between items-center">
            <div>
              <div className="text-sm">{s.name} <span className="text-[10px] font-mono uppercase text-[#FF3B30] ml-2">{s.role}</span></div>
              <div className="text-[10px] font-mono text-neutral-500">{s.email} · perms: {s.permissions?.join(", ")}</div>
            </div>
            <Button size="sm" variant="ghost" onClick={async () => { await api.delete(`/vendor/staff/${s.id}`); load(); }} className="text-[#FF3B30]"><Trash2 className="w-3 h-3" /></Button>
          </div>
        ))}
        {rows.length === 0 && <div className="text-neutral-500 text-xs">No sub-users yet. Add a receptionist so they can log in at /login with their own credentials.</div>}
      </div>
      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="bg-[#0c0c0c] border-white/10 text-white max-w-md">
          <DialogHeader><DialogTitle>Invite staff</DialogTitle></DialogHeader>
          <Input placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input placeholder="Email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input placeholder="Password (min 6)" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Select value={f.role} onValueChange={(v) => setF({ ...f, role: v })}>
            <SelectTrigger className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#141414] border-white/10 text-white">
              <SelectItem value="receptionist">Receptionist (bookings + customers + check-in; NO reports)</SelectItem>
              <SelectItem value="coach">Coach (batches + check-in)</SelectItem>
              <SelectItem value="owner">Owner (full access)</SelectItem>
            </SelectContent>
          </Select>
          <Button data-testid="staff-submit" onClick={submit} className="bg-[#FF3B30] hover:bg-[#E82C22] text-white rounded-sm">Create</Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Check-in — QR poster + list of currently on-premise + countdown +
// checkout with automatic overrun-billing + ambiguity picker.
// ─────────────────────────────────────────────────────────────
function CheckIn({ vendor }) {
  const [code, setCode] = useState("");
  const [last, setLast] = useState(null);
  const [ambiguous, setAmbiguous] = useState(null); // {customer, options}
  const [active, setActive] = useState([]);
  const [showPoster, setShowPoster] = useState(false);
  const [_tick, setTick] = useState(0);

  const loadActive = () => {
    api.get("/vendor/checkins/active").then((r) => setActive(r.data || [])).catch(() => {});
  };
  useEffect(() => {
    loadActive();
    // Client-side countdown tick — every 30s recompute time-remaining labels
    const t = setInterval(() => setTick((x) => x + 1), 30000);
    return () => clearInterval(t);
  }, []);

  const submit = async (opts = {}) => {
    if (!code.trim() && !opts.context_type) return;
    try {
      const body = { code: code.trim(), method: "manual", ...opts };
      const { data } = await api.post("/vendor/checkin", body);
      if (data.ambiguous) {
        setAmbiguous(data);
        return;
      }
      setLast(data); setCode(""); setAmbiguous(null);
      toast.success("Checked in");
      loadActive();
    } catch (e) { toast.error(e.response?.data?.detail || "Not found"); }
  };

  const pickOption = (opt) => {
    submit({ context_type: opt.type, context_id: opt.id });
  };

  const checkout = async (ci) => {
    if (!window.confirm("Confirm checkout?")) return;
    try {
      const { data } = await api.post(`/vendor/checkins/${ci.id}/checkout`, { bill_overrun: true });
      if (data.overrun_minutes > 0 && data.extra_amount > 0) {
        toast.warning(`Overrun ${data.overrun_minutes} min — extra invoice for ${fmtPrice(data.extra_amount, "INR")} generated.`);
      } else {
        toast.success("Checked out");
      }
      loadActive();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  // Vendor QR poster — encodes the vendor's public site URL. Anyone scanning
  // lands on Kreeda Nation, then picks a listing to browse/book.
  const base = typeof window !== "undefined" ? window.location.origin : "";
  const posterUrl = `${base}/vendors/${vendor?.id || "unknown"}`;
  const qrSrc = `https://api.qrserver.com/v1/create-qr-code/?size=280x280&data=${encodeURIComponent(posterUrl)}`;

  const remaining = (planned) => {
    if (!planned) return { text: "—", warn: false };
    const p = new Date(planned).getTime();
    const now = Date.now();
    const diff = p - now;
    if (diff < 0) {
      const over = Math.floor(-diff / 60000);
      return { text: `Overdue ${over}m`, warn: true };
    }
    const mins = Math.floor(diff / 60000);
    const hh = Math.floor(mins / 60);
    const mm = mins % 60;
    return { text: `${hh > 0 ? `${hh}h ` : ""}${mm}m left`, warn: mins <= 5 };
  };

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {/* Left: QR check-in input + QR poster */}
      <div className="space-y-3">
        <div className="border border-white/10 rounded-sm bg-[#141414] p-4">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-2">/ Check-in in &lt; 5 seconds</div>
          <p className="text-xs text-neutral-400 mb-3">Scan the customer&apos;s booking QR, or type booking ID / phone number below.</p>
          <div className="flex gap-2">
            <Input autoFocus data-testid="checkin-code" placeholder="Booking ID or phone" value={code} onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} className="bg-black/40 border-white/10 text-white" />
            <Button data-testid="checkin-submit" onClick={() => submit()} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm"><QrCode className="w-4 h-4 mr-1" /> Check-in</Button>
          </div>
        </div>

        {last && (
          <div className="border border-[#84CC16]/40 rounded-sm bg-[#84CC16]/5 p-3 text-sm">
            <div className="text-[#84CC16] font-mono uppercase text-[10px]">Last check-in · {last.context}</div>
            <div className="text-white mt-1">{last.method} · {new Date(last.checked_in_at).toLocaleTimeString()}</div>
            {last.booking_id && <div className="text-neutral-400 text-xs font-mono">Booking {last.booking_id.slice(0, 8)}…</div>}
            {last.batch_id && <div className="text-neutral-400 text-xs font-mono">Batch {last.batch_id.slice(0, 8)}…</div>}
          </div>
        )}

        {/* Vendor QR poster */}
        <div data-testid="checkin-qr-block" className="border border-white/10 rounded-sm bg-[#141414] p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Your check-in QR poster</div>
            <Button size="sm" data-testid="checkin-print-poster" variant="ghost" onClick={() => setShowPoster(true)} className="h-7 text-[11px] text-[#06B6D4]">Print / preview</Button>
          </div>
          <div className="flex items-center gap-3">
            <img data-testid="checkin-qr-image" src={qrSrc} alt="QR poster" className="w-28 h-28 rounded-sm bg-white p-1" />
            <div className="text-xs text-neutral-400">
              Print this and mount at your reception. Customers scan it → land on your public listing page → confirm booking on their phone.
              <div className="mt-2 font-mono text-[10px] text-neutral-500 break-all">{posterUrl}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Currently on-premise list */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Currently on premises ({active.length})</div>
          <Button size="sm" variant="ghost" onClick={loadActive} className="text-[#06B6D4] h-7 px-2 text-[11px]">Refresh</Button>
        </div>
        <div className="space-y-2 max-h-[440px] overflow-auto">
          {active.length === 0 && <div className="text-neutral-500 text-xs italic">Nobody checked in right now.</div>}
          {active.map((ci) => {
            const r = remaining(ci.planned_end_at);
            return (
              <div key={ci.id} data-testid={`active-checkin-${ci.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm">{ci.customer_name}</div>
                    <div className="text-[10px] font-mono text-neutral-500">{ci.label || "Walk-in"} · in @ {new Date(ci.checked_in_at).toLocaleTimeString()}</div>
                  </div>
                  <div className={`text-[10px] font-mono uppercase tracking-widest px-2 py-1 rounded-sm ${r.warn ? "bg-[#FF3B30]/20 text-[#FF3B30] border border-[#FF3B30]/40" : "bg-black/40 text-neutral-300 border border-white/10"}`}>{r.text}</div>
                </div>
                <div className="mt-2 flex justify-end">
                  <Button size="sm" data-testid={`checkout-${ci.id}`} onClick={() => checkout(ci)} className="bg-[#84CC16] hover:bg-[#65A30D] text-black h-7 text-[11px] rounded-sm">Check out</Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Ambiguity picker */}
      <Dialog open={!!ambiguous} onOpenChange={() => setAmbiguous(null)}>
        <DialogContent className="bg-[#0c0c0c] border-white/10 text-white">
          <DialogHeader><DialogTitle>Which one is {ambiguous?.customer?.name} here for?</DialogTitle></DialogHeader>
          <p className="text-xs text-neutral-400 mb-2">Multiple active contexts found — pick one to check them in.</p>
          <div className="space-y-2 max-h-72 overflow-auto">
            {(ambiguous?.options || []).map((opt, i) => (
              <button
                key={i}
                data-testid={`checkin-opt-${opt.type}-${opt.id}`}
                onClick={() => pickOption(opt)}
                className="w-full text-left border border-white/10 rounded-sm bg-black/40 hover:bg-[#84CC16] hover:text-black transition-colors p-3"
              >
                <div className="font-mono text-[10px] uppercase tracking-widest opacity-70">{opt.type}</div>
                <div className="text-sm mt-1">{opt.label}</div>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Poster preview modal */}
      <Dialog open={showPoster} onOpenChange={() => setShowPoster(false)}>
        <DialogContent className="bg-white text-black max-w-md">
          <div className="text-center p-4">
            <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mb-2">SCAN TO CHECK IN</div>
            <div className="text-xl font-semibold mb-3">{vendor?.business_name || "Your venue"}</div>
            <img src={qrSrc.replace("280x280", "500x500")} alt="QR poster preview" className="mx-auto rounded" />
            <div className="mt-3 text-xs text-neutral-600">Powered by Kreeda Nation</div>
            <Button data-testid="poster-print-btn" onClick={() => window.print()} className="mt-4 bg-black text-white hover:bg-neutral-800">Print</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

