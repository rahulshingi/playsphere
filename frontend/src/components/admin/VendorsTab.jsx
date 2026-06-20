import { Link } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

export default function VendorsTab({ vendors, reload, canManage }) {
  const toggleApproval = async (v) => {
    await api.patch(`/vendors/${v.id}/approve`, { approved: !v.approved });
    reload();
    toast.success(v.approved ? "Revoked" : "Approved");
  };

  return (
    <div className="space-y-2">
      {vendors.map((v) => (
        <div key={v.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between hover:border-[#EC4899] transition-colors">
          <Link to={`/platform-admin/vendors/${v.id}`} data-testid={`pa-vendor-${v.id}`} className="flex-1 min-w-0">
            <div className="font-semibold">{v.business_name} <span className="text-[10px] font-mono uppercase text-neutral-500 ml-2">{v.vendor_type}</span></div>
            <div className="text-xs font-mono text-neutral-500">{v.contact_name} · {v.city} · {v.mobile} · {v.email}</div>
          </Link>
          <div className="flex items-center gap-2 ml-3">
            <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${v.approved ? "text-[#84CC16] border-[#84CC16]/40" : "text-amber-400 border-amber-500/40"}`}>{v.approved ? "APPROVED" : "PENDING"}</span>
            {canManage && (
              <Button size="sm" data-testid={`pa-approve-vendor-${v.id}`} onClick={() => toggleApproval(v)}
                className={v.approved ? "bg-white/10 hover:bg-white/20 text-white rounded-sm" : "bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"}>
                {v.approved ? "Revoke" : "Approve"}
              </Button>
            )}
          </div>
        </div>
      ))}
      {vendors.length === 0 && <div className="text-neutral-500 text-sm text-center py-12">No vendors registered.</div>}
    </div>
  );
}
