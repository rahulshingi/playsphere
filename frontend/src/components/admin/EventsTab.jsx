import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2 } from "lucide-react";
import { SPORTS } from "@/lib/sports";
import ImageUpload from "@/components/ImageUpload";
import VenuePicker from "@/components/VenuePicker";
import SuggestVenueButton from "@/components/event/SuggestVenueButton";

const INDIVIDUAL_SPORTS = new Set(["chess", "quiz", "hackathon"]);
const BLANK_EVENT = { name: "", sport: "cricket", format: "round_robin", event_type: "playsphere_organized", description: "", venue: "", banner_url: "", stream_url: "" };
const onSportChange = (current, value) => ({
  ...current,
  sport: value,
  format: INDIVIDUAL_SPORTS.has(value) ? "knockout" : current.format,
});

export default function EventsTab({ events, companies = [], reload, canManage }) {
  const nav = useNavigate();
  const [newEvent, setNewEvent] = useState(BLANK_EVENT);
  const [venuePickerOpen, setVenuePickerOpen] = useState(false);
  // Build a quick lookup so each event row can show the organising company / organiser name
  // without an extra round-trip. PlatformAdmin already loads companies in the same fetch.
  const companyMap = Object.fromEntries((companies || []).map((c) => [c.id, c]));

  const createEvent = async (e) => {
    e.preventDefault();
    if (!newEvent.name) return toast.error("Event name required");
    try {
      await api.post("/events", newEvent);
      toast.success("Event created");
      setNewEvent(BLANK_EVENT);
      reload();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const deleteEvent = async (id, name) => {
    if (!window.confirm(`Delete ${name}? This will also delete its fixtures.`)) return;
    try {
      await api.delete(`/events/${id}`);
      toast.success("Deleted");
      reload();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="grid md:grid-cols-2 gap-6">
      <form onSubmit={createEvent} className="border border-white/10 rounded-sm p-6 bg-[#141414] space-y-3">
        <div className="font-display tracking-wider text-2xl flex items-center gap-2"><Plus className="w-4 h-4 text-[#84CC16]" /> NEW EVENT</div>
        <Input data-testid="pa-event-name" placeholder="Event name (e.g. Kreeda Nation Cricket League 2026)" value={newEvent.name} onChange={(e) => setNewEvent({ ...newEvent, name: e.target.value })} required className="bg-black/40 border-white/10 text-white" />
        <Textarea data-testid="pa-event-desc" placeholder="Description" value={newEvent.description} onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        <div className="grid grid-cols-2 gap-2">
          <Select value={newEvent.sport} onValueChange={(v) => setNewEvent(onSportChange(newEvent, v))}>
            <SelectTrigger data-testid="pa-event-sport" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              {SPORTS.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={newEvent.format} onValueChange={(v) => setNewEvent({ ...newEvent, format: v })}>
            <SelectTrigger data-testid="pa-event-format" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              <SelectItem value="round_robin">Round-robin</SelectItem>
              <SelectItem value="knockout">Knockout</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {INDIVIDUAL_SPORTS.has(newEvent.sport) && (
          <p data-testid="pa-event-format-hint" className="text-[11px] text-[#06B6D4]">
            {newEvent.sport.charAt(0).toUpperCase() + newEvent.sport.slice(1)} is an individual sport — knockout selected by default. Switch to round-robin if you want everyone to play everyone.
          </p>
        )}
        <Select value={newEvent.event_type} onValueChange={(v) => setNewEvent({ ...newEvent, event_type: v })}>
          <SelectTrigger data-testid="pa-event-type" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            <SelectItem value="playsphere_organized">Kreeda Nation organized</SelectItem>
            <SelectItem value="inter_company">Inter-company tournament</SelectItem>
            <SelectItem value="single_company">Single company tournament</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex gap-2">
          <Input data-testid="pa-event-venue" placeholder="Venue" value={newEvent.venue} onChange={(e) => setNewEvent({ ...newEvent, venue: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Button type="button" data-testid="pa-event-venue-pick" variant="outline" onClick={() => setVenuePickerOpen(true)} className="rounded-sm border-white/10 text-white whitespace-nowrap">Pick verified venue</Button>
          <SuggestVenueButton onPick={(label) => setNewEvent({ ...newEvent, venue: label })} />
        </div>
        <ImageUpload value={newEvent.banner_url} onChange={(v) => setNewEvent({ ...newEvent, banner_url: v })} testid="pa-event-banner" placeholder="Banner image — paste URL or upload" />
        <Input data-testid="pa-event-stream" placeholder="Live stream URL (YouTube / Twitch / any)" value={newEvent.stream_url} onChange={(e) => setNewEvent({ ...newEvent, stream_url: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        <Button data-testid="pa-create-event-btn" type="submit" className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Create event</Button>
        <p className="text-[10px] text-neutral-500 leading-relaxed">Once created, click <strong>Open</strong> on the event to add teams, assign captains, attach participating companies (inter-company), and add players.</p>
      </form>
      <VenuePicker open={venuePickerOpen} onClose={() => setVenuePickerOpen(false)} sport={newEvent.sport}
        onPick={(v) => setNewEvent({ ...newEvent, venue: `${v.title} · ${v.city}` })} />

      <div className="space-y-2">
        {events.length === 0 && <div className="text-neutral-500 text-sm text-center py-12 border border-dashed border-white/10 rounded-sm">No events yet.</div>}
        {events.map((e) => {
          const org = companyMap[e.company_id];
          const orgLabel = org?.name || (e.company_id ? "Unknown organiser" : "Kreeda Nation");
          return (
          <div key={e.id} data-testid={`pa-event-row-${e.id}`} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="font-semibold truncate">{e.name}</div>
              <div className="text-[11px] text-neutral-300 mt-1 flex items-center gap-1.5 truncate" data-testid={`pa-event-org-${e.id}`}>
                <span className="font-mono text-[9px] uppercase tracking-widest text-[#84CC16]">Org</span>
                <span className="truncate">{orgLabel}</span>
                {org?.type && <span className="text-[9px] font-mono uppercase text-neutral-500">· {org.type}</span>}
              </div>
              <div className="text-[10px] font-mono text-neutral-500 uppercase tracking-widest mt-0.5">
                {e.sport} · {e.format.replace("_", " ")} · {(e.event_type || "single_company").replace("_", " ")}
                {e.stream_url && <span className="ml-2 text-[#FF3B30]">● LIVE LINK</span>}
              </div>
            </div>
            <div className="flex gap-1 shrink-0">
              <Button size="sm" variant="ghost" data-testid={`pa-event-open-${e.id}`} onClick={() => nav(`/events/${e.id}`)} className="text-[#84CC16]">Open</Button>
              {canManage && <Button size="sm" variant="ghost" data-testid={`pa-event-del-${e.id}`} onClick={() => deleteEvent(e.id, e.name)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>}
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}
