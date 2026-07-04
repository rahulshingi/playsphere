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
        <TabsContent value="checkin" className="mt-4"><CheckIn /></TabsContent>
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
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Coaches & Batches
// ─────────────────────────────────────────────────────────────
function CoachesAndBatches({ vendor, listings }) {
  const [coaches, setCoaches] = useState([]);
  const [batches, setBatches] = useState([]);
  const load = () => {
    api.get("/vendor/coaches").then((r) => setCoaches(r.data || []));
    api.get("/vendor/batches").then((r) => setBatches(r.data || []));
  };
  useEffect(load, []);
  const addCoach = async () => {
    const name = prompt("Coach name?"); if (!name) return;
    await api.post("/vendor/coaches", { name, phone: prompt("Phone?") || "", sports: (prompt("Sports (comma-sep)?") || "").split(",").map((s) => s.trim()).filter(Boolean), hourly_rate: Number(prompt("Hourly rate?") || 0) });
    toast.success("Coach added"); load();
  };
  const addBatch = async () => {
    const name = prompt("Batch name?"); if (!name) return;
    const coachId = coaches[0]?.id;
    const listingId = listings[0]?.id;
    await api.post("/vendor/batches", { name, sport: prompt("Sport?") || "", coach_id: coachId, listing_id: listingId, start_time: prompt("Start (HH:MM)?", "06:00") || "06:00", end_time: prompt("End (HH:MM)?", "07:00") || "07:00", capacity: Number(prompt("Capacity?", "20") || 20), monthly_fee: Number(prompt("Monthly fee?", "2000") || 2000) });
    toast.success("Batch added"); load();
  };
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Coaches ({coaches.length})</div>
          <Button size="sm" data-testid="obs-coach-add" onClick={addCoach} className="bg-[#EC4899] hover:bg-[#DB2777] text-white rounded-sm h-7"><Plus className="w-3 h-3 mr-1" /> New</Button>
        </div>
        <div className="space-y-1">
          {coaches.map((c) => (
            <div key={c.id} data-testid={`coach-${c.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-2 flex justify-between items-center">
              <div>
                <div className="text-sm">{c.name}</div>
                <div className="text-[10px] font-mono text-neutral-500">{c.phone} · {c.sports.join(", ")} · {fmtPrice(c.hourly_rate, "INR")}/h</div>
              </div>
              <Button size="sm" variant="ghost" onClick={async () => { await api.delete(`/vendor/coaches/${c.id}`); load(); }} className="text-[#FF3B30]"><Trash2 className="w-3 h-3" /></Button>
            </div>
          ))}
          {coaches.length === 0 && <div className="text-neutral-500 text-xs">No coaches yet.</div>}
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Batches ({batches.length})</div>
          <Button size="sm" data-testid="obs-batch-add" onClick={addBatch} disabled={coaches.length === 0} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black rounded-sm h-7"><Plus className="w-3 h-3 mr-1" /> New</Button>
        </div>
        <div className="space-y-1">
          {batches.map((b) => {
            const coachName = coaches.find((c) => c.id === b.coach_id)?.name || "—";
            return (
              <div key={b.id} data-testid={`batch-${b.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-2 flex justify-between items-center">
                <div>
                  <div className="text-sm">{b.name}</div>
                  <div className="text-[10px] font-mono text-neutral-500">{b.start_time}–{b.end_time} · coach {coachName} · {b.student_ids?.length || 0}/{b.capacity} · {fmtPrice(b.monthly_fee, "INR")}/mo</div>
                </div>
                <Button size="sm" variant="ghost" onClick={async () => { await api.delete(`/vendor/batches/${b.id}`); load(); }} className="text-[#FF3B30]"><Trash2 className="w-3 h-3" /></Button>
              </div>
            );
          })}
          {batches.length === 0 && <div className="text-neutral-500 text-xs">No batches yet — add a coach first.</div>}
        </div>
      </div>
    </div>
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
// Check-in (QR / booking-id / phone)
// ─────────────────────────────────────────────────────────────
function CheckIn() {
  const [code, setCode] = useState("");
  const [last, setLast] = useState(null);
  const submit = async () => {
    if (!code.trim()) return;
    try {
      const { data } = await api.post("/vendor/checkin", { code: code.trim(), method: "manual" });
      setLast(data); setCode(""); toast.success("Checked in");
    } catch (e) { toast.error(e.response?.data?.detail || "Not found"); }
  };
  return (
    <div className="max-w-md space-y-3">
      <div className="border border-white/10 rounded-sm bg-[#141414] p-4">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-2">/ Check-in in &lt; 5 seconds</div>
        <p className="text-xs text-neutral-400 mb-3">Scan the QR code, type the booking ID, or enter the customer&apos;s phone number.</p>
        <div className="flex gap-2">
          <Input autoFocus data-testid="checkin-code" placeholder="Booking ID or phone" value={code} onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} className="bg-black/40 border-white/10 text-white" />
          <Button data-testid="checkin-submit" onClick={submit} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm"><QrCode className="w-4 h-4 mr-1" /> Check-in</Button>
        </div>
      </div>
      {last && (
        <div className="border border-[#84CC16]/40 rounded-sm bg-[#84CC16]/5 p-3 text-sm">
          <div className="text-[#84CC16] font-mono uppercase text-[10px]">Last check-in</div>
          <div className="text-white mt-1">{last.method} · {new Date(last.checked_in_at).toLocaleTimeString()}</div>
          {last.booking_id && <div className="text-neutral-400 text-xs font-mono">Booking {last.booking_id.slice(0, 8)}…</div>}
        </div>
      )}
    </div>
  );
}
