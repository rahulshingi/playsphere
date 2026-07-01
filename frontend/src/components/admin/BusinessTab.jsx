import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CheckCircle2, XCircle, Clock, Sparkles, MapPin, Phone, Mail, FileText, Store } from "lucide-react";
import { fmtPrice } from "@/lib/currency";

const SUB_STATUS = {
  pending_payment: { label: "Pending", color: "bg-amber-500 text-black", icon: Clock },
  active: { label: "Active", color: "bg-[#84CC16] text-black", icon: CheckCircle2 },
  expired: { label: "Expired", color: "bg-neutral-500 text-white", icon: XCircle },
  cancelled: { label: "Cancelled", color: "bg-[#FF3B30] text-white", icon: XCircle },
};

const LEAD_STATUS_OPTIONS = ["open", "contacted", "converted", "archived"];

/**
 * BusinessTab — Platform Admin tab for the Phase 5A + 5C admin workflows:
 *   1. Offline-mode subscription requests from vendors — activate / reject.
 *   2. Venue leads submitted by HR / organiser / admin during event create —
 *      admin follows up + updates status + notes.
 */
export default function BusinessTab({ onQueueChange }) {
  const [subs, setSubs] = useState([]);
  const [leads, setLeads] = useState([]);

  const loadSubs = () => api.get("/admin/offline-subscriptions").then((r) => setSubs(r.data || [])).catch(() => setSubs([]));
  const loadLeads = () => api.get("/admin/venue-leads").then((r) => setLeads(r.data || [])).catch(() => setLeads([]));

  useEffect(() => { loadSubs(); loadLeads(); }, []);

  const activateSub = async (s) => {
    try {
      await api.post(`/admin/offline-subscriptions/${s.id}/activate`);
      toast.success("Subscription activated — vendor's offline mode is now unlocked");
      loadSubs();
      onQueueChange?.();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const rejectSub = async (s) => {
    const reason = window.prompt("Reason for rejection (shown to vendor):", "Payment not received");
    if (reason === null) return;
    try {
      await api.post(`/admin/offline-subscriptions/${s.id}/reject`, { reason });
      toast.success("Request rejected");
      loadSubs();
      onQueueChange?.();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const updateLead = async (l, patch) => {
    try {
      await api.patch(`/admin/venue-leads/${l.id}`, patch);
      toast.success("Lead updated");
      loadLeads();
      onQueueChange?.();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const pendingSubs = subs.filter((s) => s.status === "pending_payment");
  const otherSubs = subs.filter((s) => s.status !== "pending_payment");
  const openLeads = leads.filter((l) => l.status === "open");
  const otherLeads = leads.filter((l) => l.status !== "open");

  return (
    <div className="space-y-10">
      {/* Offline subscriptions */}
      <section data-testid="pa-business-subs">
        <div className="flex items-baseline justify-between flex-wrap gap-2 mb-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Vendor offline-mode subscriptions</div>
            <h2 className="font-display text-2xl tracking-wide mt-1">Offline-mode Requests {pendingSubs.length > 0 && <span className="text-amber-400 text-base">· {pendingSubs.length} pending</span>}</h2>
          </div>
          <div className="text-xs text-neutral-500">Vendors pay Kreeda Nation to unlock private-booking tools. Activate below once you receive their offline payment.</div>
        </div>

        {subs.length === 0 && (
          <EmptyState icon={Sparkles} text="No offline subscription requests yet." />
        )}

        {pendingSubs.length > 0 && (
          <div className="space-y-2 mb-4">
            {pendingSubs.map((s) => <SubRow key={s.id} s={s} onActivate={() => activateSub(s)} onReject={() => rejectSub(s)} />)}
          </div>
        )}

        {otherSubs.length > 0 && (
          <details data-testid="pa-business-subs-history">
            <summary className="text-xs text-neutral-500 cursor-pointer font-mono uppercase tracking-widest mb-2">/ History ({otherSubs.length})</summary>
            <div className="space-y-2 mt-2">
              {otherSubs.map((s) => <SubRow key={s.id} s={s} />)}
            </div>
          </details>
        )}
      </section>

      {/* Venue leads */}
      <section data-testid="pa-business-leads">
        <div className="flex items-baseline justify-between flex-wrap gap-2 mb-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Venue leads</div>
            <h2 className="font-display text-2xl tracking-wide mt-1">Suggested Venues {openLeads.length > 0 && <span className="text-[#06B6D4] text-base">· {openLeads.length} open</span>}</h2>
          </div>
          <div className="text-xs text-neutral-500">HR / organisers add venues that aren&apos;t yet on the platform. Reach out to onboard them.</div>
        </div>

        {leads.length === 0 && (
          <EmptyState icon={MapPin} text="No venue leads yet." />
        )}

        {openLeads.length > 0 && (
          <div className="space-y-2 mb-4">
            {openLeads.map((l) => <LeadRow key={l.id} l={l} onUpdate={(p) => updateLead(l, p)} />)}
          </div>
        )}

        {otherLeads.length > 0 && (
          <details data-testid="pa-business-leads-history">
            <summary className="text-xs text-neutral-500 cursor-pointer font-mono uppercase tracking-widest mb-2">/ History ({otherLeads.length})</summary>
            <div className="space-y-2 mt-2">
              {otherLeads.map((l) => <LeadRow key={l.id} l={l} onUpdate={(p) => updateLead(l, p)} />)}
            </div>
          </details>
        )}
      </section>
    </div>
  );
}

function EmptyState({ icon: Icon, text }) {
  return (
    <div className="text-center py-10 border border-dashed border-white/10 rounded-sm">
      <Icon className="w-6 h-6 text-neutral-500 mx-auto mb-2" />
      <div className="text-neutral-400 text-sm">{text}</div>
    </div>
  );
}

function SubRow({ s, onActivate, onReject }) {
  const meta = SUB_STATUS[s.status] || SUB_STATUS.pending_payment;
  const Icon = meta.icon;
  return (
    <div data-testid={`pa-sub-${s.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="font-semibold flex items-center gap-2 flex-wrap">
            <Store className="w-4 h-4 text-[#06B6D4]" />
            {s.vendor_email || s.vendor_id}
          </div>
          <div className="font-mono text-[10px] text-neutral-500 uppercase mt-1">
            {s.plan_type} · {fmtPrice(s.amount, s.currency)} · {s.payment_method}
            {s.expires_at && ` · expires ${s.expires_at.slice(0, 10)}`}
          </div>
          {s.cancelled_reason && <div className="text-xs text-[#FF3B30]/90 mt-1">Cancelled: {s.cancelled_reason}</div>}
        </div>
        <Badge className={`${meta.color} text-[10px] font-mono uppercase tracking-widest rounded-sm shrink-0`}>
          <Icon className="w-3 h-3 mr-1" /> {meta.label}
        </Badge>
      </div>
      {s.status === "pending_payment" && onActivate && (
        <div className="flex gap-2 mt-3">
          <Button data-testid={`pa-sub-activate-${s.id}`} size="sm" onClick={onActivate}
            className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Activate (payment received)
          </Button>
          <Button data-testid={`pa-sub-reject-${s.id}`} size="sm" variant="ghost" onClick={onReject} className="text-[#FF3B30]">
            <XCircle className="w-3.5 h-3.5 mr-1" /> Reject
          </Button>
        </div>
      )}
    </div>
  );
}

function LeadRow({ l, onUpdate }) {
  const [notes, setNotes] = useState(l.admin_notes || "");
  const [saving, setSaving] = useState(false);

  const saveNotes = async () => {
    setSaving(true);
    await onUpdate({ admin_notes: notes });
    setSaving(false);
  };

  return (
    <div data-testid={`pa-lead-${l.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="font-semibold flex items-center gap-2 flex-wrap">
            <MapPin className="w-4 h-4 text-[#84CC16]" /> {l.venue_name}
          </div>
          <div className="text-xs text-neutral-400 mt-1">
            {[l.street, l.locality, l.city, l.state, l.pincode].filter(Boolean).join(", ")}
          </div>
          <div className="flex flex-wrap gap-3 mt-2 text-[11px] text-neutral-400">
            {l.contact_name && <span>{l.contact_name}</span>}
            {l.contact_phone && <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{l.contact_phone}</span>}
            {l.contact_email && <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{l.contact_email}</span>}
          </div>
          {l.notes && <div className="text-xs text-neutral-500 italic mt-2 flex items-start gap-1"><FileText className="w-3 h-3 mt-0.5 shrink-0" />&ldquo;{l.notes}&rdquo;</div>}
          <div className="text-[10px] font-mono text-neutral-600 mt-2">
            Submitted by <b className="text-neutral-400">{l.submitted_by_email || l.submitted_by_user_id}</b> ({l.submitted_by_role}) · {l.created_at?.slice(0, 10)}
          </div>
        </div>
        <div className="shrink-0">
          <Select value={l.status} onValueChange={(v) => onUpdate({ status: v })}>
            <SelectTrigger data-testid={`pa-lead-status-${l.id}`} className="bg-black/40 border-white/10 text-white text-xs w-36 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              {LEAD_STATUS_OPTIONS.map((v) => <SelectItem key={v} value={v} className="capitalize">{v}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="mt-3">
        <Textarea data-testid={`pa-lead-notes-${l.id}`} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
          placeholder="Admin notes (e.g., Called owner, meeting scheduled)…"
          className="bg-black/40 border-white/10 text-white text-xs" />
        <Button size="sm" data-testid={`pa-lead-save-${l.id}`} disabled={saving || notes === (l.admin_notes || "")} onClick={saveNotes}
          className="mt-2 bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
          {saving ? "Saving…" : "Save notes"}
        </Button>
      </div>
    </div>
  );
}
