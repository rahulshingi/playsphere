import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { fmtPrice } from "@/lib/currency";

export default function ListingsTab({ listings, reload, canManage }) {
  const toggleApproval = async (l) => {
    await api.patch(`/admin/listings/${l.id}/approve`, { approved: !l.approved });
    reload();
    toast.success(l.approved ? "Hidden" : "Approved");
  };

  return (
    <div className="space-y-2">
      {listings.map((l) => (
        <div key={l.id} className="border border-white/10 rounded-sm p-4 bg-[#141414] flex items-center justify-between">
          <div className="flex items-center gap-3">
            {l.images?.[0] && <img src={l.images[0]} alt="" className="w-14 h-14 object-cover rounded-sm" />}
            <div>
              <div className="font-semibold">{l.title} <span className="text-[10px] font-mono uppercase text-neutral-500 ml-2">{l.vendor_type}</span></div>
              <div className="text-xs font-mono text-neutral-500 uppercase">{l.city} · {fmtPrice(l.price, l.currency)} {l.price_unit}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${l.approved ? "text-[#84CC16] border-[#84CC16]/40" : "text-amber-400 border-amber-500/40"}`}>{l.approved ? "LIVE" : "PENDING"}</span>
            {canManage && (
              <Button size="sm" data-testid={`pa-approve-listing-${l.id}`} onClick={() => toggleApproval(l)}
                className={l.approved ? "bg-white/10 hover:bg-white/20 text-white rounded-sm" : "bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"}>
                {l.approved ? "Unpublish" : "Approve"}
              </Button>
            )}
          </div>
        </div>
      ))}
      {listings.length === 0 && <div className="text-neutral-500 text-sm text-center py-12">No listings yet.</div>}
    </div>
  );
}
