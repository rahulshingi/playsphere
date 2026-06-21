import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Trash2, Save, Megaphone, IndianRupee, Check, X } from "lucide-react";

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
    return <SponsorBrowseView event={event} opps={opps} accept={accept} reload={reload} />;
  }

  // ---- OWNER editor ----
  return (
    <div className="space-y-6">
      {/* Interest queue (organiser side) */}
      <OrganiserInterestQueue eventId={event.id} reload={reload} />

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

function PublicOpportunityRow({ opp, onInterest, canSponsor, hasInterest }) {
  const remaining = opp.slots_remaining ?? Math.max(0, (opp.quantity_available || 0) - (opp.sold_count || 0));
  const allSold = remaining === 0;
  const awardedNames = (opp.awarded_to || []).map((a) => a.name).filter(Boolean);
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-4 flex items-center justify-between gap-3" data-testid={`public-opp-${opp.id}`}>
      <div className="min-w-0">
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
        {awardedNames.length > 0 && (
          <div className="text-xs text-[#FACC15] font-mono mt-1">✦ Sponsored by {awardedNames.join(", ")}</div>
        )}
      </div>
      <div className="text-right shrink-0 flex flex-col items-end gap-1.5">
        <div className="font-display text-2xl">₹{(opp.price || 0).toLocaleString()}</div>
        <div className="text-[10px] font-mono uppercase text-neutral-500">qty {opp.quantity_available}</div>
        {!allSold && canSponsor && !hasInterest && (
          <Button size="sm" data-testid={`opp-interest-${opp.id}`} onClick={() => onInterest(opp)}
            className="bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm text-xs">
            I'm interested
          </Button>
        )}
        {hasInterest && (
          <span className="text-[10px] font-mono uppercase text-[#FACC15] border border-[#FACC15]/40 rounded-sm px-2 py-0.5">Interest sent · pending</span>
        )}
      </div>
    </div>
  );
}

