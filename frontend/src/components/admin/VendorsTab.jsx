import { useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { XCircle } from "lucide-react";

/**
 * Admin vendors tab. Adds a "Reject with reason" flow on top of the existing
 * Approve / Revoke toggle so the platform admin can send the vendor a clear
 * note (delivered via email) about what to fix.
 */
export default function VendorsTab({ vendors, reload, canManage }) {
  const [rejecting, setRejecting] = useState(null); // vendor.id of the row showing the reason form
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const approve = async (v) => {
    setBusy(true);
    try {
      await api.patch(`/vendors/${v.id}/approve`, { approved: true });
      toast.success("Approved — vendor notified");
      reload();
    } catch { toast.error("Failed"); } finally { setBusy(false); }
  };

  const revoke = async (v) => {
    setBusy(true);
    try {
      await api.patch(`/vendors/${v.id}/approve`, { approved: false });
      toast.success("Revoked");
      reload();
    } catch { toast.error("Failed"); } finally { setBusy(false); }
  };

  const rejectWithReason = async (v) => {
    if (!reason.trim()) { toast.error("Reason is required"); return; }
    setBusy(true);
    try {
      await api.patch(`/vendors/${v.id}/approve`, { approved: false, reason: reason.trim() });
      toast.success("Rejected — vendor notified by email");
      setRejecting(null); setReason("");
      reload();
    } catch { toast.error("Failed"); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-2">
      {vendors.map((v) => (
        <div key={v.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] hover:border-[#EC4899] transition-colors">
          <div className="flex items-center justify-between gap-2">
            <Link to={`/platform-admin/vendors/${v.id}`} data-testid={`pa-vendor-${v.id}`} className="flex-1 min-w-0">
              <div className="font-semibold">{v.business_name} <span className="text-[10px] font-mono uppercase text-neutral-500 ml-2">{v.vendor_type}</span></div>
              <div className="text-xs font-mono text-neutral-500">{v.contact_name} · {v.city} · {v.mobile} · {v.email}</div>
            </Link>
            <div className="flex items-center gap-2 ml-3">
              <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${v.approved ? "text-[#84CC16] border-[#84CC16]/40" : "text-amber-400 border-amber-500/40"}`}>{v.approved ? "APPROVED" : "PENDING"}</span>
              {canManage && !v.approved && (
                <>
                  <Button size="sm" data-testid={`pa-approve-vendor-${v.id}`} onClick={() => approve(v)} disabled={busy}
                    className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
                    Approve
                  </Button>
                  <Button size="sm" data-testid={`pa-reject-vendor-${v.id}`} onClick={() => { setRejecting(v.id); setReason(""); }} disabled={busy}
                    variant="outline" className="bg-transparent border-[#FF3B30] text-[#FF3B30] hover:bg-[#FF3B30]/10">
                    <XCircle className="w-3.5 h-3.5 mr-1" /> Reject
                  </Button>
                </>
              )}
              {canManage && v.approved && (
                <Button size="sm" data-testid={`pa-revoke-vendor-${v.id}`} onClick={() => revoke(v)} disabled={busy}
                  className="bg-white/10 hover:bg-white/20 text-white rounded-sm">
                  Revoke
                </Button>
              )}
            </div>
          </div>
          {rejecting === v.id && (
            <div className="mt-3 space-y-2" data-testid={`pa-reject-vendor-form-${v.id}`}>
              <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
                placeholder="Why is this vendor being rejected? They'll receive this in their email."
                className="bg-black/40 border-white/10 text-white text-sm" />
              <div className="flex gap-2">
                <Button size="sm" onClick={() => rejectWithReason(v)} disabled={busy}
                  className="bg-[#FF3B30] hover:bg-[#dc2626] text-white font-semibold rounded-sm">
                  Confirm rejection + email
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { setRejecting(null); setReason(""); }}
                  className="text-neutral-300 hover:text-white">
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      ))}
      {vendors.length === 0 && <div className="text-neutral-500 text-sm text-center py-12">No vendors registered.</div>}
    </div>
  );
}
