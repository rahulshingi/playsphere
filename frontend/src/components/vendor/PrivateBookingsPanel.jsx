import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Plus, Trash2, Lock, Receipt, CheckCircle2, User, Pencil, CalendarDays, ChevronLeft, ChevronRight, MessageCircle } from "lucide-react";
import DatePicker from "@/components/ui/DatePicker";
import { fmtPrice } from "@/lib/currency";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const BLANK_BOOKING = {
  listing_id: "", customer_id: "", client_name: "", client_phone: "", client_email: "",
  requested_date: "", start_time: "18:00", end_time: "19:00", hours: 1,
  rate_type: "total", rate_per_hour: 0, amount: 0, currency: "INR", notes: "",
  recurrence: "", recurrence_until: "", recurrence_days_of_week: [],
};
const BLANK_CUSTOMER = { name: "", phone: "", email: "", address: "", gstin: "", notes: "" };

// Add whole hours to a HH:MM string. Wraps at 24h (returns "24:00" as sentinel
// so the caller can flag it if needed; we clamp to 23:59 for display).
function addHours(hhmm, hours) {
  if (!hhmm || !/^\d{2}:\d{2}$/.test(hhmm)) return hhmm;
  const [h, m] = hhmm.split(":").map(Number);
  let total = h * 60 + m + Number(hours || 0) * 60;
  if (total >= 24 * 60) total = 24 * 60 - 1; // clamp to 23:59
  const nh = Math.floor(total / 60);
  const nm = total % 60;
  return `${String(nh).padStart(2, "0")}:${String(nm).padStart(2, "0")}`;
}

