import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { fmtPrice } from "@/lib/currency";
import { XCircle } from "lucide-react";

/**
 * Admin listings tab — Approve / Unpublish + Reject-with-reason (emails the vendor).
 */
export default function ListingsTab({ listings, reload, canManage }) {
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const approve = async (l) => {
    setBusy(true);
    try {
      await api.patch(`/admin/listings/${l.id}/approve`, { approved: true });
      toast.success("Approved — vendor notified");
      reload();
    } catch { toast.error("Failed"); } finally { setBusy(false); }
  };
  const unpublish = async (l) => {
    setBusy(true);
    try {
      await api.patch(`/admin/listings/${l.id}/approve`, { approved: false });
      toast.success("Unpublished");
      reload();
    } catch { toast.error("Failed"); } finally { setBusy(false); }
  };
  const rejectWithReason = async (l) => {
    if (!reason.trim()) { toast.error("Reason is required"); return; }
    setBusy(true);
    try {
      await api.patch(`/admin/listings/${l.id}/approve`, { approved: false, reason: reason.trim() });
      toast.success("Rejected — vendor notified by email");
      setRejecting(null); setReason("");
      reload();
    } catch { toast.error("Failed"); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-2">
      {listings.map((l) => (
        <div key={l.id} className="border border-white/10 rounded-sm p-4 bg-[#141414]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {l.images?.[0] && <img src={l.images[0]} alt="" className="w-14 h-14 object-cover rounded-sm" />}
              <div>
                <div className="font-semibold">{l.title} <span className="text-[10px] font-mono uppercase text-neutral-500 ml-2">{l.vendor_type}</span></div>
                <div className="text-xs font-mono text-neutral-500 uppercase">{l.city} · {fmtPrice(l.price, l.currency)} {l.price_unit}</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${l.approved ? "text-[#84CC16] border-[#84CC16]/40" : "text-amber-400 border-amber-500/40"}`}>{l.approved ? "LIVE" : "PENDING"}</span>
              {canManage && !l.approved && (
                <>
                  <Button size="sm" data-testid={`pa-approve-listing-${l.id}`} onClick={() => approve(l)} disabled={busy}
                    className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
                    Approve
                  </Button>
                  <Button size="sm" data-testid={`pa-reject-listing-${l.id}`} onClick={() => { setRejecting(l.id); setReason(""); }} disabled={busy}
                    variant="outline" className="bg-transparent border-[#FF3B30] text-[#FF3B30] hover:bg-[#FF3B30]/10">
                    <XCircle className="w-3.5 h-3.5 mr-1" /> Reject
                  </Button>
                </>
              )}
              {canManage && l.approved && (
                <Button size="sm" data-testid={`pa-unpublish-listing-${l.id}`} onClick={() => unpublish(l)} disabled={busy}
                  className="bg-white/10 hover:bg-white/20 text-white rounded-sm">
                  Unpublish
                </Button>
              )}
            </div>
          </div>
          {rejecting === l.id && (
            <div className="mt-3 space-y-2" data-testid={`pa-reject-listing-form-${l.id}`}>
              <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
                placeholder="Why is this listing being rejected? The vendor will receive this in their email."
                className="bg-black/40 border-white/10 text-white text-sm" />
              <div className="flex gap-2">
                <Button size="sm" onClick={() => rejectWithReason(l)} disabled={busy}
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
      {listings.length === 0 && <div className="text-neutral-500 text-sm text-center py-12">No listings yet.</div>}
    </div>
  );
}
