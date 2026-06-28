import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { CreditCard, Wallet, AlertTriangle, X } from "lucide-react";
import { fmtPrice } from "@/lib/currency";

/**
 * MembershipPurchaseModal — opened from a "Buy" CTA on any membership plan card.
 * Renders two CTAs: Pay online (disabled stub until Razorpay lands) and
 * Proceed with offline payment (active). Both call POST /api/memberships/purchase.
 */
export default function MembershipPurchaseModal({ plan, open, onClose, onPurchased }) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  if (!plan) return null;

  const purchase = async (method) => {
    setBusy(true);
    try {
      const { data } = await api.post("/memberships/purchase", {
        plan_id: plan.id,
        payment_method: method,
        notes,
      });
      toast.success("Request sent — vendor will activate after payment is received.");
      onPurchased?.(data);
      onClose?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to send request");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose?.(); }}>
      <DialogContent data-testid="memb-purchase-modal" className="bg-[#0c0c0c] border border-white/10 text-white max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl tracking-wide flex items-center gap-2">
            Buy <span className="text-[#EC4899]">{plan.title}</span>
          </DialogTitle>
          <DialogDescription className="text-neutral-400 text-xs">
            {plan.duration_days}-day plan · {plan.max_bookings ? `${plan.max_bookings} bookings` : "unlimited bookings"} · {fmtPrice(plan.price, plan.currency)}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="border border-amber-500/40 bg-amber-500/5 rounded-sm px-3 py-2 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <div className="text-xs text-amber-200/90">
              Online payment gateway is not enabled yet. Please <b>proceed with offline payment</b>:
              your request will be queued, and the vendor will activate your membership once they
              receive the payment (cash / UPI / bank transfer at the venue desk).
            </div>
          </div>

          <div>
            <label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Notes for vendor (optional)</label>
            <Textarea data-testid="memb-purchase-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
              placeholder="When you plan to pay, payment reference, anything else…"
              className="mt-1 bg-black/40 border-white/10 text-white" />
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2">
            <Button data-testid="memb-purchase-online" disabled className="bg-neutral-700 text-neutral-400 cursor-not-allowed rounded-sm">
              <CreditCard className="w-4 h-4 mr-1.5" /> Pay online · coming soon
            </Button>
            <Button data-testid="memb-purchase-offline" disabled={busy} onClick={() => purchase("offline")}
              className="bg-[#EC4899] hover:bg-[#db2777] text-white font-semibold rounded-sm">
              <Wallet className="w-4 h-4 mr-1.5" /> {busy ? "Sending…" : "Proceed offline"}
            </Button>
          </div>

          <button onClick={onClose} className="mt-2 text-xs text-neutral-500 hover:text-neutral-300 flex items-center gap-1">
            <X className="w-3 h-3" /> Cancel
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
