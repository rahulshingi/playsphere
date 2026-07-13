import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { fmtPrice } from "@/lib/currency";
import { Badge } from "@/components/ui/badge";
import { Receipt, AlertCircle, CheckCircle2, Info } from "lucide-react";

/**
 * VendorCommissionInvoices — vendor's view of the platform commission
 * they owe Kreeda Nation on completed platform (online) bookings.
 *
 * Read-only for vendors — admin marks paid via /admin/commission-invoices.
 * Vendors settle offline (bank transfer / UPI) and reply to admin with the
 * UTR. Razorpay Route-based auto-split will replace this once keys are wired.
 */
export default function VendorCommissionInvoices() {
  const [invoices, setInvoices] = useState([]);
  const [totals, setTotals] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/vendor/commission-invoices")
      .then((r) => { setInvoices(r.data.invoices || []); setTotals(r.data.totals || null); })
      .catch(() => setInvoices([]))
      .finally(() => setLoading(false));
  }, []);

  const pending = useMemo(() => invoices.filter((i) => i.status === "pending"), [invoices]);
  const paid = useMemo(() => invoices.filter((i) => i.status === "paid"), [invoices]);

  return (
    <div data-testid="vendor-commissions" className="mt-12">
      <div className="flex items-center justify-between mb-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">
          / Platform commission — invoices ({invoices.length})
        </div>
      </div>

      {/* Top-row KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Kpi label="Pending amount" value={fmtPrice(totals?.pending_amount || 0, "INR")} tone="border-[#F59E0B]/40 text-[#F59E0B] bg-[#F59E0B]/5" testid="commission-pending-amount" />
        <Kpi label="Pending invoices" value={totals?.pending_count || 0} tone="border-[#06B6D4]/40 text-[#06B6D4] bg-[#06B6D4]/5" testid="commission-pending-count" />
        <Kpi label="Paid amount" value={fmtPrice(totals?.paid_amount || 0, "INR")} tone="border-[#84CC16]/40 text-[#84CC16] bg-[#84CC16]/5" testid="commission-paid-amount" />
        <Kpi label="Paid invoices" value={totals?.paid_count || 0} tone="border-[#EC4899]/40 text-[#EC4899] bg-[#EC4899]/5" testid="commission-paid-count" />
      </div>

      {(totals?.pending_count || 0) > 0 && (
        <div className="border border-[#F59E0B]/30 bg-[#F59E0B]/10 rounded-sm p-4 mb-4 text-sm flex gap-3">
          <AlertCircle className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-[#F59E0B]">Commission pending — please settle to keep your listings live</div>
            <div className="text-neutral-400 text-xs mt-1 leading-relaxed">
              Transfer {fmtPrice(totals?.pending_amount || 0, "INR")} to Kreeda Nation&rsquo;s registered bank account
              and reply to the admin&apos;s reminder email with your UTR. Admin will mark these invoices as paid within 24 hours.
              Online (Razorpay) auto-collect coming soon.
            </div>
          </div>
        </div>
      )}

      {loading && <div className="text-neutral-500 text-sm">Loading…</div>}

      {!loading && invoices.length === 0 && (
        <div className="text-neutral-500 text-sm text-center py-8 border border-dashed border-white/10 rounded-sm flex items-center justify-center gap-2">
          <Info className="w-4 h-4" /> No commission invoices yet — they&rsquo;re auto-generated when a platform booking is completed.
        </div>
      )}

      {pending.length > 0 && (
        <div>
          <div className="text-[10px] font-mono uppercase text-neutral-500 mb-1.5">Pending ({pending.length})</div>
          <InvoiceTable rows={pending} testid="commission-pending-table" />
        </div>
      )}

      {paid.length > 0 && (
        <div className="mt-6">
          <div className="text-[10px] font-mono uppercase text-neutral-500 mb-1.5">Paid ({paid.length})</div>
          <InvoiceTable rows={paid} testid="commission-paid-table" showPaidAt />
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, tone, testid }) {
  return (
    <div data-testid={testid} className={`border rounded-sm p-3 ${tone}`}>
      <div className="text-[10px] font-mono uppercase tracking-widest opacity-75">{label}</div>
      <div className="text-lg font-semibold mt-0.5">{value}</div>
    </div>
  );
}

function InvoiceTable({ rows, testid, showPaidAt }) {
  return (
    <div data-testid={testid} className="border border-white/10 rounded-sm bg-[#0f0f0f] overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
          <tr>
            <th className="text-left px-3 py-2">Booking date</th>
            <th className="text-left px-3 py-2">Listing</th>
            <th className="text-right px-3 py-2">Booking ₹</th>
            <th className="text-right px-3 py-2">Overtime ₹</th>
            <th className="text-right px-3 py-2">Base %</th>
            <th className="text-right px-3 py-2">OT commission</th>
            <th className="text-right px-3 py-2">Total commission</th>
            <th className="text-left px-3 py-2">Status</th>
            {showPaidAt && <th className="text-left px-3 py-2">Paid on</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-testid={`invoice-row-${r.id}`} className="border-t border-white/5 hover:bg-white/[0.02]">
              <td className="px-3 py-2 font-mono text-neutral-400">{r.requested_date}</td>
              <td className="px-3 py-2 text-neutral-200 truncate max-w-[220px]">{r.listing_title}</td>
              <td className="px-3 py-2 text-right font-mono">{fmtPrice(r.booking_total, r.currency)}</td>
              <td className="px-3 py-2 text-right font-mono text-[#FACC15]">
                {r.overtime_amount > 0 ? `${fmtPrice(r.overtime_amount, r.currency)} · ${r.overtime_minutes}m` : "—"}
              </td>
              <td className="px-3 py-2 text-right font-mono">{r.commission_percent?.toFixed(1)}%</td>
              <td className="px-3 py-2 text-right font-mono text-[#FACC15]">
                {r.overtime_commission_amount > 0 ? fmtPrice(r.overtime_commission_amount, r.currency) : "—"}
              </td>
              <td className="px-3 py-2 text-right font-mono text-white font-semibold">{fmtPrice(r.commission_amount, r.currency)}</td>
              <td className="px-3 py-2">
                {r.status === "paid" ? (
                  <Badge className="bg-[#84CC16]/15 text-[#84CC16] border border-[#84CC16]/40">
                    <CheckCircle2 className="w-3 h-3 mr-1" /> Paid
                  </Badge>
                ) : (
                  <Badge className="bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/40">
                    <Receipt className="w-3 h-3 mr-1" /> Pending
                  </Badge>
                )}
              </td>
              {showPaidAt && (
                <td className="px-3 py-2 font-mono text-[10px] text-neutral-500">
                  {r.paid_at ? r.paid_at.slice(0, 10) : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
