import { useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { XCircle, Percent, Pencil } from "lucide-react";

/**
 * Admin vendors tab. Adds a "Reject with reason" flow on top of the existing
 * Approve / Revoke toggle so the platform admin can send the vendor a clear
 * note (delivered via email) about what to fix.
 */
export default function VendorsTab({ vendors, reload, canManage }) {
  const [rejecting, setRejecting] = useState(null); // vendor.id of the row showing the reason form
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [editingCommission, setEditingCommission] = useState(null); // vendor.id showing commission form
  const [commissionForm, setCommissionForm] = useState({ percent: 10, flat: 100 });

  const approve = async (v) => {
    setBusy(true);
    try {
      await api.patch(`/vendors/${v.id}/approve`, {
        approved: true,
        commission_percent: v.commission_percent ?? 10,
        commission_min_flat: v.commission_min_flat ?? 100,
      });
      toast.success("Approved — vendor notified");
      reload();
    } catch { toast.error("Failed"); } finally { setBusy(false); }
  };

  const saveCommission = async (v) => {
    const pct = Number(commissionForm.percent);
    const flat = Number(commissionForm.flat);
    if (isNaN(pct) || pct < 0 || pct > 100) { toast.error("Percent must be 0–100"); return; }
    if (isNaN(flat) || flat < 0) { toast.error("Flat floor must be ≥ 0"); return; }
    setBusy(true);
    try {
      await api.patch(`/vendors/${v.id}/approve`, {
        approved: !!v.approved,
        commission_percent: pct,
        commission_min_flat: flat,
      });
      toast.success(`Commission set: ${pct}% or ₹${flat} (whichever is higher)`);
      setEditingCommission(null);
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
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
              {canManage && (
                <Button
                  size="sm"
                  data-testid={`pa-commission-vendor-${v.id}`}
                  onClick={() => {
                    setEditingCommission(v.id);
                    setCommissionForm({ percent: v.commission_percent ?? 10, flat: v.commission_min_flat ?? 100 });
                  }}
                  disabled={busy}
                  variant="outline"
                  className="border-[#EC4899]/40 text-[#EC4899] hover:bg-[#EC4899]/10"
                >
                  <Percent className="w-3.5 h-3.5 mr-1" /> {(v.commission_percent ?? 10)}% <span className="text-neutral-500 mx-1">or</span> ₹{(v.commission_min_flat ?? 100)}
                </Button>
              )}
            </div>
          </div>
          {editingCommission === v.id && (
            <div data-testid={`pa-commission-form-${v.id}`} className="mt-3 border border-[#EC4899]/30 rounded-sm bg-[#EC4899]/5 p-3">
              <div className="text-[10px] font-mono uppercase tracking-widest text-[#EC4899] mb-2 flex items-center gap-2">
                <Pencil className="w-3 h-3" /> Set commission — max(percent × total, flat floor)
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-mono text-neutral-500">Percent (%)</label>
                  <Input
                    data-testid={`pa-commission-pct-${v.id}`}
                    type="number" min={0} max={100} step={0.5}
                    value={commissionForm.percent}
                    onChange={(e) => setCommissionForm({ ...commissionForm, percent: e.target.value })}
                    className="mt-1 bg-black/40 border-white/10 text-white h-9"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-mono text-neutral-500">Flat floor (₹)</label>
                  <Input
                    data-testid={`pa-commission-flat-${v.id}`}
                    type="number" min={0}
                    value={commissionForm.flat}
                    onChange={(e) => setCommissionForm({ ...commissionForm, flat: e.target.value })}
                    className="mt-1 bg-black/40 border-white/10 text-white h-9"
                  />
                </div>
              </div>
              <p className="text-[10px] text-neutral-500 mt-2 font-mono">
                Example: on a ₹500 booking → 10% = ₹50 vs ₹100 floor → platform collects <b className="text-white">₹100</b>.
              </p>
              <div className="flex gap-2 mt-3">
                <Button size="sm" data-testid={`pa-commission-save-${v.id}`} onClick={() => saveCommission(v)} disabled={busy}
                  className="bg-[#EC4899] hover:bg-[#DB2777] text-white rounded-sm">Save</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditingCommission(null)} className="text-neutral-400">Cancel</Button>
              </div>
            </div>
          )}
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