export default function PrivateBookingsPanel({ vendor, listings = [] }) {
  const [bookings, setBookings] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [showBooking, setShowBooking] = useState(false);
  const [showCustomer, setShowCustomer] = useState(false);
  const [previewInvoice, setPreviewInvoice] = useState(null);
  const [form, setForm] = useState(BLANK_BOOKING);
  const [editingId, setEditingId] = useState(null);
  const [custForm, setCustForm] = useState(BLANK_CUSTOMER);
  const [busy, setBusy] = useState(false);

  const enabled = !!vendor?.offline_mode;

  const reload = () => {
    if (!enabled) return;
    // Merge offline (private) + platform (marketplace) bookings so the
    // vendor's calendar shows every occupied slot — matching the "block the
    // time on my calendar" expectation. Marketplace rows are tagged with a
    // `source` marker so we can render them read-only in the calendar.
    Promise.all([
      api.get("/vendor/private-bookings").then((r) => (r.data || []).map((b) => ({ ...b, source: "offline" }))).catch(() => []),
      api.get("/vendor-bookings").then((r) => (r.data || [])
        // Ignore cancelled/rejected marketplace slots — the time is freed up.
        .filter((b) => !["cancelled", "rejected"].includes(b.status))
        .map((b) => ({
          ...b,
          source: "platform",
          client_name: b.company_name || "Platform booking",
          amount: b.total,
          status: b.status === "completed" ? "completed" : "active",
        }))).catch(() => []),
    ]).then(([offline, platform]) => setBookings([...offline, ...platform]));
    api.get("/vendor/customers").then((r) => setCustomers(r.data || [])).catch(() => setCustomers([]));
    api.get("/vendor/invoices").then((r) => setInvoices(r.data || [])).catch(() => setInvoices([]));
  };
  useEffect(reload, [enabled]);

  const active = bookings.filter((b) => b.status === "active");
  const completed = bookings.filter((b) => b.status === "completed");

  // Auto-adjust end_time whenever start_time OR hours change in the dialog.
  useEffect(() => {
    if (!showBooking) return;
    const suggested = addHours(form.start_time, form.hours);
    if (suggested && suggested !== form.end_time) {
      setForm((f) => ({ ...f, end_time: suggested }));
    }
    // We deliberately only react to start_time + hours changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.start_time, form.hours, showBooking]);

  // Derive amount when rate_type=hourly
  const computedAmount = useMemo(() => {
    if (form.rate_type === "hourly") return Number(form.rate_per_hour || 0) * Number(form.hours || 0);
    return Number(form.amount || 0);
  }, [form.rate_type, form.rate_per_hour, form.hours, form.amount]);

  const openNew = () => { setEditingId(null); setForm(BLANK_BOOKING); setShowBooking(true); };
  const openEdit = (b) => {
    setEditingId(b.id);
    setForm({
      listing_id: b.listing_id || "",
      customer_id: b.customer_id || "",
      client_name: b.client_name || "",
      client_phone: b.client_phone || "",
      client_email: b.client_email || "",
      requested_date: b.requested_date || "",
      start_time: b.start_time || "18:00",
      end_time: b.end_time || "19:00",
      hours: b.hours || 1,
      rate_type: b.rate_type || "total",
      rate_per_hour: b.rate_per_hour || 0,
      amount: b.amount || 0,
      currency: b.currency || "INR",
      notes: b.notes || "",
      recurrence: b.recurrence || "",
      recurrence_until: b.recurrence_until || "",
      recurrence_days_of_week: b.recurrence_days_of_week || [],
    });
    setShowBooking(true);
  };

  const submitBooking = async () => {
    if (!form.listing_id) return toast.error("Pick a listing");
    if (!form.client_name && !form.customer_id) return toast.error("Pick a customer or type a name");
    if (!form.requested_date) return toast.error("Pick a start date");
    if (form.recurrence === "weekly") {
      if (!form.recurrence_until) return toast.error("Weekly recurrence needs an end date");
      if (form.recurrence_until <= form.requested_date) return toast.error("End date must be after start date");
      if (!form.recurrence_days_of_week.length) return toast.error("Pick at least one day of the week");
    }
    setBusy(true);
    try {
      const payload = { ...form, hours: Number(form.hours) || 1, amount: computedAmount };
      if (form.customer_id) {
        const c = customers.find((x) => x.id === form.customer_id);
        if (c) { payload.client_name = c.name; payload.client_phone = c.phone; payload.client_email = c.email; }
      }
      if (!payload.recurrence) { payload.recurrence = null; payload.recurrence_until = null; payload.recurrence_days_of_week = []; }
      if (editingId) {
        await api.patch(`/vendor/private-bookings/${editingId}`, payload);
        toast.success("Booking updated");
      } else {
        await api.post("/vendor/private-bookings", payload);
        toast.success("Booking added");
      }
      setShowBooking(false); setEditingId(null); setForm(BLANK_BOOKING); reload();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const submitCustomer = async () => {
    if (!custForm.name) return toast.error("Name is required");
    setBusy(true);
    try {
      await api.post("/vendor/customers", custForm);
      toast.success("Customer added");
      setShowCustomer(false); setCustForm(BLANK_CUSTOMER); reload();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const markCompleted = async (b) => {
    try {
      await api.patch(`/vendor/private-bookings/${b.id}`, { status: "completed" });
      toast.success("Marked completed");
      reload();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const deleteBooking = async (id) => {
    if (!window.confirm("Delete this booking?")) return;
    try { await api.delete(`/vendor/private-bookings/${id}`); toast.success("Deleted"); reload(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const generateInvoice = async (b) => {
    if (b.invoice_id) {
      const inv = invoices.find((i) => i.id === b.invoice_id);
      if (inv) { setPreviewInvoice(inv); return; }
    }
    try {
      const { data } = await api.post("/vendor/invoices", { booking_id: b.id });
      toast.success(`Invoice ${data.invoice_number} generated`);
      reload();
      setPreviewInvoice(data);
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const deleteCustomer = async (id) => {
    if (!window.confirm("Delete this customer?")) return;
    try { await api.delete(`/vendor/customers/${id}`); reload(); }
    catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const markInvoicePaid = async (inv) => {
    try {
      const { data } = await api.post(`/vendor/invoices/${inv.id}/mark-paid`);
      toast.success("Marked paid");
      setPreviewInvoice(data); reload();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  if (!enabled) {
    return (
      <div data-testid="private-bookings-locked" className="mt-10 border border-dashed border-white/15 rounded-sm p-8 text-center bg-black/30">
        <Lock className="w-6 h-6 text-neutral-500 mx-auto mb-2" />
        <div className="text-neutral-300">Private bookings are part of offline-mode.</div>
        <div className="text-xs text-neutral-500 mt-1">Subscribe above to manage your offline client roster.</div>
      </div>
    );
  }

  return (
    <div data-testid="private-bookings-panel" className="mt-10">
      <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">
        / Offline business · <span className="text-[#06B6D4]">clients invisible to Kreeda Nation users</span>
      </div>

      <Tabs defaultValue="active">
        <TabsList data-testid="pb-tabs" className="bg-black/40 border border-white/10 rounded-sm">
          <TabsTrigger data-testid="pb-tab-active" value="active" className="data-[state=active]:bg-[#06B6D4] data-[state=active]:text-black rounded-sm">Active ({active.length})</TabsTrigger>
          <TabsTrigger data-testid="pb-tab-completed" value="completed" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">Completed ({completed.length})</TabsTrigger>
          <TabsTrigger data-testid="pb-tab-calendar" value="calendar" className="data-[state=active]:bg-[#A855F7] data-[state=active]:text-white rounded-sm">Calendar</TabsTrigger>
          <TabsTrigger data-testid="pb-tab-customers" value="customers" className="data-[state=active]:bg-[#EC4899] data-[state=active]:text-white rounded-sm">Customers ({customers.length})</TabsTrigger>
          <TabsTrigger data-testid="pb-tab-invoices" value="invoices" className="data-[state=active]:bg-[#FACC15] data-[state=active]:text-black rounded-sm">Invoices ({invoices.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="active" className="mt-4">
          <Button data-testid="pb-new-booking" onClick={openNew} className="mb-3 bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
            <Plus className="w-4 h-4 mr-1" /> New booking
          </Button>
          <BookingList items={active} vendor={vendor} onEdit={openEdit} onComplete={markCompleted} onInvoice={generateInvoice} onDelete={deleteBooking} />
        </TabsContent>

        <TabsContent value="completed" className="mt-4">
          <BookingList items={completed} vendor={vendor} onInvoice={generateInvoice} onDelete={deleteBooking} />
        </TabsContent>

        <TabsContent value="calendar" className="mt-4">
          <BookingsCalendar bookings={bookings} listings={listings} onEdit={openEdit} />
        </TabsContent>

        <TabsContent value="customers" className="mt-4">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <Button data-testid="pb-new-customer" onClick={() => setShowCustomer(true)} className="bg-[#EC4899] hover:bg-[#db2777] text-white font-semibold rounded-sm">
              <Plus className="w-4 h-4 mr-1" /> New customer
            </Button>
            <a
              data-testid="pb-cust-export"
              href={`${process.env.REACT_APP_BACKEND_URL}/api/vendor/customers.csv`}
              className="inline-flex items-center gap-1 h-9 px-3 rounded-sm bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold text-sm"
            >
              Export CSV ({customers.length})
            </a>
          </div>
          {customers.length === 0 ? (
            <div className="text-neutral-500 text-sm text-center py-8 border border-dashed border-white/10 rounded-sm">No customers yet.</div>
          ) : (
            <div className="space-y-2">
              {customers.map((c) => (
                <div key={c.id} data-testid={`pb-cust-${c.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-3 flex items-start justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="font-semibold flex items-center gap-2"><User className="w-4 h-4 text-[#EC4899]" />{c.name}</div>
                    <div className="text-xs text-neutral-400 mt-0.5">{[c.phone, c.email].filter(Boolean).join(" · ")}</div>
                    {c.gstin && <div className="text-[10px] font-mono text-neutral-500 mt-0.5">GSTIN: {c.gstin}</div>}
                    {c.address && <div className="text-xs text-neutral-500 mt-0.5">{c.address}</div>}
                  </div>
                  <Button size="sm" variant="ghost" data-testid={`pb-cust-del-${c.id}`} onClick={() => deleteCustomer(c.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></Button>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="invoices" className="mt-4">
          {invoices.length === 0 ? (
            <div className="text-neutral-500 text-sm text-center py-8 border border-dashed border-white/10 rounded-sm">No invoices generated yet. Generate one from any booking.</div>
          ) : (
            <div className="space-y-2">
              {invoices.map((i) => (
                <div key={i.id} data-testid={`pb-inv-${i.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-3 flex items-center justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="font-semibold flex items-center gap-2 flex-wrap">
                      <Receipt className="w-4 h-4 text-[#FACC15]" />{i.invoice_number}
                      <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm ${i.status === "paid" ? "bg-[#84CC16]/20 text-[#84CC16]" : "bg-amber-500/20 text-amber-400"}`}>{i.status}</span>
                    </div>
                    <div className="text-xs text-neutral-400 mt-0.5">{i.customer_snapshot?.name} · {fmtPrice(i.total, i.currency)} · {i.issued_at?.slice(0, 10)}</div>
                  </div>
                  <Button size="sm" variant="outline" data-testid={`pb-inv-view-${i.id}`} onClick={() => setPreviewInvoice(i)} className="rounded-sm border-white/10 text-white">View</Button>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Booking form dialog */}
      <Dialog open={showBooking} onOpenChange={(v) => { setShowBooking(v); if (!v) { setEditingId(null); } }}>
        <DialogContent data-testid="pb-booking-form" className="bg-[#0c0c0c] border-white/10 text-white max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display text-2xl tracking-wide">{editingId ? "Edit offline booking" : "New offline booking"}</DialogTitle></DialogHeader>
          <div className="grid md:grid-cols-2 gap-3">
            <Fld label="Listing *">
              <Select value={form.listing_id} onValueChange={(v) => setForm({ ...form, listing_id: v })}>
                <SelectTrigger data-testid="pb-listing" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Pick a listing" /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  {listings.map((L) => <SelectItem key={L.id} value={L.id}>{L.title} · {L.city}</SelectItem>)}
                </SelectContent>
              </Select>
            </Fld>
            <Fld label="Customer">
              <Select value={form.customer_id || "walkin"} onValueChange={(v) => setForm({ ...form, customer_id: v === "walkin" ? "" : v })}>
                <SelectTrigger data-testid="pb-customer" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  <SelectItem value="walkin">Walk-in (enter below)</SelectItem>
                  {customers.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}{c.phone ? ` · ${c.phone}` : ""}</SelectItem>)}
                </SelectContent>
              </Select>
            </Fld>
            {!form.customer_id && (
              <>
                <Fld label="Client name *">
                  <Input data-testid="pb-client-name" value={form.client_name} onChange={(e) => setForm({ ...form, client_name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                </Fld>
                <Fld label="Client phone">
                  <Input data-testid="pb-client-phone" value={form.client_phone} onChange={(e) => setForm({ ...form, client_phone: e.target.value })} className="bg-black/40 border-white/10 text-white" />
                </Fld>
              </>
            )}
            <Fld label="Start date *"><DatePicker testid="pb-date" value={form.requested_date} onChange={(v) => setForm({ ...form, requested_date: v })} /></Fld>
            <Fld label="Hours"><Input data-testid="pb-hours" type="number" min={1} value={form.hours} onChange={(e) => setForm({ ...form, hours: Number(e.target.value) || 1 })} className="bg-black/40 border-white/10 text-white" /></Fld>
            <Fld label="Start time"><Input data-testid="pb-start" type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
            <Fld label="End time"><Input data-testid="pb-end" type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
            <Fld label="Charge as">
              <Select value={form.rate_type} onValueChange={(v) => setForm({ ...form, rate_type: v })}>
                <SelectTrigger data-testid="pb-rate-type" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  <SelectItem value="total">Flat total amount</SelectItem>
                  <SelectItem value="hourly">Rate per hour (auto × hours)</SelectItem>
                </SelectContent>
              </Select>
            </Fld>
            {form.rate_type === "hourly" ? (
              <Fld label="Rate per hour (₹) *">
                <Input data-testid="pb-rate" type="number" min={0} value={form.rate_per_hour} onChange={(e) => setForm({ ...form, rate_per_hour: Number(e.target.value) || 0 })} className="bg-black/40 border-white/10 text-white" />
              </Fld>
            ) : (
              <Fld label="Total amount (₹) *">
                <Input data-testid="pb-amount" type="number" min={0} value={form.amount} onChange={(e) => setForm({ ...form, amount: Number(e.target.value) || 0 })} className="bg-black/40 border-white/10 text-white" />
              </Fld>
            )}
          </div>
          <div className="text-sm text-neutral-300">Total to charge: <span className="font-display text-2xl text-[#84CC16] ml-1">{fmtPrice(computedAmount, "INR")}</span></div>
          <Fld label="Recurrence">
            <Select value={form.recurrence || "none"} onValueChange={(v) => setForm({ ...form, recurrence: v === "none" ? "" : v })}>
              <SelectTrigger data-testid="pb-recurrence" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                <SelectItem value="none">One-off</SelectItem>
                <SelectItem value="weekly">Weekly (repeats until end date)</SelectItem>
              </SelectContent>
            </Select>
          </Fld>
          {form.recurrence === "weekly" && (
            <div className="border border-amber-500/30 bg-amber-500/5 rounded-sm p-3 space-y-3">
              <Fld label="Repeat until (end date) *"><DatePicker testid="pb-recur-until" value={form.recurrence_until} onChange={(v) => setForm({ ...form, recurrence_until: v })} /></Fld>
              <Fld label="Days of week *">
                <div className="flex flex-wrap gap-1.5">
                  {DAYS.map((d, i) => (
                    <button key={d} type="button" data-testid={`pb-recur-dow-${i}`}
                      onClick={() => setForm({ ...form, recurrence_days_of_week: form.recurrence_days_of_week.includes(i) ? form.recurrence_days_of_week.filter((x) => x !== i) : [...form.recurrence_days_of_week, i].sort() })}
                      className={`text-[10px] font-mono uppercase px-2 py-1 rounded-sm border ${form.recurrence_days_of_week.includes(i) ? "bg-[#FACC15] text-black border-transparent" : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"}`}>{d}</button>
                  ))}
                </div>
              </Fld>
            </div>
          )}
          <Fld label="Notes (vendor-only)"><Textarea data-testid="pb-notes" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
          <div className="flex gap-2 pt-2">
            <Button data-testid="pb-submit" disabled={busy} onClick={submitBooking} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">{busy ? "Saving…" : editingId ? "Update booking" : "Save booking"}</Button>
            <Button variant="ghost" onClick={() => { setShowBooking(false); setEditingId(null); }} className="text-neutral-300">Cancel</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Customer form */}
      <Dialog open={showCustomer} onOpenChange={setShowCustomer}>
        <DialogContent data-testid="pb-customer-form" className="bg-[#0c0c0c] border-white/10 text-white max-w-lg">
          <DialogHeader><DialogTitle className="font-display text-2xl tracking-wide">New customer</DialogTitle></DialogHeader>
          <div className="grid md:grid-cols-2 gap-3">
            <Fld label="Name *"><Input data-testid="pb-cust-name" value={custForm.name} onChange={(e) => setCustForm({ ...custForm, name: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
            <Fld label="Phone"><Input data-testid="pb-cust-phone" value={custForm.phone} onChange={(e) => setCustForm({ ...custForm, phone: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
            <Fld label="Email"><Input data-testid="pb-cust-email" value={custForm.email} onChange={(e) => setCustForm({ ...custForm, email: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
            <Fld label="GSTIN"><Input data-testid="pb-cust-gstin" value={custForm.gstin} onChange={(e) => setCustForm({ ...custForm, gstin: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
            <div className="md:col-span-2"><Fld label="Address"><Textarea data-testid="pb-cust-address" rows={2} value={custForm.address} onChange={(e) => setCustForm({ ...custForm, address: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld></div>
          </div>
          <div className="flex gap-2 pt-2">
            <Button data-testid="pb-cust-submit" disabled={busy} onClick={submitCustomer} className="bg-[#EC4899] hover:bg-[#db2777] text-white font-semibold rounded-sm">{busy ? "Saving…" : "Save customer"}</Button>
            <Button variant="ghost" onClick={() => setShowCustomer(false)} className="text-neutral-300">Cancel</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Invoice preview */}
      {previewInvoice && <InvoicePreview inv={previewInvoice} onClose={() => setPreviewInvoice(null)} onMarkPaid={() => markInvoicePaid(previewInvoice)} />}
    </div>
  );
}

function BookingList({ items, onEdit, onComplete, onInvoice, onDelete, vendor }) {
  if (items.length === 0) return <div className="text-neutral-500 text-sm text-center py-8 border border-dashed border-white/10 rounded-sm">No bookings here yet.</div>;
  return (
    <div className="space-y-2">
      {items.map((b) => (
        <div key={b.id} data-testid={`pb-row-${b.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-3 flex items-center justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="font-semibold flex items-center gap-2 flex-wrap">
              {b.client_name}
              {b.recurrence === "weekly" && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-amber-500/15 text-amber-300 border border-amber-500/40">Weekly · till {b.recurrence_until}</span>}
              {b.invoice_id && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#FACC15]/15 text-[#FACC15] border border-[#FACC15]/40">Invoiced</span>}
            </div>
            <div className="font-mono text-[10px] text-neutral-500 uppercase mt-0.5">
              {b.requested_date} · {b.start_time}–{b.end_time} · {b.hours}h · {fmtPrice(b.amount, b.currency)}
              {b.client_phone && <span className="ml-2 text-neutral-400">· {b.client_phone}</span>}
            </div>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {onEdit && <Button size="sm" variant="outline" data-testid={`pb-edit-${b.id}`} onClick={() => onEdit(b)} className="border-white/10 text-white bg-transparent rounded-sm"><Pencil className="w-3.5 h-3.5 mr-1" /> Edit</Button>}
            {b.client_phone && (
              <Button size="sm" data-testid={`pb-whatsapp-${b.id}`}
                onClick={() => shareBookingOnWhatsApp(b, vendor)}
                title="Send booking confirmation on WhatsApp"
                className="bg-[#25D366] hover:bg-[#1EBE5D] text-black rounded-sm">
                <MessageCircle className="w-3.5 h-3.5 mr-1" /> WhatsApp
              </Button>
            )}
            {onComplete && <Button size="sm" data-testid={`pb-complete-${b.id}`} onClick={() => onComplete(b)} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm"><CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Complete</Button>}
            <Button size="sm" data-testid={`pb-invoice-${b.id}`} onClick={() => onInvoice(b)} className="bg-[#FACC15] hover:bg-[#eab308] text-black rounded-sm"><Receipt className="w-3.5 h-3.5 mr-1" /> {b.invoice_id ? "View invoice" : "Generate invoice"}</Button>
            <Button size="sm" variant="ghost" data-testid={`pb-del-${b.id}`} onClick={() => onDelete(b.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></Button>
          </div>
        </div>
      ))}
    </div>
  );
}

// -------------------------------------------------------------------------
// WhatsApp share helpers — client-only wa.me deep-links, no keys needed.
// Strips non-digits from the phone (wa.me requires country code + digits only).
// If phone is blank we still return a wa.me link with no recipient — WhatsApp
// Web will then open the "New chat" picker.
// -------------------------------------------------------------------------
function normalisePhoneForWa(phone) {
  const digits = (phone || "").replace(/\D+/g, "");
  // If it looks like a 10-digit Indian number, prepend country code 91.
  if (digits.length === 10 && !digits.startsWith("91")) return `91${digits}`;
  return digits;
}

function shareBookingOnWhatsApp(b, vendor) {
  const biz = vendor?.invoice_business_name || vendor?.business_name || "our venue";
  const lines = [
    `Hi ${b.client_name}, this is a booking confirmation from ${biz}.`,
    ``,
    `📅 Date: ${b.requested_date}`,
    `⏰ Time: ${b.start_time}–${b.end_time} (${b.hours || 1}h)`,
    b.amount ? `💰 Amount: ${fmtPrice(b.amount, b.currency)}` : null,
    b.recurrence === "weekly" && b.recurrence_until ? `🔁 Recurs weekly till ${b.recurrence_until}` : null,
    b.notes ? `📝 ${b.notes}` : null,
    ``,
    `See you then! — ${biz}`,
  ].filter(Boolean).join("\n");
  const url = `https://wa.me/${normalisePhoneForWa(b.client_phone)}?text=${encodeURIComponent(lines)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

function shareInvoiceOnWhatsApp(inv) {
  const bizName = inv.vendor_snapshot?.business_name || "our venue";
  const to = inv.customer_snapshot?.name || "there";
  const phone = inv.customer_snapshot?.phone || "";
  const lines = [
    `Hi ${to}, invoice ${inv.invoice_number} from ${bizName}.`,
    ``,
    ...(inv.line_items || []).map((li) => `• ${li.description} — ${fmtPrice(li.amount, inv.currency)}`),
    ``,
    `Subtotal: ${fmtPrice(inv.subtotal, inv.currency)}`,
    `Tax (${inv.tax_percent}%): ${fmtPrice(inv.tax_amount, inv.currency)}`,
    `Total: ${fmtPrice(inv.total, inv.currency)}`,
    `Status: ${(inv.status || "").toUpperCase()}`,
    ``,
    inv.vendor_snapshot?.footer_note || `Thanks for your business — ${bizName}`,
  ].join("\n");
  const url = `https://wa.me/${normalisePhoneForWa(phone)}?text=${encodeURIComponent(lines)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

// -------------------------------------------------------------------------
// Monthly calendar view — coloured cells for booked/available days.
// Weekly recurrences are expanded on the fly for the visible month.
// -------------------------------------------------------------------------
function BookingsCalendar({ bookings, listings, onEdit }) {
  const today = new Date();
  const [cursor, setCursor] = useState({ y: today.getFullYear(), m: today.getMonth() });
  const [listingId, setListingId] = useState(listings[0]?.id || "");

  const year = cursor.y;
  const month = cursor.m; // 0-based
  const monthStart = new Date(year, month, 1);
  const monthEnd = new Date(year, month + 1, 0);
  const daysInMonth = monthEnd.getDate();
  // Sunday-first grid → convert JS 0=Sun into Mon-first index
  const firstWeekday = (monthStart.getDay() + 6) % 7; // 0=Mon

  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

  const inMonthBookings = useMemo(() => {
    const startIso = iso(monthStart);
    const endIso = iso(monthEnd);
    const list = bookings.filter((b) => !listingId || b.listing_id === listingId);
    // Map: date -> [bookings]
    const map = {};
    for (const b of list) {
      if (!b.requested_date) continue;
      if (b.recurrence === "weekly" && b.recurrence_until) {
        // Expand into every matching day within the visible month.
        const startDate = new Date(b.requested_date + "T00:00:00");
        const endDate = new Date(b.recurrence_until + "T23:59:59");
        const dows = new Set((b.recurrence_days_of_week || []).map((n) => Number(n)));
        const from = new Date(Math.max(monthStart, startDate));
        const to = new Date(Math.min(monthEnd, endDate));
        for (let d = new Date(from); d <= to; d.setDate(d.getDate() + 1)) {
          const dow = (d.getDay() + 6) % 7; // 0=Mon
          if (dows.size === 0 || dows.has(dow)) {
            const k = iso(d);
            (map[k] ||= []).push(b);
          }
        }
      } else if (b.requested_date >= startIso && b.requested_date <= endIso) {
        (map[b.requested_date] ||= []).push(b);
      }
    }
    return map;
  }, [bookings, listingId, year, month]); // eslint-disable-line react-hooks/exhaustive-deps

  const goto = (delta) => {
    const m = month + delta;
    if (m < 0) setCursor({ y: year - 1, m: 11 });
    else if (m > 11) setCursor({ y: year + 1, m: 0 });
    else setCursor({ y: year, m });
  };

  const cells = [];
  for (let i = 0; i < firstWeekday; i++) cells.push({ blank: true });
  for (let d = 1; d <= daysInMonth; d++) {
    const dateIso = iso(new Date(year, month, d));
    cells.push({ d, dateIso, items: inMonthBookings[dateIso] || [] });
  }
  while (cells.length % 7 !== 0) cells.push({ blank: true });

  const monthName = monthStart.toLocaleString("en-US", { month: "long", year: "numeric" });
  const todayIso = iso(today);

  return (
    <div data-testid="pb-calendar" className="border border-white/10 rounded-sm bg-[#0c0c0c] p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" data-testid="pb-cal-prev" onClick={() => goto(-1)} className="text-neutral-300"><ChevronLeft className="w-4 h-4" /></Button>
          <div className="font-display text-lg tracking-wide flex items-center gap-2"><CalendarDays className="w-4 h-4 text-[#A855F7]" /> {monthName}</div>
          <Button size="sm" variant="ghost" data-testid="pb-cal-next" onClick={() => goto(1)} className="text-neutral-300"><ChevronRight className="w-4 h-4" /></Button>
        </div>
        <div className="flex items-center gap-2">
          <Select value={listingId || "all"} onValueChange={(v) => setListingId(v === "all" ? "" : v)}>
            <SelectTrigger data-testid="pb-cal-listing" className="bg-black/40 border-white/10 text-white h-8 text-xs w-56"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              <SelectItem value="all">All listings</SelectItem>
              {listings.map((L) => <SelectItem key={L.id} value={L.id}>{L.title}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-1 text-[10px] font-mono uppercase text-neutral-500 mb-1">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} className="text-center py-1">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((c, i) => (
          <div key={i} data-testid={c.dateIso ? `pb-cal-cell-${c.dateIso}` : undefined}
            className={`min-h-[80px] rounded-sm p-1.5 border ${
              c.blank ? "border-transparent" :
              c.dateIso === todayIso ? "border-[#A855F7] bg-[#A855F7]/10" :
              c.items.length ? "border-[#06B6D4]/40 bg-[#06B6D4]/5" : "border-white/5 bg-black/30"
            }`}>
            {!c.blank && (
              <>
                <div className="text-[11px] font-mono text-neutral-400 flex items-center justify-between">
                  <span>{c.d}</span>
                  {c.items.length > 0 && <span className="text-[9px] px-1 rounded bg-[#06B6D4] text-black">{c.items.length}</span>}
                </div>
                <div className="mt-1 space-y-0.5">
                  {c.items.slice(0, 3).map((b, idx) => {
                    const platform = b.source === "platform";
                    return (
                      <button key={`${b.id}-${idx}`}
                        onClick={() => !platform && onEdit?.(b)}
                        disabled={platform}
                        data-testid={`pb-cal-item-${c.dateIso}-${idx}`}
                        title={`${b.start_time}–${b.end_time} · ${b.client_name}${platform ? " · platform (read-only)" : ""}`}
                        className={`w-full text-left truncate text-[10px] px-1 py-0.5 rounded-sm font-mono ${
                          platform ? "bg-[#FACC15]/20 text-[#FACC15] border border-[#FACC15]/40 cursor-not-allowed" :
                          b.status === "completed" ? "bg-[#84CC16]/20 text-[#84CC16]" :
                          b.status === "cancelled" ? "bg-neutral-800 text-neutral-500 line-through" :
                          "bg-[#06B6D4]/25 text-[#67e8f9]"
                        }`}
                      >{platform ? "\u25CF " : ""}{b.start_time} {b.client_name.slice(0, 10)}</button>
                    );
                  })}
                  {c.items.length > 3 && <div className="text-[9px] font-mono text-neutral-500">+{c.items.length - 3} more</div>}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-3 text-[10px] font-mono uppercase text-neutral-500 flex-wrap">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#06B6D4]/25 border border-[#06B6D4]/40"></span> Active</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#84CC16]/20"></span> Completed</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#FACC15]/20 border border-[#FACC15]/40"></span> Platform (read-only)</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#A855F7]/20 border border-[#A855F7]"></span> Today</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-black border border-white/10"></span> Available</span>
      </div>
    </div>
  );
}

function InvoicePreview({ inv, onClose, onMarkPaid }) {
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent data-testid="pb-invoice-preview" className="bg-white text-black max-w-2xl max-h-[90vh] overflow-y-auto print:shadow-none">
        <div id="print-invoice" className="p-6 text-sm">
          <div className="flex items-start justify-between border-b pb-3">
            <div>
              <div className="font-bold text-2xl">{inv.vendor_snapshot?.business_name}</div>
              {inv.vendor_snapshot?.gstin && <div className="text-xs mt-0.5">GSTIN: {inv.vendor_snapshot.gstin}</div>}
              <div className="text-xs mt-0.5 whitespace-pre-line">{inv.vendor_snapshot?.address}</div>
              <div className="text-xs mt-0.5">{[inv.vendor_snapshot?.phone, inv.vendor_snapshot?.email].filter(Boolean).join(" · ")}</div>
            </div>
            <div className="text-right">
              <div className="font-bold text-lg">TAX INVOICE</div>
              <div className="text-xs">#{inv.invoice_number}</div>
              <div className="text-xs">Issued: {inv.issued_at?.slice(0, 10)}</div>
              <div className={`text-xs mt-1 inline-block px-2 py-0.5 rounded ${inv.status === "paid" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{inv.status.toUpperCase()}</div>
            </div>
          </div>
          <div className="mt-3">
            <div className="text-xs uppercase text-gray-500">Bill to</div>
            <div className="font-semibold">{inv.customer_snapshot?.name}</div>
            <div className="text-xs">{[inv.customer_snapshot?.phone, inv.customer_snapshot?.email].filter(Boolean).join(" · ")}</div>
            {inv.customer_snapshot?.gstin && <div className="text-xs">GSTIN: {inv.customer_snapshot.gstin}</div>}
            {inv.customer_snapshot?.address && <div className="text-xs whitespace-pre-line">{inv.customer_snapshot.address}</div>}
          </div>
          <table className="w-full mt-4 text-xs">
            <thead className="border-b border-gray-300"><tr className="text-left"><th className="py-1">Description</th><th className="text-right">Hours</th><th className="text-right">Rate</th><th className="text-right">Amount</th></tr></thead>
            <tbody>
              {inv.line_items.map((li, i) => (<tr key={i} className="border-b border-gray-200"><td className="py-1.5">{li.description}</td><td className="text-right">{li.hours}</td><td className="text-right">{fmtPrice(li.rate, inv.currency)}</td><td className="text-right">{fmtPrice(li.amount, inv.currency)}</td></tr>))}
            </tbody>
          </table>
          <div className="mt-3 flex justify-end">
            <div className="w-64 text-xs space-y-1">
              <div className="flex justify-between"><span>Subtotal</span><span>{fmtPrice(inv.subtotal, inv.currency)}</span></div>
              <div className="flex justify-between"><span>Tax ({inv.tax_percent}%)</span><span>{fmtPrice(inv.tax_amount, inv.currency)}</span></div>
              <div className="flex justify-between font-bold text-base border-t border-gray-300 pt-1"><span>TOTAL</span><span>{fmtPrice(inv.total, inv.currency)}</span></div>
            </div>
          </div>
          {inv.notes && <div className="mt-4 text-xs italic text-gray-600">Note: {inv.notes}</div>}
          {inv.vendor_snapshot?.footer_note && <div className="mt-4 text-[10px] text-gray-500 border-t pt-2">{inv.vendor_snapshot.footer_note}</div>}
        </div>
        <div className="flex gap-2 justify-end p-3 print:hidden">
          {inv.customer_snapshot?.phone && (
            <Button data-testid="pb-invoice-whatsapp" onClick={() => shareInvoiceOnWhatsApp(inv)}
              className="bg-[#25D366] hover:bg-[#1EBE5D] text-black rounded-sm">
              <MessageCircle className="w-4 h-4 mr-1" /> WhatsApp
            </Button>
          )}
          {inv.status !== "paid" && <Button data-testid="pb-invoice-mark-paid" onClick={onMarkPaid} className="bg-[#84CC16] text-black rounded-sm">Mark paid</Button>}
          <Button data-testid="pb-invoice-print" onClick={() => window.print()} className="bg-black text-white rounded-sm">Print / PDF</Button>
          <Button variant="ghost" onClick={onClose} className="text-neutral-700">Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Fld({ label, children }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}