// ---- Sponsor-side browse view: shows opps with "I'm interested" CTAs + a proposal dialog ----
function SponsorBrowseView({ event, opps, accept, reload }) {
  const { canSponsor, user } = useAuth();
  const [myInterests, setMyInterests] = useState([]);
  const [draft, setDraft] = useState(null); // { opp, message }

  const loadMine = () => {
    if (!canSponsor) return;
    api.get("/sponsorships/interests/mine").then((r) => setMyInterests(r.data)).catch(() => {});
  };
  useEffect(() => { loadMine(); }, [canSponsor, user?.id]);

  const submit = async () => {
    try {
      await api.post("/sponsorships/interests", {
        event_id: event.id,
        opportunity_id: draft.opp.id,
        proposal_message: draft.message || "",
      });
      toast.success("Interest sent — the organiser will review and respond shortly.");
      setDraft(null);
      loadMine();
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not send interest");
    }
  };

  const hasInterestFor = (oppId) =>
    myInterests.some((i) => i.event_id === event.id && i.opportunity_id === oppId && i.status === "pending");

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
      {accept && !canSponsor && (
        <div className="border border-amber-500/40 bg-amber-500/10 rounded-sm p-3 text-sm">
          <Link to="/sponsor/signup" className="text-[#FACC15] underline">Sign up as a sponsor</Link> or sign in to express interest.
        </div>
      )}
      {accept && opps.map((o) => (
        <PublicOpportunityRow key={o.id} opp={o}
          canSponsor={canSponsor}
          hasInterest={hasInterestFor(o.id)}
          onInterest={(opp) => setDraft({ opp, message: "" })} />
      ))}

      {/* Proposal dialog */}
      {draft && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6" data-testid="interest-dialog">
          <div className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-lg p-6 text-white space-y-4">
            <div className="font-display tracking-wider text-2xl">EXPRESS INTEREST</div>
            <div className="text-sm text-neutral-400">
              <strong>{draft.opp.name}</strong> · ₹{(draft.opp.price || 0).toLocaleString()} · {event.name}
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase text-neutral-500">Proposal message (optional)</Label>
              <Textarea data-testid="interest-message" rows={4} value={draft.message} placeholder="Why does this opportunity match your brand goals?"
                onChange={(e) => setDraft({ ...draft, message: e.target.value })}
                className="mt-1.5 bg-black/40 border-white/10 text-white" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" data-testid="interest-cancel" onClick={() => setDraft(null)} className="text-neutral-400">Cancel</Button>
              <Button data-testid="interest-submit" onClick={submit} className="bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm">Send interest</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Organiser-side: queue of received interests with Accept / Reject actions ----
function OrganiserInterestQueue({ eventId, reload }) {
  const [interests, setInterests] = useState([]);
  const [busyId, setBusyId] = useState(null);

  const load = () => {
    api.get(`/events/${eventId}/sponsorships/interests`).then((r) => setInterests(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, [eventId]);

  const decide = async (id, status) => {
    if (status === "rejected" && !window.confirm("Reject this sponsor's interest? They will be notified.")) return;
    if (status === "accepted" && !window.confirm("Accept this sponsor? The opportunity slot will be marked sold.")) return;
    setBusyId(id);
    try {
      await api.patch(`/sponsorships/interests/${id}`, { status });
      toast.success(status === "accepted" ? "Sponsor accepted · opportunity awarded" : "Interest rejected");
      load();
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally { setBusyId(null); }
  };

  const pending = interests.filter((i) => i.status === "pending");
  const decided = interests.filter((i) => i.status !== "pending");

  if (interests.length === 0) return null;

  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-5 space-y-3">
      <div className="font-display tracking-wider text-xl">INTEREST QUEUE ({pending.length} pending)</div>
      {pending.length === 0 && <div className="text-xs text-neutral-500">No pending interests.</div>}
      {pending.map((i) => (
        <div key={i.id} data-testid={`interest-row-${i.id}`} className="border border-[#FACC15]/30 bg-[#FACC15]/5 rounded-sm p-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <div className="font-semibold">{i.sponsor_company_name || "Anonymous sponsor"}</div>
              <span className="text-[10px] font-mono uppercase text-neutral-500">{i.sponsor_industry || "—"}</span>
              {i.sponsor_budget_range && <span className="text-[10px] font-mono uppercase text-[#FACC15]">{i.sponsor_budget_range}</span>}
            </div>
            <div className="text-xs font-mono text-neutral-400 mt-1">
              wants <span className="text-white">{i.opportunity_name}</span> · ₹{Number(i.opportunity_price || 0).toLocaleString()}
            </div>
            {i.sponsor_website && (
              <a href={i.sponsor_website} target="_blank" rel="noopener noreferrer" className="text-[10px] font-mono text-[#FACC15] hover:underline">{i.sponsor_website}</a>
            )}
            {i.proposal_message && <div className="text-xs text-neutral-300 mt-2 italic border-l-2 border-white/20 pl-2">"{i.proposal_message}"</div>}
          </div>
          <div className="flex flex-col gap-1.5 shrink-0">
            <Button size="sm" disabled={busyId === i.id} data-testid={`interest-accept-${i.id}`} onClick={() => decide(i.id, "accepted")}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
              <Check className="w-3.5 h-3.5 mr-1" /> Accept
            </Button>
            <Button size="sm" variant="outline" disabled={busyId === i.id} data-testid={`interest-reject-${i.id}`} onClick={() => decide(i.id, "rejected")}
              className="border-[#FF3B30]/40 bg-transparent text-[#FF3B30] hover:bg-[#FF3B30]/10 rounded-sm">
              <X className="w-3.5 h-3.5 mr-1" /> Reject
            </Button>
          </div>
        </div>
      ))}

      {decided.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-neutral-500 font-mono uppercase tracking-widest">/ Decided ({decided.length})</summary>
          <div className="space-y-1.5 mt-2">
            {decided.map((i) => (
              <div key={i.id} className="flex items-center justify-between text-xs font-mono border border-white/10 rounded-sm p-2 bg-black/30">
                <span>{i.sponsor_company_name} → {i.opportunity_name}</span>
                <span className={i.status === "accepted" ? "text-[#84CC16]" : "text-[#FF3B30]"}>{i.status.toUpperCase()}</span>
              </div>
            ))}
          </div>
        </details>
      )}
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
