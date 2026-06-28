import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { fmtPrice } from "@/lib/currency";
import { CheckCircle2, XCircle, Clock, UserPlus, Sparkles } from "lucide-react";
import UtilizationBars from "@/components/memberships/UtilizationBars";

const STATUS_META = {
  pending_payment: { label: "Pending payment", color: "bg-amber-500 text-black", icon: Clock },
  active: { label: "Active", color: "bg-[#84CC16] text-black", icon: CheckCircle2 },
  expired: { label: "Expired", color: "bg-neutral-500 text-white", icon: XCircle },
  cancelled: { label: "Cancelled", color: "bg-[#FF3B30] text-white", icon: XCircle },
};

/**
 * VendorPurchaseRequests — the activation inbox for a vendor.
 * Shows incoming `pending_payment` purchases, with Activate / Reject buttons.
 * Also lets the vendor manually issue a membership to a walk-in customer.
 */
export default function VendorPurchaseRequests({ plans = [] }) {
  const [purchases, setPurchases] = useState([]);
  const [showIssue, setShowIssue] = useState(false);
  const [issueForm, setIssueForm] = useState({ plan_id: "", buyer_email: "", notes: "", activate_immediately: true });
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/memberships/mine/purchases").then((r) => setPurchases(r.data || [])).catch(() => setPurchases([]));
  useEffect(() => { load(); }, []);

  const activate = async (p) => {
    try {
      await api.post(`/memberships/mine/purchases/${p.id}/activate`);
      toast.success("Membership activated");
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const reject = async (p) => {
    const reason = window.prompt("Reason for rejection (will be shown to buyer):", "Payment not received");
    if (reason === null) return;
    try {
      await api.post(`/memberships/mine/purchases/${p.id}/reject`, { reason });
      toast.success("Request rejected");
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); }
  };

  const submitIssue = async () => {
    if (!issueForm.plan_id || !issueForm.buyer_email) {
      toast.error("Pick a plan and enter the buyer's email");
      return;
    }
    setBusy(true);
    try {
      await api.post("/memberships/mine/issue", issueForm);
      toast.success("Membership issued");
      setShowIssue(false);
      setIssueForm({ plan_id: "", buyer_email: "", notes: "", activate_immediately: true });
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to issue");
    } finally { setBusy(false); }
  };

  const pending = purchases.filter((p) => p.status === "pending_payment");
  const others = purchases.filter((p) => p.status !== "pending_payment");

  return (
    <div className="mt-10">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">
          / Membership requests {pending.length > 0 && <span className="ml-1 text-amber-400">· {pending.length} pending</span>}
        </div>
        <Button data-testid="memb-issue-btn" onClick={() => setShowIssue(true)}
          className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
          <UserPlus className="w-4 h-4 mr-1" /> Issue manually
        </Button>
      </div>

      {showIssue && (
        <div data-testid="memb-issue-form" className="mb-4 border border-[#06B6D4]/40 rounded-sm bg-[#0c1414] p-4 space-y-3">
          <div className="font-display text-lg tracking-wide flex items-center gap-2"><Sparkles className="w-4 h-4 text-[#06B6D4]" /> Issue membership to walk-in customer</div>
          <div className="grid md:grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Plan *</label>
              <Select value={issueForm.plan_id} onValueChange={(v) => setIssueForm({ ...issueForm, plan_id: v })}>
                <SelectTrigger data-testid="memb-issue-plan" className="mt-1 bg-black/40 border-white/10 text-white"><SelectValue placeholder="Pick a plan" /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  {plans.length === 0 && <div className="px-2 py-1 text-xs text-neutral-500">Create a plan first</div>}
                  {plans.map((p) => <SelectItem key={p.id} value={p.id}>{p.title} · {fmtPrice(p.price, p.currency)}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Buyer email (must be registered) *</label>
              <Input data-testid="memb-issue-email" value={issueForm.buyer_email}
                onChange={(e) => setIssueForm({ ...issueForm, buyer_email: e.target.value.trim() })}
                placeholder="customer@example.com" className="mt-1 bg-black/40 border-white/10 text-white" />
            </div>
          </div>
          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Notes (optional)</label>
            <Textarea data-testid="memb-issue-notes" rows={2} value={issueForm.notes}
              onChange={(e) => setIssueForm({ ...issueForm, notes: e.target.value })}
              className="mt-1 bg-black/40 border-white/10 text-white" />
          </div>
          <label className="flex items-center gap-2 text-xs text-neutral-300">
            <input data-testid="memb-issue-activate" type="checkbox" checked={issueForm.activate_immediately}
              onChange={(e) => setIssueForm({ ...issueForm, activate_immediately: e.target.checked })}
              className="accent-[#06B6D4]" />
            Activate immediately (already paid offline)
          </label>
          <div className="flex gap-2 pt-1">
            <Button data-testid="memb-issue-submit" disabled={busy} onClick={submitIssue}
              className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
              {busy ? "Issuing…" : "Issue membership"}
            </Button>
            <Button variant="ghost" onClick={() => setShowIssue(false)} className="text-neutral-300">Cancel</Button>
          </div>
        </div>
      )}

      {purchases.length === 0 && (
        <div data-testid="memb-purchases-empty" className="text-neutral-500 text-sm text-center py-8 border border-dashed border-white/10 rounded-sm">
          No purchase requests yet. They&apos;ll appear here when a player or HR buys a plan.
        </div>
      )}

      {pending.length > 0 && (
        <div className="space-y-2 mb-4">
          {pending.map((p) => <PurchaseRow key={p.id} p={p} onActivate={() => activate(p)} onReject={() => reject(p)} />)}
        </div>
      )}

      {others.length > 0 && (
        <details data-testid="memb-purchases-history">
          <summary className="text-xs text-neutral-500 cursor-pointer font-mono uppercase tracking-widest mb-2">/ History ({others.length})</summary>
          <div className="space-y-2 mt-2">
            {others.map((p) => <PurchaseRow key={p.id} p={p} />)}
          </div>
        </details>
      )}
    </div>
  );
}

function PurchaseRow({ p, onActivate, onReject }) {
  const meta = STATUS_META[p.status] || STATUS_META.pending_payment;
  const Icon = meta.icon;
  return (
    <div data-testid={`memb-purchase-${p.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="font-semibold flex items-center gap-2 flex-wrap">
            {p.plan_title}
            {p.issued_by_vendor && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#06B6D4]/15 text-[#06B6D4] border border-[#06B6D4]/40">Walk-in</span>}
          </div>
          <div className="text-xs text-neutral-400 mt-0.5">
            {p.buyer_name || p.buyer_email} · <span className="font-mono text-neutral-500">{p.buyer_role}</span>
          </div>
          <div className="font-mono text-[10px] text-neutral-500 uppercase mt-1">
            {fmtPrice(p.price, p.currency)} · {p.duration_days}d · {p.payment_method}
            {p.expires_at && ` · expires ${p.expires_at.slice(0, 10)}`}
          </div>
          {p.notes && <div className="text-xs text-neutral-400 mt-1 italic">&ldquo;{p.notes}&rdquo;</div>}
          {p.cancelled_reason && <div className="text-xs text-[#FF3B30]/90 mt-1">Cancelled: {p.cancelled_reason}</div>}
        </div>
        <Badge className={`${meta.color} text-[10px] font-mono uppercase tracking-widest rounded-sm shrink-0`}>
          <Icon className="w-3 h-3 mr-1" /> {meta.label}
        </Badge>
      </div>
      {p.status === "pending_payment" && onActivate && (
        <div className="flex gap-2 mt-3">
          <Button data-testid={`memb-activate-${p.id}`} size="sm" onClick={onActivate}
            className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Activate (payment received)
          </Button>
          <Button data-testid={`memb-reject-${p.id}`} size="sm" variant="ghost" onClick={onReject} className="text-[#FF3B30]">
            <XCircle className="w-3.5 h-3.5 mr-1" /> Reject
          </Button>
        </div>
      )}
      {p.status === "active" && <UtilizationBars purchaseId={p.id} compact />}
    </div>
  );
}
