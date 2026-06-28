import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Plus, Trash2, X } from "lucide-react";
import { todayLocalISO, minTimeForDate, validateFutureDateTime } from "@/lib/dateConstraints";

const HOURS_24 = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, "0")}:00`);

export default function VenueScheduleEditor({ listing, onClose }) {
  const [schedule, setSchedule] = useState(null);
  const [subUnits, setSubUnits] = useState([]);
  const [newSub, setNewSub] = useState({ name: "", capacity: "" });
  const [blocks, setBlocks] = useState([]);
  const [newBlock, setNewBlock] = useState({ date: "", start_time: "", end_time: "", reason: "" });

  const load = async () => {
    const [s, u, b] = await Promise.all([
      api.get(`/vendor-listings/${listing.id}/schedule`),
      api.get(`/vendor-listings/${listing.id}/sub-units`),
      api.get(`/vendor-listings/${listing.id}/blocks`),
    ]);
    setSchedule(s.data);
    setSubUnits(u.data);
    setBlocks(b.data);
  };
  useEffect(() => { load(); }, [listing.id]);

  const saveSchedule = async () => {
    try {
      await api.patch(`/vendor-listings/${listing.id}/schedule`, schedule);
      toast.success("Schedule saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const addSub = async () => {
    if (!newSub.name) return toast.error("Name required");
    await api.post(`/vendor-listings/${listing.id}/sub-units`, newSub);
    setNewSub({ name: "", capacity: "" });
    load();
  };
  const delSub = async (sid) => {
    if (!window.confirm("Delete this sub-unit?")) return;
    await api.delete(`/vendor-listings/${listing.id}/sub-units/${sid}`);
    load();
  };
  const addBlock = async () => {
    if (!(newBlock.date && newBlock.start_time && newBlock.end_time)) return toast.error("Date + start + end required");
    const err = validateFutureDateTime(newBlock.date, newBlock.start_time);
    if (err) return toast.error(err);
    if (newBlock.end_time <= newBlock.start_time) return toast.error("End time must be after start time");
    await api.post(`/vendor-listings/${listing.id}/blocks`, newBlock);
    setNewBlock({ date: "", start_time: "", end_time: "", reason: "" });
    load();
  };
  const delBlock = async (bid) => {
    await api.delete(`/vendor-listings/${listing.id}/blocks/${bid}`);
    load();
  };

  const togglePeakHour = (h) => {
    const cur = new Set(schedule.peak_hours || []);
    if (cur.has(h)) cur.delete(h); else cur.add(h);
    setSchedule({ ...schedule, peak_hours: Array.from(cur).sort() });
  };

  if (!schedule) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6" onClick={onClose}>
      <div data-testid="venue-schedule-editor" className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-3xl my-10 text-white" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#06B6D4]">/ Venue management</div>
            <h2 className="font-display text-2xl tracking-wider">SCHEDULE — {listing.title}</h2>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-white"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-8">
          {/* OPENING HOURS + SLOT + PRICING */}
          <section>
            <h3 className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">Opening hours &amp; pricing</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div><Label className="text-xs uppercase font-mono text-neutral-500">Opens</Label>
                <Select value={schedule.opening_time} onValueChange={(v) => setSchedule({ ...schedule, opening_time: v })}>
                  <SelectTrigger data-testid="vs-opening" className="bg-black/40 border-white/10 text-white mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10 max-h-[260px]">{HOURS_24.map((h) => <SelectItem key={h} value={h}>{h}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label className="text-xs uppercase font-mono text-neutral-500">Closes</Label>
                <Select value={schedule.closing_time} onValueChange={(v) => setSchedule({ ...schedule, closing_time: v })}>
                  <SelectTrigger data-testid="vs-closing" className="bg-black/40 border-white/10 text-white mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10 max-h-[260px]">{HOURS_24.map((h) => <SelectItem key={h} value={h}>{h}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label className="text-xs uppercase font-mono text-neutral-500">Slot length (min)</Label>
                <Select value={String(schedule.slot_minutes)} onValueChange={(v) => setSchedule({ ...schedule, slot_minutes: Number(v) })}>
                  <SelectTrigger data-testid="vs-slot-mins" className="bg-black/40 border-white/10 text-white mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    {[30, 60, 90, 120].map((n) => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
                  </SelectContent>
                </Select></div>
              <div><Label className="text-xs uppercase font-mono text-neutral-500">Peak +</Label>
                <Input data-testid="vs-peak-factor" type="number" step="0.05" value={schedule.peak_price_factor} onChange={(e) => setSchedule({ ...schedule, peak_price_factor: Number(e.target.value) })} className="mt-1 bg-black/40 border-white/10 text-white" /></div>
              <div className="col-span-2"><Label className="text-xs uppercase font-mono text-neutral-500">Weekend +</Label>
                <Input data-testid="vs-weekend-factor" type="number" step="0.05" value={schedule.weekend_price_factor} onChange={(e) => setSchedule({ ...schedule, weekend_price_factor: Number(e.target.value) })} className="mt-1 bg-black/40 border-white/10 text-white" /></div>
            </div>
            <div className="mt-4">
              <Label className="text-xs uppercase font-mono text-neutral-500">Peak hours (toggle)</Label>
              <div className="mt-2 flex flex-wrap gap-1">
                {HOURS_24.map((h) => (
                  <button key={h} data-testid={`vs-peak-${h.replace(":", "")}`} onClick={() => togglePeakHour(h)}
                    className={`text-[10px] font-mono px-2 py-1 rounded-sm border ${(schedule.peak_hours || []).includes(h) ? "bg-[#F59E0B] text-black border-[#F59E0B]" : "bg-black/40 text-neutral-400 border-white/10"}`}>
                    {h}
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-4"><Label className="text-xs uppercase font-mono text-neutral-500">Amenities</Label>
              <Input data-testid="vs-amenities" value={(schedule.amenities || []).join(", ")} onChange={(e) => setSchedule({ ...schedule, amenities: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} className="mt-1 bg-black/40 border-white/10 text-white" placeholder="parking, washroom, lights, equipment, changing room" /></div>

            <HappyHoursEditor schedule={schedule} setSchedule={setSchedule} />

            <Button data-testid="vs-save" onClick={saveSchedule} className="mt-4 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save schedule</Button>
          </section>

          {/* SUB-UNITS */}
          <section>
            <h3 className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">Sub-units (Turf A / Court 1 / etc.)</h3>
            <div className="space-y-2 mb-3">
              {subUnits.length === 0 && <div className="text-xs text-neutral-600">No sub-units yet. Use them when your venue has multiple bookable courts/turfs.</div>}
              {subUnits.map((s) => (
                <div key={s.id} data-testid={`sub-unit-${s.id}`} className="flex items-center justify-between border border-white/10 rounded-sm px-3 py-2 bg-black/30">
                  <div><span className="font-semibold">{s.name}</span>{s.capacity ? <span className="ml-2 text-[10px] font-mono text-neutral-500">cap {s.capacity}</span> : null}</div>
                  <button onClick={() => delSub(s.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Input data-testid="sub-unit-name" placeholder="e.g. Turf A" value={newSub.name} onChange={(e) => setNewSub({ ...newSub, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
              <Input data-testid="sub-unit-cap" placeholder="Capacity" type="number" value={newSub.capacity} onChange={(e) => setNewSub({ ...newSub, capacity: Number(e.target.value) })} className="bg-black/40 border-white/10 text-white w-32" />
              <Button data-testid="sub-unit-add" onClick={addSub} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black rounded-sm">Add</Button>
            </div>
          </section>

          {/* BLOCKS */}
          <section>
            <h3 className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">Block dates / times</h3>
            <div className="space-y-2 mb-3">
              {blocks.length === 0 && <div className="text-xs text-neutral-600">No blocks. Use this when you&apos;re closed for maintenance, tournaments etc.</div>}
              {blocks.map((b) => (
                <div key={b.id} data-testid={`block-${b.id}`} className="flex items-center justify-between border border-white/10 rounded-sm px-3 py-2 bg-black/30">
                  <div><span className="font-mono">{b.date}</span> · {b.start_time}–{b.end_time} {b.reason && <span className="text-neutral-400 italic ml-2">— {b.reason}</span>}</div>
                  <button onClick={() => delBlock(b.id)} className="text-[#FF3B30]"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-4 gap-2">
              <Input data-testid="block-date" type="date" min={todayLocalISO()} value={newBlock.date} onChange={(e) => setNewBlock({ ...newBlock, date: e.target.value })} className="bg-black/40 border-white/10 text-white" />
              <Input data-testid="block-start" type="time" min={minTimeForDate(newBlock.date)} value={newBlock.start_time} onChange={(e) => setNewBlock({ ...newBlock, start_time: e.target.value })} className="bg-black/40 border-white/10 text-white" />
              <Input data-testid="block-end" type="time" min={newBlock.start_time || undefined} value={newBlock.end_time} onChange={(e) => setNewBlock({ ...newBlock, end_time: e.target.value })} className="bg-black/40 border-white/10 text-white" />
              <Input data-testid="block-reason" placeholder="Reason" value={newBlock.reason} onChange={(e) => setNewBlock({ ...newBlock, reason: e.target.value })} className="bg-black/40 border-white/10 text-white" />
            </div>
            <Button data-testid="block-add" onClick={addBlock} className="mt-2 bg-[#FF3B30] hover:bg-[#DC2626] text-white rounded-sm">Add block</Button>
          </section>
        </div>
      </div>
    </div>
  );
}

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function HappyHoursEditor({ schedule, setSchedule }) {
  const hh = schedule.happy_hours || [];
  const update = (next) => setSchedule({ ...schedule, happy_hours: next });
  const add = () => update([...hh, { label: "Happy Hour", days: [], start: "12:00", end: "16:00", factor: 0.8 }]);
  const remove = (idx) => update(hh.filter((_, i) => i !== idx));
  const patch = (idx, key, value) => update(hh.map((h, i) => (i === idx ? { ...h, [key]: value } : h)));
  const toggleDay = (idx, day) => {
    const set = new Set(hh[idx].days || []);
    if (set.has(day)) set.delete(day);
    else set.add(day);
    patch(idx, "days", Array.from(set).sort());
  };

  return (
    <div className="mt-5 border border-[#A855F7]/30 rounded-sm p-4 bg-[#A855F7]/5">
      <div className="flex items-center justify-between">
        <Label className="text-xs uppercase font-mono text-[#A855F7]">Happy hours (discounts)</Label>
        <Button data-testid="hh-add" type="button" onClick={add} size="sm" className="bg-[#A855F7] hover:bg-[#9333EA] text-white rounded-sm">
          <Plus className="w-3 h-3 mr-1" /> Add window
        </Button>
      </div>
      {hh.length === 0 && (
        <div className="text-xs text-neutral-500 mt-2">No happy hour windows. Add discounted off-peak slots to boost utilization.</div>
      )}
      <div className="space-y-2 mt-3">
        {hh.map((h, idx) => (
          <div key={`hh-${idx}`} data-testid={`hh-row-${idx}`} className="border border-white/10 rounded-sm p-3 bg-black/30">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 items-end">
              <div>
                <Label className="text-[10px] font-mono text-neutral-500">Label</Label>
                <Input data-testid={`hh-label-${idx}`} value={h.label} onChange={(e) => patch(idx, "label", e.target.value)} className="mt-1 bg-black/40 border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-[10px] font-mono text-neutral-500">Start</Label>
                <Input data-testid={`hh-start-${idx}`} type="time" value={h.start} onChange={(e) => patch(idx, "start", e.target.value)} className="mt-1 bg-black/40 border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-[10px] font-mono text-neutral-500">End</Label>
                <Input data-testid={`hh-end-${idx}`} type="time" value={h.end} onChange={(e) => patch(idx, "end", e.target.value)} className="mt-1 bg-black/40 border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-[10px] font-mono text-neutral-500">Factor (e.g. 0.7 = 30% off)</Label>
                <Input data-testid={`hh-factor-${idx}`} type="number" step="0.05" min="0" value={h.factor} onChange={(e) => patch(idx, "factor", Number(e.target.value))} className="mt-1 bg-black/40 border-white/10 text-white" />
              </div>
              <button data-testid={`hh-remove-${idx}`} type="button" onClick={() => remove(idx)} className="text-[#FF3B30] justify-self-end">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
            <div className="mt-3">
              <Label className="text-[10px] font-mono text-neutral-500">Days (leave all unselected to apply every day)</Label>
              <div className="flex flex-wrap gap-1 mt-1">
                {DAY_LABELS.map((label, di) => {
                  const on = (h.days || []).includes(di);
                  return (
                    <button key={label} data-testid={`hh-day-${idx}-${di}`} type="button"
                      onClick={() => toggleDay(idx, di)}
                      className={`text-[10px] font-mono px-2 py-1 rounded-sm border ${on ? "bg-[#A855F7] text-white border-[#A855F7]" : "bg-black/40 text-neutral-400 border-white/10"}`}>
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
