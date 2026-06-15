import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { fmtPrice } from "@/lib/currency";
import { CheckCircle, XCircle, Clock, Ban, Megaphone, Edit3 } from "lucide-react";

const STATUS_META = {
  pending: { label: "Awaiting vendor", color: "bg-[#F59E0B] text-black", icon: Clock },
  vendor_accepted: { label: "Vendor accepted · awaiting admin", color: "bg-[#06B6D4] text-black", icon: CheckCircle },
  vendor_declined: { label: "Vendor declined · admin reviewing", color: "bg-[#FF3B30] text-white", icon: XCircle },
  confirmed: { label: "Confirmed by Kreeda Nation", color: "bg-[#84CC16] text-black", icon: CheckCircle },
  rejected: { label: "Rejected by Kreeda Nation", color: "bg-[#FF3B30] text-white", icon: XCircle },
  cancelled: { label: "Cancelled", color: "bg-neutral-500 text-white", icon: Ban },
};

export default function VendorBookings() {
  const { user, isCompanyAdmin, isPlatformAdmin, isVendor } = useAuth();
  const [bookings, setBookings] = useState([]);
  const [overrideOpenId, setOverrideOpenId] = useState(null);
  const [noteDraft, setNoteDraft] = useState("");

  const load = () => api.get("/vendor-bookings").then((r) => setBookings(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const adminAct = async (id, status) => {
    try {
      await api.patch(`/vendor-bookings/${id}`, { status, admin_notes: noteDraft });
      toast.success(`Booking ${status}`);
      setOverrideOpenId(null);
      setNoteDraft("");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const vendorAct = async (id, status) => {
    try {
      await api.patch(`/vendor-bookings/${id}`, { status });
      toast.success(`Marked ${status.replace("vendor_", "")}`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const hrCancel = async (id) => {
    if (!window.confirm("Cancel this booking request?")) return;
    try {
      await api.patch(`/vendor-bookings/${id}`, { status: "cancelled" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  if (bookings.length === 0) return null;

  return (
    <div data-testid="vendor-bookings-panel" className="mt-16">
      <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Ground bookings</div>
      <h2 className="font-display text-3xl tracking-wide mt-2">GROUNDS &amp; TALENT REQUESTS</h2>
      <p className="text-xs text-neutral-500 mt-1">
        {isPlatformAdmin && "Confirm or reject each request after coordinating with the vendor."}
        {isCompanyAdmin && "Track your booking requests. You'll be notified when Kreeda Nation confirms with the vendor."}
        {isVendor && "Respond to incoming requests. Kreeda Nation admin will finalize."}
      </p>

      <div className="mt-6 space-y-3">
        {bookings.map((b) => {
          const meta = STATUS_META[b.status] || STATUS_META.pending;
          const Icon = meta.icon;
          const latest = b.notifications?.[b.notifications.length - 1];
          const canVendorAct = isVendor && b.status === "pending";
          const canAdminAct = isPlatformAdmin && b.status !== "cancelled";
          const canHrCancel = isCompanyAdmin && ["pending", "vendor_accepted", "vendor_declined"].includes(b.status);

          return (
            <div key={b.id} data-testid={`vb-row-${b.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-semibold">{b.listing_title}</div>
                  <div className="text-[11px] font-mono text-neutral-500 uppercase tracking-widest mt-0.5">
                    {b.city || "—"} · {b.sport || b.vendor_type} · {b.requested_date} · {b.start_time}–{b.end_time} ({b.hours}h)
                  </div>
                  {isPlatformAdmin && <div className="text-[11px] font-mono text-neutral-500 mt-0.5">HR: {b.hr_email || b.company_name}</div>}
                </div>
                <div className="flex items-center gap-2">
                  <Badge data-testid={`vb-status-${b.id}`} className={`${meta.color} text-[10px] font-mono uppercase tracking-widest rounded-sm`}>
                    <Icon className="w-3 h-3 mr-1" /> {meta.label}
                  </Badge>
                  <div className="text-right">
                    <div className="font-mono text-lg text-[#84CC16]">{fmtPrice(b.total || b.price, b.currency)}</div>
                    <div className="text-[10px] font-mono text-neutral-500">{b.hours}h × {fmtPrice(b.price, b.currency)}</div>
                  </div>
                </div>
              </div>

              {latest && (
                <div className="mt-3 flex items-start gap-2 text-[11px] text-neutral-400 bg-black/30 rounded-sm px-3 py-2 border border-white/5">
                  <Megaphone className="w-3 h-3 mt-0.5 text-[#06B6D4]" />
                  <div className="min-w-0 flex-1">
                    <span className="text-neutral-300">{latest.message}</span>
                    <span className="ml-2 text-neutral-600 font-mono uppercase">— {latest.by_name || latest.by_role}</span>
                  </div>
                </div>
              )}
              {b.admin_notes && (
                <div className="mt-2 text-[11px] text-[#84CC16] bg-[#84CC16]/5 border border-[#84CC16]/20 rounded-sm px-3 py-2">
                  Admin note: {b.admin_notes}
                </div>
              )}

              {/* Vendor row actions */}
              {canVendorAct && (
                <div className="mt-3 flex gap-2">
                  <Button data-testid={`vb-vendor-accept-${b.id}`} size="sm" onClick={() => vendorAct(b.id, "vendor_accepted")} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black rounded-sm">Accept</Button>
                  <Button data-testid={`vb-vendor-decline-${b.id}`} size="sm" variant="outline" onClick={() => vendorAct(b.id, "vendor_declined")} className="rounded-sm border-white/10 text-white">Decline</Button>
                </div>
              )}

              {/* HR cancel */}
              {canHrCancel && (
                <div className="mt-3">
                  <Button data-testid={`vb-hr-cancel-${b.id}`} size="sm" variant="ghost" onClick={() => hrCancel(b.id)} className="text-[#FF3B30]">Cancel request</Button>
                </div>
              )}

              {/* Admin actions */}
              {canAdminAct && (
                <div className="mt-3 border-t border-white/5 pt-3">
                  {overrideOpenId === b.id ? (
                    <div className="space-y-2">
                      <Input data-testid={`vb-admin-note-${b.id}`} placeholder="Admin note (visible to HR & vendor)" value={noteDraft} onChange={(e) => setNoteDraft(e.target.value)} className="bg-black/40 border-white/10 text-white text-sm" />
                      <div className="flex gap-2">
                        <Button data-testid={`vb-admin-confirm-${b.id}`} size="sm" onClick={() => adminAct(b.id, "confirmed")} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm">Confirm</Button>
                        <Button data-testid={`vb-admin-reject-${b.id}`} size="sm" variant="outline" onClick={() => adminAct(b.id, "rejected")} className="rounded-sm border-[#FF3B30]/40 text-[#FF3B30]">Reject</Button>
                        <Button size="sm" variant="ghost" onClick={() => { setOverrideOpenId(null); setNoteDraft(""); }} className="text-neutral-400">Close</Button>
                      </div>
                    </div>
                  ) : (
                    <Button data-testid={`vb-admin-open-${b.id}`} size="sm" variant="outline" onClick={() => { setOverrideOpenId(b.id); setNoteDraft(b.admin_notes || ""); }} className="rounded-sm border-white/10 text-white">
                      <Edit3 className="w-3.5 h-3.5 mr-1" /> Confirm / Reject
                    </Button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
