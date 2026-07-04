import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CheckCircle2, XCircle, Clock, Sparkles, MapPin, Phone, Mail, FileText, Store, PauseCircle, PlayCircle } from "lucide-react";
import { fmtPrice } from "@/lib/currency";

const SUB_STATUS = {
  pending_payment: { label: "Pending", color: "bg-amber-500 text-black", icon: Clock },
  active: { label: "Active", color: "bg-[#84CC16] text-black", icon: CheckCircle2 },
  paused: { label: "Paused", color: "bg-[#FACC15] text-black", icon: PauseCircle },
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

  const pauseSub = async (s) => {
    const reason = window.prompt(
      `Pause ${s.vendor_email || s.vendor_id}'s ${s.plan_type} subscription?\nReason (shown to vendor):`,
      "Discrepancy under review",
    );
    if (reason === null) return;
    try {
      await api.post(`/admin/offline-subscriptions/${s.id}/pause`, { reason });
      toast.success("Subscription paused — vendor's offline mode is now disabled");
      loadSubs();
      onQueueChange?.();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const resumeSub = async (s) => {
    if (!window.confirm(`Resume ${s.vendor_email || s.vendor_id}'s ${s.plan_type} subscription?`)) return;
    try {
      await api.post(`/admin/offline-subscriptions/${s.id}/resume`);
      toast.success("Subscription resumed — vendor's offline mode is back");
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
  const activeSubs = subs.filter((s) => s.status === "active" || s.status === "paused");
  const historySubs = subs.filter((s) => !["pending_payment", "active", "paused"].includes(s.status));
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

        {activeSubs.length > 0 && (
          <div data-testid="pa-business-active-subs" className="mt-6">
            <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-2">
              / Active subscribers <span className="text-[#84CC16]">· {activeSubs.filter((s) => s.status === "active").length} active</span>
              {activeSubs.filter((s) => s.status === "paused").length > 0 && <span className="text-[#FACC15] ml-1">· {activeSubs.filter((s) => s.status === "paused").length} paused</span>}
            </div>
            <div className="space-y-2">
              {activeSubs.map((s) => (
                <SubRow key={s.id} s={s}
                  onPause={s.status === "active" ? () => pauseSub(s) : undefined}
                  onResume={s.status === "paused" ? () => resumeSub(s) : undefined}
                />
              ))}
            </div>
          </div>
        )}

        {historySubs.length > 0 && (
          <details data-testid="pa-business-subs-history" className="mt-6">
            <summary className="text-xs text-neutral-500 cursor-pointer font-mono uppercase tracking-widest mb-2">/ History ({historySubs.length})</summary>
            <div className="space-y-2 mt-2">
              {historySubs.map((s) => <SubRow key={s.id} s={s} />)}
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

      <SubscriptionPackagesSection />
      <ReferralLeaderboardSection />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Subscription packages editor (admin creates monthly/quarterly/annual/etc.
// plans that vendors pick from at subscription time).
// ─────────────────────────────────────────────────────────────
function SubscriptionPackagesSection() {
  const [pkgs, setPkgs] = useState([]);
  const [f, setF] = useState({ name: "", duration_days: 30, price: 99, description: "", active: true });
  const load = () => api.get("/admin/subscription-packages").then((r) => setPkgs(r.data || [])).catch(() => setPkgs([]));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    if (!f.name || !f.duration_days || !f.price) return toast.error("Name, duration & price required");
    try { await api.post("/admin/subscription-packages", { ...f, duration_days: Number(f.duration_days), price: Number(f.price) });
      toast.success("Package added"); setF({ name: "", duration_days: 30, price: 99, description: "", active: true }); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const del = async (id) => { await api.delete(`/admin/subscription-packages/${id}`); load(); };
  const toggle = async (p) => { await api.patch(`/admin/subscription-packages/${p.id}`, { active: !p.active }); load(); };
  return (
    <section data-testid="pa-subscription-packages" className="mt-8">
      <div className="mb-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Subscription packages</div>
        <h2 className="font-display text-2xl tracking-wide mt-1">Offline-mode Plans</h2>
        <div className="text-xs text-neutral-500 mt-1">Create custom plans (monthly / quarterly / annual / promo). Vendors pick from these at subscription time. Existing vendors auto-lock their last-paid price on renewals (togglable in Site settings).</div>
      </div>
      <div className="border border-white/10 rounded-sm bg-[#141414] p-3 grid md:grid-cols-6 gap-2 mb-3">
        <input data-testid="pkg-name" placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="bg-black/40 border border-white/10 text-white rounded-sm px-2 py-1 text-sm" />
        <input data-testid="pkg-days" type="number" placeholder="Duration (days)" value={f.duration_days} onChange={(e) => setF({ ...f, duration_days: e.target.value })} className="bg-black/40 border border-white/10 text-white rounded-sm px-2 py-1 text-sm" />
        <input data-testid="pkg-price" type="number" placeholder="Price ₹" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} className="bg-black/40 border border-white/10 text-white rounded-sm px-2 py-1 text-sm" />
        <input data-testid="pkg-desc" placeholder="Description" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="md:col-span-2 bg-black/40 border border-white/10 text-white rounded-sm px-2 py-1 text-sm" />
        <button data-testid="pkg-add" onClick={save} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm px-3 py-1 text-sm font-semibold">Add plan</button>
      </div>
      {pkgs.length === 0
        ? <div className="text-neutral-500 text-xs italic">No custom plans yet. Vendors will see the default monthly/yearly prices from Site settings until you add one.</div>
        : (
          <div className="space-y-1">
            {pkgs.map((p) => (
              <div key={p.id} data-testid={`pkg-${p.id}`} className={`border rounded-sm p-2 flex items-center justify-between ${p.active ? "border-white/10 bg-[#141414]" : "border-white/5 bg-black/40 opacity-60"}`}>
                <div>
                  <div className="text-sm text-white">{p.name} <span className="font-mono text-[10px] text-neutral-500 ml-2">₹{p.price} · {p.duration_days}d</span></div>
                  {p.description && <div className="text-[11px] text-neutral-500">{p.description}</div>}
                </div>
                <div className="flex gap-2 items-center">
                  <button onClick={() => toggle(p)} className={`text-[10px] font-mono uppercase rounded-sm px-2 py-0.5 border ${p.active ? "text-[#84CC16] border-[#84CC16]/40" : "text-neutral-500 border-white/10"}`}>{p.active ? "active" : "inactive"}</button>
                  <button onClick={() => del(p.id)} className="text-[#FF3B30] text-xs">Delete</button>
                </div>
              </div>
            ))}
          </div>
        )}
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
// Vendor referral leaderboard
// ─────────────────────────────────────────────────────────────
function ReferralLeaderboardSection() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [lastReward, setLastReward] = useState(null);
  const load = () => { api.get("/admin/vendor-referral-leaderboard").then((r) => setRows(r.data || [])).catch(() => setRows([])); };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const rewardTop = async () => {
    if (!confirm("Issue a 20%-off promo code to the top 5 referring vendors and email them?")) return;
    setBusy(true);
    try {
      const { data } = await api.post("/admin/promo-codes/reward-top-referrers", { top_n: 5, discount_percent: 20, validity_days: 60 });
      setLastReward(data);
      toast.success(`Issued ${data.issued} promo code(s)`);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <section data-testid="pa-vendor-referrals" className="mt-8">
      <div className="mb-3 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Vendor referral leaderboard</div>
          <h2 className="font-display text-2xl tracking-wide mt-1">Top offline→platform Referrers</h2>
          <div className="text-xs text-neutral-500 mt-1">Vendors who moved the most of their pre-existing offline customers onto Kreeda Nation.</div>
        </div>
        <button data-testid="reward-top-5" onClick={rewardTop} disabled={busy || rows.length === 0} className="bg-[#FACC15] hover:bg-[#eab308] text-black rounded-sm px-3 py-2 text-sm font-semibold disabled:opacity-50">
          {busy ? "Sending…" : "🎁 Reward top 5 (20% off promo)"}
        </button>
      </div>
      {lastReward && (
        <div data-testid="reward-last-batch" className="mb-3 border border-[#84CC16]/40 rounded-sm bg-[#84CC16]/5 p-3 text-xs">
          <div className="text-[#84CC16] font-mono uppercase">Issued {lastReward.issued} promo(s):</div>
          <div className="mt-1 space-y-0.5 font-mono">
            {lastReward.results.map((r) => (
              <div key={r.vendor_id}>{r.business_name} — <span className="text-[#FACC15]">{r.code}</span> ({r.referred_count} referrals{r.email_sent ? " · email sent" : ""})</div>
            ))}
          </div>
        </div>
      )}
      {rows.length === 0
        ? <div className="text-neutral-500 text-xs italic">No referrals yet. Vendors invite via their Customers tab → WhatsApp invite link.</div>
        : (
          <div className="border border-white/10 rounded-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
                <tr><th className="text-left px-3 py-2">#</th><th className="text-left px-3 py-2">Vendor</th><th className="text-left px-3 py-2">City</th><th className="text-right px-3 py-2">Referred</th><th className="text-right px-3 py-2">Waived commission</th></tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.vendor_id} data-testid={`ref-row-${r.vendor_id}`} className="border-t border-white/5">
                    <td className="px-3 py-2 text-neutral-500 font-mono">{i + 1}</td>
                    <td className="px-3 py-2">{r.business_name}</td>
                    <td className="px-3 py-2 text-neutral-400 font-mono text-xs">{r.city || ""}</td>
                    <td className="px-3 py-2 text-right text-[#84CC16] font-mono">{r.referred_count}</td>
                    <td className="px-3 py-2 text-right text-[#FACC15] font-mono">₹{r.estimated_commission_waived}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </section>
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

function SubRow({ s, onActivate, onReject, onPause, onResume }) {
  const meta = SUB_STATUS[s.status] || SUB_STATUS.pending_payment;
  const Icon = meta.icon;
  const daysLeft = s.expires_at
    ? Math.ceil((new Date(s.expires_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
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
            {s.started_at && ` · started ${s.started_at.slice(0, 10)}`}
            {s.expires_at && ` · expires ${s.expires_at.slice(0, 10)}`}
            {daysLeft != null && daysLeft >= 0 && s.status !== "cancelled" && <span className="ml-1 text-[#84CC16]">· {daysLeft}d left</span>}
          </div>
          {s.paused_reason && <div className="text-xs text-[#FACC15]/90 mt-1">Paused: {s.paused_reason}{s.paused_at && ` · ${s.paused_at.slice(0, 10)}`}</div>}
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
      {s.status === "active" && onPause && (
        <div className="flex gap-2 mt-3">
          <Button data-testid={`pa-sub-pause-${s.id}`} size="sm" onClick={onPause}
            className="bg-[#FACC15] hover:bg-[#eab308] text-black font-semibold rounded-sm">
            <PauseCircle className="w-3.5 h-3.5 mr-1" /> Pause subscription
          </Button>
        </div>
      )}
      {s.status === "paused" && onResume && (
        <div className="flex gap-2 mt-3">
          <Button data-testid={`pa-sub-resume-${s.id}`} size="sm" onClick={onResume}
            className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
            <PlayCircle className="w-3.5 h-3.5 mr-1" /> Resume subscription
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
