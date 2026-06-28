import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2, Lock } from "lucide-react";
import DatePicker from "@/components/ui/DatePicker";
import { fmtPrice } from "@/lib/currency";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const BLANK = {
  listing_id: "", client_name: "", client_phone: "", client_email: "",
  requested_date: "", start_time: "18:00", end_time: "19:00", hours: 1,
  amount: 0, currency: "INR", notes: "",
  recurrence: "", recurrence_until: "", recurrence_days_of_week: [],
};

export default function PrivateBookingsPanel({ vendor, listings = [] }) {
  const [items, setItems] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK);
  const [busy, setBusy] = useState(false);

  const enabled = !!vendor?.offline_mode;

  const load = () => api.get("/vendor/private-bookings").then((r) => setItems(r.data || [])).catch(() => setItems([]));
  useEffect(() => { if (enabled) load(); }, [enabled]);

  const toggleDow = (i) => {
    const cur = form.recurrence_days_of_week || [];
    const next = cur.includes(i) ? cur.filter((x) => x !== i) : [...cur, i].sort();
    setForm({ ...form, recurrence_days_of_week: next });
  };

  const submit = async () => {
    if (!form.listing_id) { toast.error("Pick a listing"); return; }
    if (!form.client_name) { toast.error("Client name is required"); return; }
    if (!form.requested_date) { toast.error("Pick a date"); return; }
    setBusy(true);
    try {
      const payload = { ...form, hours: Number(form.hours) || 1, amount: Number(form.amount) || 0 };
      if (!payload.recurrence) {
        delete payload.recurrence;
        delete payload.recurrence_until;
        payload.recurrence_days_of_week = [];
      }
      await api.post("/vendor/private-bookings", payload);
      toast.success("Private booking added");
      setShowForm(false);
      setForm(BLANK);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this private booking?")) return;
    try {
      await api.delete(`/vendor/private-bookings/${id}`);
      toast.success("Deleted");
      load();
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
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">
          / Private bookings ({items.length}) <span className="text-[#06B6D4]">· offline only · clients invisible to Kreeda Nation users</span>
        </div>
        <Button data-testid="private-bookings-new" onClick={() => setShowForm(true)}
          className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
          <Plus className="w-4 h-4 mr-1" /> New booking
        </Button>
      </div>

      {showForm && (
        <div data-testid="private-bookings-form" className="border border-[#06B6D4]/40 rounded-sm bg-[#0c1414] p-4 space-y-3 mb-4">
          <div className="grid md:grid-cols-2 gap-3">
            <Field label="Listing *">
              <Select value={form.listing_id} onValueChange={(v) => setForm({ ...form, listing_id: v })}>
                <SelectTrigger data-testid="pb-listing" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Pick a listing" /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  {listings.map((L) => <SelectItem key={L.id} value={L.id}>{L.title} · {L.city}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Client name *">
              <Input data-testid="pb-client-name" value={form.client_name} onChange={(e) => setForm({ ...form, client_name: e.target.value })}
                className="bg-black/40 border-white/10 text-white" />
            </Field>
            <Field label="Client phone">
              <Input data-testid="pb-client-phone" value={form.client_phone} onChange={(e) => setForm({ ...form, client_phone: e.target.value })}
                className="bg-black/40 border-white/10 text-white" />
            </Field>
            <Field label="Client email (optional)">
              <Input data-testid="pb-client-email" value={form.client_email} onChange={(e) => setForm({ ...form, client_email: e.target.value })}
                className="bg-black/40 border-white/10 text-white" />
            </Field>
            <Field label="Date *">
              <DatePicker testid="pb-date" value={form.requested_date} onChange={(v) => setForm({ ...form, requested_date: v })} />
            </Field>
            <Field label="Hours">
              <Input data-testid="pb-hours" type="number" min={1} value={form.hours} onChange={(e) => setForm({ ...form, hours: Number(e.target.value) || 1 })}
                className="bg-black/40 border-white/10 text-white" />
            </Field>
            <Field label="Start time">
              <Input data-testid="pb-start" type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                className="bg-black/40 border-white/10 text-white" />
            </Field>
            <Field label="End time">
              <Input data-testid="pb-end" type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                className="bg-black/40 border-white/10 text-white" />
            </Field>
            <Field label="Amount (INR)">
              <Input data-testid="pb-amount" type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })}
                className="bg-black/40 border-white/10 text-white" />
            </Field>
            <Field label="Recurrence">
              <Select value={form.recurrence || "none"} onValueChange={(v) => setForm({ ...form, recurrence: v === "none" ? "" : v })}>
                <SelectTrigger data-testid="pb-recurrence" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  <SelectItem value="none">One-off</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                </SelectContent>
              </Select>
            </Field>
          </div>
          {form.recurrence === "weekly" && (
            <div className="border border-amber-500/30 bg-amber-500/5 rounded-sm p-3 space-y-2">
              <Field label="Repeat until">
                <DatePicker testid="pb-recur-until" value={form.recurrence_until} onChange={(v) => setForm({ ...form, recurrence_until: v })} />
              </Field>
              <Field label="Days of week">
                <div className="flex flex-wrap gap-1.5">
                  {DAYS.map((d, i) => (
                    <button key={d} type="button" data-testid={`pb-recur-dow-${i}`} onClick={() => toggleDow(i)}
                      className={`text-[10px] font-mono uppercase px-2 py-1 rounded-sm border ${
                        (form.recurrence_days_of_week || []).includes(i)
                          ? "bg-[#FACC15] text-black border-transparent"
                          : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
                      }`}>{d}</button>
                  ))}
                </div>
              </Field>
            </div>
          )}
          <Field label="Notes (vendor-only)">
            <Textarea data-testid="pb-notes" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="bg-black/40 border-white/10 text-white" />
          </Field>
          <div className="flex gap-2 pt-2">
            <Button data-testid="pb-submit" disabled={busy} onClick={submit}
              className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
              {busy ? "Saving…" : "Save booking"}
            </Button>
            <Button variant="ghost" onClick={() => { setShowForm(false); setForm(BLANK); }} className="text-neutral-300">Cancel</Button>
          </div>
        </div>
      )}

      {items.length === 0 && !showForm && (
        <div className="text-neutral-500 text-sm text-center py-8 border border-dashed border-white/10 rounded-sm">
          No private bookings yet. Add one to block its slot on the public calendar.
        </div>
      )}

      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((b) => (
            <div key={b.id} data-testid={`pb-row-${b.id}`} className="border border-white/10 rounded-sm bg-[#141414] px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="font-semibold flex items-center gap-2 flex-wrap">
                  {b.client_name}
                  {b.recurrence === "weekly" && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-amber-500/15 text-amber-300 border border-amber-500/40">Weekly</span>}
                </div>
                <div className="font-mono text-[10px] text-neutral-500 uppercase mt-0.5">
                  {b.requested_date} · {b.start_time}–{b.end_time} · {b.hours}h · {fmtPrice(b.amount, b.currency)}
                  {b.client_phone && <span className="ml-2 text-neutral-400">· {b.client_phone}</span>}
                </div>
              </div>
              <Button size="sm" variant="ghost" data-testid={`pb-del-${b.id}`} onClick={() => del(b.id)} className="text-[#FF3B30]">
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}
