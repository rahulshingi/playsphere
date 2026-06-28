import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Sparkles, ShieldCheck, AlertTriangle, CreditCard, Wallet, CheckCircle2 } from "lucide-react";
import { fmtPrice } from "@/lib/currency";

/**
 * OfflineModeCard — vendor-side subscription unlock for the "Use Kreeda Nation
 * for my offline business" feature. Mirrors the offline-first rail used for
 * membership purchases: shows monthly + yearly tiers, online CTA disabled until
 * Razorpay arrives, offline CTA active, admin activates from /platform-admin.
 *
 * Props:
 *  - vendor: { offline_mode, offline_subscription_expires_at }
 *  - onChange: () => void  // called after a request goes through, to reload
 */
export default function OfflineModeCard({ vendor, onChange }) {
  const [mySubs, setMySubs] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pricing, setPricing] = useState({ monthly: 99, yearly: 999, currency: "INR" });

  const load = () => api.get("/offline-subscriptions/mine").then((r) => setMySubs(r.data || [])).catch(() => setMySubs([]));
  useEffect(() => { load(); }, []);

  useEffect(() => {
    api.get("/settings").then((r) => {
      const s = r.data || {};
      setPricing({
        monthly: Number(s.offline_subscription_monthly_price ?? 99),
        yearly: Number(s.offline_subscription_yearly_price ?? 999),
        currency: s.offline_subscription_currency || "INR",
      });
    }).catch(() => {});
  }, []);

  const submit = async (plan_type) => {
    setBusy(true);
    try {
      await api.post("/offline-subscriptions/request", { plan_type });
      toast.success("Request sent — admin will activate after offline payment");
      setOpen(false);
      load();
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  const latestPending = mySubs.find((s) => s.status === "pending_payment");
  const activeSub = mySubs.find((s) => s.status === "active");
  const isActive = !!vendor?.offline_mode;

  return (
    <div data-testid="offline-mode-card" className="mt-10 border border-[#06B6D4]/40 rounded-sm bg-gradient-to-br from-[#06B6D4]/8 to-transparent p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4] flex items-center gap-1.5">
            <Sparkles className="w-3 h-3" /> / Offline business mode
          </div>
          <div className="font-display text-2xl tracking-wider mt-1">USE KREEDA NATION FOR YOUR OWN BOOKINGS TOO</div>
          <p className="text-sm text-neutral-400 mt-1 max-w-2xl">
            Maintain your private client roster, manage offline / walk-in bookings, and block your calendar — all in one place. Kreeda Nation buyers see only that the slot is unavailable; your client&apos;s personal info stays with you.
          </p>
          {isActive && activeSub && (
            <div data-testid="offline-mode-active" className="mt-3 text-xs flex items-center gap-2 text-[#84CC16]">
              <CheckCircle2 className="w-4 h-4" /> Active until <b className="ml-1">{activeSub.expires_at?.slice(0, 10)}</b>
            </div>
          )}
          {!isActive && latestPending && (
            <div data-testid="offline-mode-pending" className="mt-3 text-xs flex items-center gap-2 text-amber-400">
              <AlertTriangle className="w-4 h-4" /> {latestPending.plan_type === "yearly" ? "Yearly" : "Monthly"} plan request pending admin activation
            </div>
          )}
        </div>
        {!isActive && (
          <Button data-testid="offline-mode-unlock" onClick={() => setOpen(true)} disabled={!!latestPending}
            className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm shrink-0">
            <ShieldCheck className="w-4 h-4 mr-1.5" /> Unlock offline mode
          </Button>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="offline-mode-modal" className="bg-[#0c0c0c] border border-white/10 text-white max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl tracking-wide">Pick a plan</DialogTitle>
            <DialogDescription className="text-neutral-400 text-xs">
              Online payment is coming soon — for now confirm by offline payment (UPI / bank). Admin activates once received.
            </DialogDescription>
          </DialogHeader>

          <div className="border border-amber-500/40 bg-amber-500/5 rounded-sm px-3 py-2 flex items-start gap-2 text-xs text-amber-200/90">
            <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            Online payment gateway is not enabled yet. Please proceed offline; we&apos;ll activate once admin confirms receipt.
          </div>

          <div className="grid grid-cols-2 gap-3 mt-3">
            <PlanTile testid="offline-mode-monthly" label="Monthly" price={pricing.monthly} currency={pricing.currency}
              perks={["Full offline-bookings module", "Block any slot from your dashboard", "Renew every month"]}
              onPick={() => submit("monthly")} disabled={busy} />
            <PlanTile testid="offline-mode-yearly" label="Yearly · save 10×" price={pricing.yearly} currency={pricing.currency}
              perks={["Same module — billed once a year", "Best for active venues", "Auto-cancel if not renewed"]}
              onPick={() => submit("yearly")} disabled={busy} highlight />
          </div>

          <div className="flex gap-2 mt-4">
            <Button data-testid="offline-mode-online-disabled" disabled className="bg-neutral-700 text-neutral-400 cursor-not-allowed rounded-sm">
              <CreditCard className="w-4 h-4 mr-1.5" /> Pay online · coming soon
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)} className="text-neutral-400">Cancel</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function PlanTile({ testid, label, price, currency, perks, onPick, disabled, highlight }) {
  return (
    <button data-testid={testid} onClick={onPick} disabled={disabled}
      className={`text-left rounded-sm border p-4 transition-all bg-black/30 hover:bg-black/50 ${highlight ? "border-[#EC4899] ring-1 ring-[#EC4899]/50" : "border-white/10"} ${disabled ? "opacity-50 cursor-wait" : ""}`}>
      <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="font-display text-3xl tracking-wide mt-1">{fmtPrice(price, currency)}</div>
      <ul className="mt-2 space-y-1 text-[11px] text-neutral-300">
        {perks.map((p, i) => <li key={i} className="flex items-start gap-1.5"><CheckCircle2 className="w-3 h-3 text-[#84CC16] mt-0.5 shrink-0" />{p}</li>)}
      </ul>
      <div className="mt-3 text-[10px] font-mono uppercase tracking-widest text-[#06B6D4] flex items-center gap-1">
        <Wallet className="w-3 h-3" /> Pay offline · click to request
      </div>
    </button>
  );
}
