import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { PlusCircle, MapPin } from "lucide-react";

/**
 * SuggestVenueButton — for event-create forms (HR, organiser, admin).
 * If the venue you want isn't on the platform, submit a lead so KN admin
 * can reach out for a tie-up. The selected venue name is written back
 * to the parent form via `onPick(venueLabel)` so the event still saves
 * with a useful label.
 */
export default function SuggestVenueButton({ eventId, onPick }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    venue_name: "", street: "", locality: "", city: "", state: "", pincode: "",
    contact_name: "", contact_phone: "", contact_email: "", notes: "",
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.venue_name || !form.city) { toast.error("Venue name + city are required"); return; }
    setBusy(true);
    try {
      await api.post("/venue-leads", { ...form, event_id: eventId || null });
      toast.success("Thanks! Kreeda Nation will reach out to onboard this venue.");
      const label = [form.venue_name, form.locality, form.city].filter(Boolean).join(" · ");
      onPick?.(label);
      setOpen(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to submit");
    } finally { setBusy(false); }
  };

  return (
    <>
      <Button type="button" data-testid="suggest-venue-btn" variant="outline" onClick={() => setOpen(true)}
        className="rounded-sm border-white/10 text-white whitespace-nowrap">
        <PlusCircle className="w-4 h-4 mr-1.5" /> Suggest new venue
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="suggest-venue-modal" className="bg-[#0c0c0c] border border-white/10 text-white max-w-xl">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl tracking-wide flex items-center gap-2">
              <MapPin className="w-5 h-5 text-[#84CC16]" /> Add a venue not on Kreeda Nation
            </DialogTitle>
            <DialogDescription className="text-neutral-400 text-xs">
              We&apos;ll save your event with this venue and have our team reach out to onboard them so future bookings can flow through Kreeda Nation.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-3">
            <Fld label="Venue name *" testid="sv-name" value={form.venue_name} onChange={(v) => setForm({ ...form, venue_name: v })} />
            <Fld label="City *" testid="sv-city" value={form.city} onChange={(v) => setForm({ ...form, city: v })} />
            <Fld label="Locality" testid="sv-locality" value={form.locality} onChange={(v) => setForm({ ...form, locality: v })} />
            <Fld label="State" testid="sv-state" value={form.state} onChange={(v) => setForm({ ...form, state: v })} />
            <Fld label="Pincode" testid="sv-pincode" value={form.pincode} onChange={(v) => setForm({ ...form, pincode: v })} />
            <Fld label="Street / building" testid="sv-street" value={form.street} onChange={(v) => setForm({ ...form, street: v })} />
            <Fld label="Contact name" testid="sv-cname" value={form.contact_name} onChange={(v) => setForm({ ...form, contact_name: v })} />
            <Fld label="Contact phone" testid="sv-cphone" value={form.contact_phone} onChange={(v) => setForm({ ...form, contact_phone: v })} />
            <div className="col-span-2">
              <Fld label="Contact email" testid="sv-cemail" value={form.contact_email} onChange={(v) => setForm({ ...form, contact_email: v })} />
            </div>
            <div className="col-span-2">
              <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Notes</div>
              <Textarea data-testid="sv-notes" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="mt-1 bg-black/40 border-white/10 text-white" />
            </div>
          </div>

          <div className="flex gap-2 mt-3">
            <Button data-testid="sv-submit" disabled={busy} onClick={submit}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
              {busy ? "Submitting…" : "Use this venue + notify admin"}
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)} className="text-neutral-400">Cancel</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function Fld({ label, testid, value, onChange }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
      <Input data-testid={testid} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 bg-black/40 border-white/10 text-white" />
    </div>
  );
}
