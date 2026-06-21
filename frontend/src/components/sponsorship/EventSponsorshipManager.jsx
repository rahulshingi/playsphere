import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Trash2, Save, Megaphone, IndianRupee } from "lucide-react";

const REQS_FIELDS = [
  { key: "expected_reach", label: "Expected reach", type: "number", placeholder: "50000" },
  { key: "expected_participants", label: "Expected participants", type: "number", placeholder: "600" },
  { key: "target_audience", label: "Target audience description", type: "textarea", placeholder: "Mid-senior IT professionals…" },
  { key: "player_demographics", label: "Player demographics", type: "text", placeholder: "25-45 yrs, 60% male 40% female" },
  { key: "company_demographics", label: "Company demographics", type: "text", placeholder: "50+ IT companies, 5000+ employees" },
  { key: "social_media_reach", label: "Social media reach", type: "number", placeholder: "100000" },
  { key: "livestream_views", label: "Livestream expected views", type: "number", placeholder: "20000" },
  { key: "venue_location", label: "Venue location", type: "text", placeholder: "Bangalore" },
  { key: "event_category", label: "Event category", type: "text", placeholder: "Corporate Sports / Family Day" },
  { key: "brochure_url", label: "Sponsorship brochure URL (optional)", type: "text", placeholder: "https://…" },
];

const OPP_TYPES = ["title", "associate", "best-batsman", "best-bowler", "streaming", "boundary", "powered-by", "category-partner", "other"];

