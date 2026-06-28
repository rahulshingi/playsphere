import { useEffect, useState } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { fmtPrice } from "@/lib/currency";
import { Sparkles, ShieldCheck } from "lucide-react";
import MembershipPurchaseModal from "./MembershipPurchaseModal";

/**
 * PublicMembershipsList — shows membership plans for a specific vendor or listing.
 * Drops a "Buy" CTA next to every plan. Used inside the VendorMarket booking modal
 * and the public vendor profile page.
 *
 * Props:
 *  - vendorId OR listingId (one required)
 *  - title: optional heading override
 */
export default function PublicMembershipsList({ vendorId, listingId, title = "Membership plans" }) {
  const { user } = useAuth();
  const [plans, setPlans] = useState([]);
  const [buying, setBuying] = useState(null);

  useEffect(() => {
    const url = listingId
      ? `/memberships/listing/${listingId}`
      : vendorId
        ? `/memberships/vendor/${vendorId}`
        : null;
    if (!url) return;
    api.get(url).then((r) => setPlans(r.data || [])).catch(() => setPlans([]));
  }, [vendorId, listingId]);

  if (!plans.length) return null;

  const canBuy = user && ["company_admin", "player", "organiser"].includes(user.role);

  return (
    <div className="mt-4 border border-[#EC4899]/30 bg-gradient-to-br from-[#EC4899]/5 to-transparent rounded-sm p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#EC4899] mb-3 flex items-center gap-1.5">
        <Sparkles className="w-3 h-3" /> / {title}
      </div>
      <div className="space-y-2">
        {plans.map((p) => (
          <div key={p.id} data-testid={`pubmemb-${p.id}`} className="flex items-center justify-between gap-3 border border-white/10 rounded-sm p-3 bg-black/30">
            <div className="min-w-0">
              <div className="font-semibold text-sm flex items-center gap-2 flex-wrap">
                {p.title}
                <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#EC4899]/15 text-[#EC4899] border border-[#EC4899]/40">
                  {p.plan_type.replace("_", " ")}
                </span>
              </div>
              <div className="text-[10px] font-mono uppercase text-neutral-500 mt-0.5">
                {fmtPrice(p.price, p.currency)} · {p.duration_days}d
                {p.max_bookings ? ` · ${p.max_bookings} bookings` : " · unlimited"}
                {p.plan_type === "fixed_slot" && p.slot_start_time && ` · ${p.slot_start_time}–${p.slot_end_time}`}
              </div>
              {p.description && <div className="text-xs text-neutral-400 mt-1 line-clamp-2">{p.description}</div>}
            </div>
            {canBuy ? (
              <Button data-testid={`pubmemb-buy-${p.id}`} size="sm" onClick={() => setBuying(p)}
                className="bg-[#EC4899] hover:bg-[#db2777] text-white font-semibold rounded-sm shrink-0">
                <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Buy
              </Button>
            ) : (
              <span className="text-[10px] font-mono uppercase text-neutral-500 shrink-0">Sign in to buy</span>
            )}
          </div>
        ))}
      </div>
      <MembershipPurchaseModal plan={buying} open={!!buying} onClose={() => setBuying(null)} />
    </div>
  );
}
