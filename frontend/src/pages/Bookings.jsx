import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { fmtPrice } from "@/lib/currency";
import VendorBookings from "@/components/VendorBookings";

const statusOptions = ["pending", "approved", "fulfilled", "cancelled"];

export default function Bookings() {
  const { ready, isCompanyAdmin, isPlatformAdmin, isVendor } = useAuth();
  const nav = useNavigate();
  const [items, setItems] = useState([]);

  const load = () => {
    if (isVendor) { setItems([]); return; } // vendors don't have service bookings
    api.get("/bookings").then((r) => setItems(r.data));
  };

  useEffect(() => {
    if (ready && !(isCompanyAdmin || isPlatformAdmin || isVendor)) { nav("/login"); return; }
    if (ready) load();
  }, [ready, isCompanyAdmin, isPlatformAdmin, isVendor, nav]);

  const updateStatus = async (id, status) => {
    try { await api.patch(`/bookings/${id}`, { status }); toast.success("Updated"); load(); } catch { toast.error("Failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Cancel this booking?")) return;
    try { await api.delete(`/bookings/${id}`); load(); } catch { toast.error("Failed"); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Bookings</div>
        <div className="flex items-end justify-between">
          <h1 className="font-display text-6xl tracking-wide mt-3">
            {isVendor ? "INCOMING REQUESTS" : isPlatformAdmin ? "ALL BOOKINGS" : "YOUR BOOKINGS"}
          </h1>
          {!isVendor && (
            <Link to="/services"><Button data-testid="bookings-browse" className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Browse services</Button></Link>
          )}
        </div>

        {!isVendor && (
        <div className="mt-10 border border-white/10 rounded-sm overflow-hidden">
          <table data-testid="bookings-table" className="w-full text-sm">
            <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
              <tr>
                {isPlatformAdmin && <th className="text-left px-4 py-3">Company</th>}
                <th className="text-left px-4 py-3">Service</th>
                <th className="text-left px-4 py-3">Variant</th>
                <th className="text-left px-4 py-3">Custom text</th>
                <th className="text-right px-3 py-3">Qty</th>
                <th className="text-right px-3 py-3">Total</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-right px-3 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr key={b.id} className="border-t border-white/5 align-top">
                  {isPlatformAdmin && <td className="px-4 py-3 font-medium">{b.company_name}</td>}
                  <td className="px-4 py-3">{b.service_name}<div className="text-[10px] text-neutral-500 mt-0.5">{new Date(b.created_at).toLocaleString()}</div></td>
                  <td className="px-4 py-3 text-neutral-300">{b.variant_name || "—"}</td>
                  <td className="px-4 py-3 text-neutral-400 max-w-xs">{b.custom_text || "—"}</td>
                  <td className="px-3 py-3 text-right font-mono">{b.quantity}</td>
                  <td className="px-3 py-3 text-right font-mono text-[#84CC16]">{fmtPrice(b.total_price, b.currency)}</td>
                  <td className="px-4 py-3">
                    {isPlatformAdmin ? (
                      <select data-testid={`booking-status-${b.id}`} value={b.status} onChange={(e) => updateStatus(b.id, e.target.value)} className="bg-black/40 border border-white/10 text-white rounded-sm px-2 py-1 text-xs font-mono uppercase">
                        {statusOptions.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    ) : (
                      <span className="text-[10px] font-mono uppercase border border-white/10 rounded-sm px-2 py-0.5 text-neutral-300">{b.status}</span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <Button size="sm" variant="ghost" data-testid={`booking-delete-${b.id}`} onClick={() => remove(b.id)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={isPlatformAdmin ? 8 : 7} className="text-center py-16 text-neutral-500">No bookings yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        )}

        <VendorBookings />
      </div>
      <Footer />
    </div>
  );
}