export default function EventSponsorshipManager({ event, canManage, reload }) {
  const [opps, setOpps] = useState(event.sponsorship_opportunities || []);
  const [reqs, setReqs] = useState(event.sponsorship_requirements || {});
  const [accept, setAccept] = useState(!!event.accept_sponsorships);
  const [agree, setAgree] = useState(!!event.data_share_agreement);
  const [busy, setBusy] = useState(false);
  const [newOpp, setNewOpp] = useState({ name: "", type: "associate", price: "", quantity_available: 1, benefits: "" });

  useEffect(() => {
    setOpps(event.sponsorship_opportunities || []);
    setReqs(event.sponsorship_requirements || {});
    setAccept(!!event.accept_sponsorships);
    setAgree(!!event.data_share_agreement);
  }, [event.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveSettings = async () => {
    if (accept && !agree) return toast.error("You must agree to share event data with sponsors before going live");
    setBusy(true);
    try {
      await api.patch(`/events/${event.id}`, {
        accept_sponsorships: accept,
        sponsorship_requirements: reqs,
        data_share_agreement: agree,
      });
      toast.success("Sponsorship settings saved");
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const addOpp = async () => {
    if (!newOpp.name.trim()) return toast.error("Opportunity name required");
    try {
      await api.post(`/events/${event.id}/sponsorships`, {
        ...newOpp,
        price: Number(newOpp.price) || 0,
        quantity_available: Number(newOpp.quantity_available) || 1,
      });
      toast.success("Opportunity added");
      setNewOpp({ name: "", type: "associate", price: "", quantity_available: 1, benefits: "" });
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const updateOpp = async (id, patch) => {
    try {
      await api.patch(`/events/${event.id}/sponsorships/${id}`, patch);
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const removeOpp = async (id) => {
    if (!window.confirm("Remove this sponsorship opportunity?")) return;
    try {
      await api.delete(`/events/${event.id}/sponsorships/${id}`);
      toast.success("Removed");
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  // ---- READ-ONLY view (non-owners or organiser who hasn't enabled marketplace yet) ----
  if (!canManage) {
    return (
      <div className="space-y-3">
        {!accept && (
          <div className="text-neutral-500 text-center py-12 border border-dashed border-white/10 rounded-sm">
            The organiser has not enabled sponsorship for this event yet.
          </div>
        )}
        {accept && opps.length === 0 && (
          <div className="text-neutral-500 text-center py-12 border border-dashed border-white/10 rounded-sm">
            Sponsorships are accepted, but no opportunities listed yet — check back soon.
          </div>
        )}
        {accept && opps.map((o) => <PublicOpportunityRow key={o.id} opp={o} />)}
      </div>
    );
  }

  // ---- OWNER editor ----
  return (
    <div className="space-y-6">
      {/* Toggle + requirements */}
      <div className="border border-white/10 rounded-sm bg-[#141414] p-5 space-y-4">
        <div className="font-display tracking-wider text-2xl flex items-center gap-2"><Megaphone className="w-5 h-5 text-[#FACC15]" /> SPONSORSHIP MARKETPLACE</div>

        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" data-testid="event-accept-sponsorships" checked={accept} onChange={(e) => setAccept(e.target.checked)} className="accent-[#FACC15] w-4 h-4" />
          <span className="font-semibold">Accept sponsorships for this event</span>
        </label>

        {accept && (
          <>
            <div className="grid md:grid-cols-2 gap-3 pt-2">
              {REQS_FIELDS.map((f) => (
                <div key={f.key} className={f.type === "textarea" ? "md:col-span-2" : ""}>
                  <Label className="text-[10px] font-mono uppercase text-neutral-500">{f.label}</Label>
                  {f.type === "textarea" ? (
                    <Textarea data-testid={`event-reqs-${f.key}`} rows={2} value={reqs[f.key] || ""} placeholder={f.placeholder}
                      onChange={(e) => setReqs({ ...reqs, [f.key]: e.target.value })} className="mt-1.5 bg-black/40 border-white/10 text-white" />
                  ) : (
                    <Input data-testid={`event-reqs-${f.key}`} type={f.type} value={reqs[f.key] ?? ""} placeholder={f.placeholder}
                      onChange={(e) => setReqs({ ...reqs, [f.key]: f.type === "number" ? (e.target.value === "" ? null : Number(e.target.value)) : e.target.value })}
                      className="mt-1.5 bg-black/40 border-white/10 text-white" />
                  )}
                </div>
              ))}
            </div>

            <label className="flex items-start gap-2 text-xs cursor-pointer pt-2 border-t border-white/10">
              <input type="checkbox" data-testid="event-data-share-agreement" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="accent-[#FACC15] w-4 h-4 mt-0.5" />
              <span>I agree to share event data and participant information with sponsors who agree to sponsor this event. <span className="text-amber-400">This must be checked before the listing goes live.</span></span>
            </label>
          </>
        )}

        <Button data-testid="event-sponsorship-save" disabled={busy} onClick={saveSettings}
          className="bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm">
          <Save className="w-4 h-4 mr-1" /> {busy ? "Saving…" : "Save sponsorship settings"}
        </Button>
      </div>

      {/* Opportunities list */}
      {accept && (
        <div className="border border-white/10 rounded-sm bg-[#141414] p-5 space-y-3">
          <div className="font-display tracking-wider text-xl">OPPORTUNITIES ({opps.length})</div>
          {opps.length === 0 && <div className="text-xs text-neutral-500">No opportunities yet. Add your first below.</div>}
          {opps.map((o) => (
            <OwnerOpportunityRow key={o.id} opp={o} onSave={(patch) => updateOpp(o.id, patch)} onRemove={() => removeOpp(o.id)} />
          ))}

          <div className="border-t border-white/10 pt-4 mt-4">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15] mb-2">/ Add new opportunity</div>
            <div className="grid md:grid-cols-12 gap-2">
              <Input data-testid="new-opp-name" placeholder="Title Sponsor" value={newOpp.name} onChange={(e) => setNewOpp({ ...newOpp, name: e.target.value })} className="md:col-span-3 bg-black/40 border-white/10 text-white" />
              <select data-testid="new-opp-type" value={newOpp.type} onChange={(e) => setNewOpp({ ...newOpp, type: e.target.value })} className="md:col-span-2 bg-black/40 border border-white/10 rounded-sm px-2 text-white text-sm">
                {OPP_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <div className="md:col-span-2 relative">
                <IndianRupee className="w-3.5 h-3.5 absolute left-2 top-2.5 text-neutral-500" />
                <Input data-testid="new-opp-price" type="number" placeholder="Price" value={newOpp.price} onChange={(e) => setNewOpp({ ...newOpp, price: e.target.value })} className="pl-7 bg-black/40 border-white/10 text-white" />
              </div>
              <Input data-testid="new-opp-qty" type="number" min={1} placeholder="Qty" value={newOpp.quantity_available} onChange={(e) => setNewOpp({ ...newOpp, quantity_available: e.target.value })} className="md:col-span-1 bg-black/40 border-white/10 text-white" />
              <Input data-testid="new-opp-benefits" placeholder="Benefits (e.g. Top logo placement)" value={newOpp.benefits} onChange={(e) => setNewOpp({ ...newOpp, benefits: e.target.value })} className="md:col-span-3 bg-black/40 border-white/10 text-white" />
              <Button data-testid="new-opp-add" onClick={addOpp} className="md:col-span-1 bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm">
                <Plus className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PublicOpportunityRow({ opp }) {
  const remaining = opp.slots_remaining ?? Math.max(0, (opp.quantity_available || 0) - (opp.sold_count || 0));
  const allSold = remaining === 0;
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-4 flex items-center justify-between gap-3">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="font-semibold">{opp.name}</div>
          <span className="text-[10px] font-mono uppercase text-neutral-500">{opp.type}</span>
          {allSold ? (
            <span className="text-[10px] font-mono uppercase text-[#FF3B30] border border-[#FF3B30]/40 rounded-sm px-1.5 py-0.5">SOLD</span>
          ) : (
            <span className="text-[10px] font-mono uppercase text-[#84CC16] border border-[#84CC16]/40 rounded-sm px-1.5 py-0.5">AVAILABLE · {remaining} slot{remaining === 1 ? "" : "s"}</span>
          )}
        </div>
        {opp.benefits && <div className="text-xs text-neutral-400 mt-1">{opp.benefits}</div>}
        {(opp.awarded_to_name) && (
          <div className="text-xs text-[#FACC15] font-mono mt-1">✦ Sponsored by {opp.awarded_to_name}</div>
        )}
      </div>
      <div className="text-right shrink-0">
        <div className="font-display text-2xl">₹{(opp.price || 0).toLocaleString()}</div>
        <div className="text-[10px] font-mono uppercase text-neutral-500">qty {opp.quantity_available}</div>
      </div>
    </div>
  );
}

function OwnerOpportunityRow({ opp, onSave, onRemove }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ ...opp });
  const remaining = Math.max(0, (opp.quantity_available || 0) - (opp.sold_count || 0));
  if (editing) {
    return (
      <div className="border border-[#FACC15]/40 rounded-sm bg-black/30 p-3">
        <div className="grid md:grid-cols-12 gap-2">
          <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className="md:col-span-3 bg-black/40 border-white/10 text-white" />
          <select value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value })} className="md:col-span-2 bg-black/40 border border-white/10 rounded-sm px-2 text-white text-sm">
            {OPP_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <Input type="number" value={draft.price} onChange={(e) => setDraft({ ...draft, price: Number(e.target.value) })} className="md:col-span-2 bg-black/40 border-white/10 text-white" />
          <Input type="number" min={1} value={draft.quantity_available} onChange={(e) => setDraft({ ...draft, quantity_available: Number(e.target.value) })} className="md:col-span-1 bg-black/40 border-white/10 text-white" />
          <Input value={draft.benefits || ""} onChange={(e) => setDraft({ ...draft, benefits: e.target.value })} className="md:col-span-3 bg-black/40 border-white/10 text-white" />
          <div className="md:col-span-1 flex gap-1">
            <Button size="sm" data-testid={`opp-save-${opp.id}`} onClick={() => { onSave(draft); setEditing(false); }} className="bg-[#84CC16] text-black font-semibold rounded-sm">Save</Button>
          </div>
        </div>
        <Button size="sm" variant="ghost" onClick={() => setEditing(false)} className="text-neutral-400 mt-2">Cancel</Button>
      </div>
    );
  }
  return (
    <div data-testid={`opp-row-${opp.id}`} className="border border-white/10 rounded-sm p-3 bg-black/20 flex items-center justify-between gap-3">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="font-semibold">{opp.name}</div>
          <span className="text-[10px] font-mono uppercase text-neutral-500">{opp.type}</span>
          <span className="text-[10px] font-mono uppercase text-[#84CC16]">{remaining}/{opp.quantity_available} slots available</span>
        </div>
        {opp.benefits && <div className="text-xs text-neutral-400 mt-1">{opp.benefits}</div>}
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <div className="font-display text-lg">₹{(opp.price || 0).toLocaleString()}</div>
        <Button size="sm" variant="ghost" data-testid={`opp-edit-${opp.id}`} onClick={() => setEditing(true)} className="text-[#84CC16]">Edit</Button>
        <Button size="sm" variant="ghost" data-testid={`opp-del-${opp.id}`} onClick={onRemove} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
      </div>
    </div>
  );
}
