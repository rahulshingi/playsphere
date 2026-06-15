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

function useVendorBookings() {
  const [bookings, setBookings] = useState([]);
  const reload = () => api.get("/vendor-bookings").then((r) => setBookings(r.data)).catch(() => {});
  useEffect(() => { reload(); }, []);
  return [bookings, reload];
}

function StatusBadge({ booking }) {
  const meta = STATUS_META[booking.status] || STATUS_META.pending;
  const Icon = meta.icon;
  return (
    <Badge data-testid={`vb-status-${booking.id}`} className={`${meta.color} text-[10px] font-mono uppercase tracking-widest rounded-sm`}>
      <Icon className="w-3 h-3 mr-1" /> {meta.label}
    </Badge>
  );
}

function NotificationBanner({ booking }) {
  const latest = booking.notifications?.[booking.notifications.length - 1];
  if (!latest) return null;
  return (
    <div className="mt-3 flex items-start gap-2 text-[11px] text-neutral-400 bg-black/30 rounded-sm px-3 py-2 border border-white/5">
      <Megaphone className="w-3 h-3 mt-0.5 text-[#06B6D4]" />
      <div className="min-w-0 flex-1">
        <span className="text-neutral-300">{latest.message}</span>
        <span className="ml-2 text-neutral-600 font-mono uppercase">— {latest.by_name || latest.by_role}</span>
      </div>
    </div>
  );
}

function VendorActions({ booking, onAct }) {
  return (
    <div className="mt-3 flex gap-2">
      <Button data-testid={`vb-vendor-accept-${booking.id}`} size="sm" onClick={() => onAct("vendor_accepted")} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black rounded-sm">Accept</Button>
      <Button data-testid={`vb-vendor-decline-${booking.id}`} size="sm" variant="outline" onClick={() => onAct("vendor_declined")} className="rounded-sm border-white/10 text-white">Decline</Button>
    </div>
  );
}

function HrCancel({ booking, onCancel }) {
  return (
    <div className="mt-3">
      <Button data-testid={`vb-hr-cancel-${booking.id}`} size="sm" variant="ghost" onClick={onCancel} className="text-[#FF3B30]">Cancel request</Button>
    </div>
  );
}

function AdminActions({ booking, onConfirm, onReject }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState(booking.admin_notes || "");

  if (!open) {
    return (
      <div className="mt-3 border-t border-white/5 pt-3">
        <Button data-testid={`vb-admin-open-${booking.id}`} size="sm" variant="outline" onClick={() => setOpen(true)} className="rounded-sm border-white/10 text-white">
          <Edit3 className="w-3.5 h-3.5 mr-1" /> Confirm / Reject
        </Button>
      </div>
    );
  }
  return (
    <div className="mt-3 border-t border-white/5 pt-3 space-y-2">
      <Input data-testid={`vb-admin-note-${booking.id}`} placeholder="Admin note (visible to HR & vendor)" value={note} onChange={(e) => setNote(e.target.value)} className="bg-black/40 border-white/10 text-white text-sm" />
      <div className="flex gap-2">
        <Button data-testid={`vb-admin-confirm-${booking.id}`} size="sm" onClick={() => onConfirm(note)} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm">Confirm</Button>
        <Button data-testid={`vb-admin-reject-${booking.id}`} size="sm" variant="outline" onClick={() => onReject(note)} className="rounded-sm border-[#FF3B30]/40 text-[#FF3B30]">Reject</Button>
        <Button size="sm" variant="ghost" onClick={() => { setOpen(false); setNote(""); }} className="text-neutral-400">Close</Button>
      </div>
    </div>
  );
}

function BookingRow({ booking, role, onPatch }) {
  const { isVendor, isCompanyAdmin, isPlatformAdmin } = role;
  const canVendorAct = isVendor && booking.status === "pending";
  const canAdminAct = isPlatformAdmin && booking.status !== "cancelled";
  const canHrCancel = isCompanyAdmin && ["pending", "vendor_accepted", "vendor_declined"].includes(booking.status);

  const hrCancel = () => {
    if (!window.confirm("Cancel this booking request?")) return;
    onPatch(booking.id, { status: "cancelled" });
  };

  return (
    <div data-testid={`vb-row-${booking.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-semibold">{booking.listing_title}</div>
          <div className="text-[11px] font-mono text-neutral-500 uppercase tracking-widest mt-0.5">
            {booking.city || "—"} · {booking.sport || booking.vendor_type} · {booking.requested_date} · {booking.start_time}–{booking.end_time} ({booking.hours}h)
          </div>
          {isPlatformAdmin && <div className="text-[11px] font-mono text-neutral-500 mt-0.5">HR: {booking.hr_email || booking.company_name}</div>}
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge booking={booking} />
          <div className="text-right">
            <div className="font-mono text-lg text-[#84CC16]">{fmtPrice(booking.total || booking.price, booking.currency)}</div>
            <div className="text-[10px] font-mono text-neutral-500">{booking.hours}h × {fmtPrice(booking.price, booking.currency)}</div>
          </div>
        </div>
      </div>

      <NotificationBanner booking={booking} />
      {booking.admin_notes && (
        <div className="mt-2 text-[11px] text-[#84CC16] bg-[#84CC16]/5 border border-[#84CC16]/20 rounded-sm px-3 py-2">
          Admin note: {booking.admin_notes}
        </div>
      )}

      {canVendorAct && <VendorActions booking={booking} onAct={(s) => onPatch(booking.id, { status: s })} />}
      {canHrCancel && <HrCancel booking={booking} onCancel={hrCancel} />}
      {canAdminAct && (
        <AdminActions
          booking={booking}
          onConfirm={(note) => onPatch(booking.id, { status: "confirmed", admin_notes: note })}
          onReject={(note) => onPatch(booking.id, { status: "rejected", admin_notes: note })}
        />
      )}
    </div>
  );
}

export default function VendorBookings() {
  const role = useAuth();
  const [bookings, reload] = useVendorBookings();

  const onPatch = async (id, payload) => {
    try {
      await api.patch(`/vendor-bookings/${id}`, payload);
      const verb = payload.status?.replace("vendor_", "") || "updated";
      toast.success(`Booking ${verb}`);
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  if (bookings.length === 0) return null;
  return (
    <div data-testid="vendor-bookings-panel" className="mt-16">
      <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Ground bookings</div>
      <h2 className="font-display text-3xl tracking-wide mt-2">GROUNDS &amp; TALENT REQUESTS</h2>
      <p className="text-xs text-neutral-500 mt-1">
        {role.isPlatformAdmin && "Confirm or reject each request after coordinating with the vendor."}
        {role.isCompanyAdmin && "Track your booking requests. You'll be notified when Kreeda Nation confirms with the vendor."}
        {role.isVendor && "Respond to incoming requests. Kreeda Nation admin will finalize."}
      </p>
      <div className="mt-6 space-y-3">
        {bookings.map((b) => <BookingRow key={b.id} booking={b} role={role} onPatch={onPatch} />)}
      </div>
    </div>
  );
}
