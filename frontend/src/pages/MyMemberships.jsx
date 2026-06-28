import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fmtPrice } from "@/lib/currency";
import { Sparkles, Clock, CheckCircle2, XCircle, AlertCircle } from "lucide-react";

const STATUS_META = {
  pending_payment: { label: "Awaiting vendor activation", color: "bg-amber-500 text-black", icon: Clock },
  active: { label: "Active", color: "bg-[#84CC16] text-black", icon: CheckCircle2 },
  expired: { label: "Expired", color: "bg-neutral-500 text-white", icon: AlertCircle },
  cancelled: { label: "Cancelled", color: "bg-[#FF3B30] text-white", icon: XCircle },
};

function daysUntil(iso) {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
}

export default function MyMemberships() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ready) return;
    if (!user || !["company_admin", "player", "organiser"].includes(user.role)) {
      nav("/login");
      return;
    }
    api.get("/memberships/my-purchases")
      .then((r) => setPurchases(r.data || []))
      .catch(() => setPurchases([]))
      .finally(() => setLoading(false));
  }, [ready, user, nav]);

  const cancel = async (p) => {
    if (!window.confirm("Cancel this pending request?")) return;
    try {
      await api.post(`/memberships/my-purchases/${p.id}/cancel`);
      toast.success("Request cancelled");
      api.get("/memberships/my-purchases").then((r) => setPurchases(r.data || []));
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Nav />
      <div className="max-w-5xl mx-auto px-6 py-12">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#EC4899]">/ My memberships</div>
        <h1 className="font-display text-5xl tracking-wider mt-2">YOUR PASSES</h1>
        <p className="text-neutral-400 text-sm mt-2 max-w-2xl">
          Active and pending subscriptions across every venue you booked through Kreeda Nation. Once the vendor confirms your offline payment, your pass switches from <b>Awaiting</b> to <b>Active</b> — and you can use it the next time you book.
        </p>

        {loading && <div className="mt-8 text-neutral-500 text-sm">Loading…</div>}
        {!loading && purchases.length === 0 && (
          <div data-testid="my-memb-empty" className="mt-12 text-center py-16 border border-dashed border-white/10 rounded-sm">
            <Sparkles className="w-8 h-8 text-[#EC4899] mx-auto mb-3 opacity-50" />
            <div className="text-neutral-300">You don&apos;t have any memberships yet.</div>
            <div className="text-xs text-neutral-500 mt-1">Browse <a href="/hire" className="text-[#EC4899] underline">/hire</a> to find a vendor with a plan that fits.</div>
          </div>
        )}

        {!loading && purchases.length > 0 && (
          <div className="mt-8 grid md:grid-cols-2 gap-4">
            {purchases.map((p) => {
              const meta = STATUS_META[p.status] || STATUS_META.pending_payment;
              const Icon = meta.icon;
              const dleft = daysUntil(p.expires_at);
              return (
                <div key={p.id} data-testid={`my-memb-${p.id}`}
                  className="border border-white/10 rounded-sm bg-[#141414] p-5 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-display text-xl tracking-wide">{p.plan_title}</div>
                      <div className="font-mono text-[10px] text-neutral-500 uppercase mt-1">
                        {p.plan_type.replace("_", " ")} · {fmtPrice(p.price, p.currency)} · {p.duration_days}d
                      </div>
                    </div>
                    <Badge data-testid={`my-memb-status-${p.id}`} className={`${meta.color} text-[10px] font-mono uppercase tracking-widest rounded-sm`}>
                      <Icon className="w-3 h-3 mr-1" /> {meta.label}
                    </Badge>
                  </div>
                  {p.status === "active" && (
                    <div className="text-xs text-neutral-300">
                      Expires <b>{p.expires_at?.slice(0, 10)}</b>
                      {dleft != null && dleft >= 0 && <span className="ml-1 text-neutral-500">({dleft} day{dleft === 1 ? "" : "s"} left)</span>}
                      {p.max_bookings && <span className="ml-2 text-neutral-500">· {p.bookings_used || 0}/{p.max_bookings} bookings used</span>}
                    </div>
                  )}
                  {p.status === "pending_payment" && (
                    <div className="text-xs text-amber-300/90 bg-amber-500/5 border border-amber-500/30 rounded-sm px-3 py-2">
                      Pay the vendor offline (cash / UPI / bank). Once they confirm, the status flips to <b>Active</b> here.
                    </div>
                  )}
                  {p.cancelled_reason && (
                    <div className="text-xs text-[#FF3B30]/90">Reason: {p.cancelled_reason}</div>
                  )}
                  <div className="flex items-center gap-2 pt-1">
                    {p.status === "pending_payment" && (
                      <Button data-testid={`my-memb-cancel-${p.id}`} size="sm" variant="ghost"
                        onClick={() => cancel(p)} className="text-[#FF3B30] hover:text-[#FF3B30]">Cancel request</Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
