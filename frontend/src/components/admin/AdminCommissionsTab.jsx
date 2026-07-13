import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { fmtPrice } from "@/lib/currency";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Send, CheckCircle2, Receipt, AlertCircle, Mail } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

/**
 * AdminCommissionsTab — platform commission tracker + reminder sender.
 *
 * Two views inside one tab:
 *   • "Per-vendor rollup" — dues summary per vendor + Send reminder button
 *   • "All invoices" — flat list, filterable by status; admin can mark paid
 *
 * All commission invoices are auto-generated on booking completion via the
 * lazy sweep in /admin/commission-invoices GET.
 */
export default function AdminCommissionsTab() {
  const [invoices, setInvoices] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filter, setFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [markingPaid, setMarkingPaid] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = () => {
    setLoading(true);
    api.get(`/admin/commission-invoices?status=${filter}`)
      .then((r) => {
        setInvoices(r.data.invoices || []);
        setVendors(r.data.vendors || []);
        setSummary(r.data.summary || null);
      })
      .catch(() => toast.error("Failed to load commissions"))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [filter]);

  const sendReminder = async (invoiceId) => {
    setBusy(invoiceId);
    try {
      await api.post(`/admin/commission-invoices/${invoiceId}/send-reminder`);
      toast.success("Reminder sent");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setBusy(null); }
  };

  const sendBulkReminder = async (vendorId) => {
    setBusy(vendorId);
    try {
      const { data } = await api.post("/admin/commission-invoices/send-reminders-bulk", { vendor_ids: [vendorId] });
      toast.success(`Reminder sent for ${data.reminders_sent} invoice(s)`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setBusy(null); }
  };

  const confirmPaid = async () => {
    if (!markingPaid) return;
    setBusy(markingPaid.id);
    try {
      await api.post(`/admin/commission-invoices/${markingPaid.id}/mark-paid`, { payment_note: "" });
      toast.success("Invoice marked paid");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setBusy(null); setMarkingPaid(null); }
  };

  const vendorsSorted = useMemo(() => [...vendors].sort((a, b) => (b.pending_amount || 0) - (a.pending_amount || 0)), [vendors]);
  const vendorsWithDues = vendorsSorted.filter((v) => v.pending_count > 0);

  return (
    <div data-testid="admin-commissions-tab" className="space-y-6">
      {/* KPI banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Total pending" value={fmtPrice(summary?.total_pending || 0, "INR")} tone="border-[#F59E0B]/40 text-[#F59E0B] bg-[#F59E0B]/5" testid="adm-total-pending" />
        <Kpi label="Vendors with dues" value={summary?.vendors_with_dues || 0} tone="border-[#EC4899]/40 text-[#EC4899] bg-[#EC4899]/5" testid="adm-vendors-with-dues" />
        <Kpi label="Pending invoices" value={summary?.total_pending_count || 0} tone="border-[#06B6D4]/40 text-[#06B6D4] bg-[#06B6D4]/5" testid="adm-pending-count" />
        <Kpi label="Collected (all-time)" value={fmtPrice(summary?.total_paid || 0, "INR")} tone="border-[#84CC16]/40 text-[#84CC16] bg-[#84CC16]/5" testid="adm-total-paid" />
      </div>

      {/* Filter buttons */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Show:</span>
        {[
          { key: "pending", label: "Pending" },
          { key: "paid", label: "Paid" },
          { key: "all", label: "All" },
        ].map((f) => (
          <button
            key={f.key}
            data-testid={`adm-filter-${f.key}`}
            onClick={() => setFilter(f.key)}
            className={`text-[10px] font-mono uppercase px-2.5 py-1 rounded-sm border ${filter === f.key ? "bg-[#06B6D4] border-[#06B6D4] text-black" : "border-white/10 text-neutral-400 hover:bg-white/5"}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Per-vendor rollup */}
      {vendorsWithDues.length > 0 && filter !== "paid" && (
        <div className="border border-white/10 rounded-sm bg-[#0f0f0f] overflow-hidden">
          <div className="px-4 py-2.5 border-b border-white/10 bg-[#141414] flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-[#F59E0B]" />
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#F59E0B]">/ Vendors with pending dues ({vendorsWithDues.length})</div>
          </div>
          <table className="w-full text-sm">
            <thead className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">
              <tr>
                <th className="text-left px-4 py-2">Vendor</th>
                <th className="text-right px-3 py-2">Pending amount</th>
                <th className="text-right px-3 py-2">Invoices</th>
                <th className="text-left px-3 py-2">Oldest since</th>
                <th className="text-right px-3 py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {vendorsWithDues.map((v) => (
                <tr key={v.vendor_id} data-testid={`adm-vendor-${v.vendor_id}`} className="border-t border-white/5 hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <div className="text-white">{v.vendor_business_name}</div>
                    <div className="text-[10px] font-mono text-neutral-500">{v.vendor_email || "no email"}</div>
                  </td>
                  <td className="px-3 py-3 text-right font-mono text-[#F59E0B] font-semibold">{fmtPrice(v.pending_amount, "INR")}</td>
                  <td className="px-3 py-3 text-right font-mono">{v.pending_count}</td>
                  <td className="px-3 py-3 font-mono text-[10px] text-neutral-500">{v.oldest_pending_at ? v.oldest_pending_at.slice(0, 10) : "—"}</td>
                  <td className="px-3 py-3 text-right">
                    <Button
                      size="sm"
                      data-testid={`adm-remind-${v.vendor_id}`}
                      disabled={busy === v.vendor_id}
                      onClick={() => sendBulkReminder(v.vendor_id)}
                      className="bg-[#F59E0B] hover:bg-[#D97706] text-black rounded-sm text-[10px] h-7 px-2"
                    >
                      <Mail className="w-3 h-3 mr-1" /> Send reminder
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Flat list */}
      <div className="border border-white/10 rounded-sm bg-[#0f0f0f] overflow-hidden">
        <div className="px-4 py-2.5 border-b border-white/10 bg-[#141414]">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ All commission invoices ({invoices.length})</div>
        </div>
        {loading ? (
          <div className="p-8 text-center text-neutral-500 text-sm">Loading…</div>
        ) : invoices.length === 0 ? (
          <div className="p-10 text-center text-neutral-500 text-sm">No {filter === "all" ? "" : filter + " "}invoices right now.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">
                <tr>
                  <th className="text-left px-3 py-2">Vendor</th>
                  <th className="text-left px-3 py-2">Booking</th>
                  <th className="text-right px-3 py-2">Booking ₹</th>
                  <th className="text-right px-3 py-2">Overtime ₹</th>
                  <th className="text-right px-3 py-2">Base comm.</th>
                  <th className="text-right px-3 py-2">OT comm.</th>
                  <th className="text-right px-3 py-2">Total</th>
                  <th className="text-left px-3 py-2">Status</th>
                  <th className="text-right px-3 py-2">Reminders</th>
                  <th className="text-right px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((i) => (
                  <tr key={i.id} data-testid={`adm-inv-${i.id}`} className="border-t border-white/5">
                    <td className="px-3 py-2">
                      <div className="text-white truncate max-w-[160px]">{i.vendor_business_name}</div>
                      <div className="text-[10px] font-mono text-neutral-500 truncate max-w-[160px]">{i.vendor_email}</div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="text-neutral-200 truncate max-w-[180px]">{i.listing_title}</div>
                      <div className="text-[10px] font-mono text-neutral-500">{i.requested_date}</div>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{fmtPrice(i.booking_total, i.currency)}</td>
                    <td className="px-3 py-2 text-right font-mono text-[#FACC15]">
                      {i.overtime_amount > 0 ? `${fmtPrice(i.overtime_amount, i.currency)} · ${i.overtime_minutes}m` : "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-neutral-300">{fmtPrice(i.base_commission_amount || 0, i.currency)}</td>
                    <td className="px-3 py-2 text-right font-mono text-[#FACC15]">
                      {i.overtime_commission_amount > 0 ? fmtPrice(i.overtime_commission_amount, i.currency) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-white font-semibold">{fmtPrice(i.commission_amount, i.currency)}</td>
                    <td className="px-3 py-2">
                      {i.status === "paid" ? (
                        <Badge className="bg-[#84CC16]/15 text-[#84CC16] border border-[#84CC16]/40">
                          <CheckCircle2 className="w-3 h-3 mr-1" /> Paid
                        </Badge>
                      ) : (
                        <Badge className="bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/40">
                          <Receipt className="w-3 h-3 mr-1" /> Pending
                        </Badge>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-[10px] text-neutral-500">
                      {i.reminders_sent || 0}{i.last_reminder_at ? ` · ${i.last_reminder_at.slice(0, 10)}` : ""}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {i.status !== "paid" && (
                        <div className="flex gap-1 justify-end">
                          <Button size="sm" data-testid={`adm-remind-single-${i.id}`} disabled={busy === i.id} onClick={() => sendReminder(i.id)}
                            className="bg-transparent border border-[#F59E0B]/40 text-[#F59E0B] hover:bg-[#F59E0B]/10 h-7 rounded-sm text-[10px] px-2">
                            <Send className="w-3 h-3 mr-1" /> Remind
                          </Button>
                          <Button size="sm" data-testid={`adm-paid-${i.id}`} disabled={busy === i.id} onClick={() => setMarkingPaid(i)}
                            className="bg-[#84CC16] hover:bg-[#65A30D] text-black h-7 rounded-sm text-[10px] px-2">
                            <CheckCircle2 className="w-3 h-3 mr-1" /> Mark paid
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <AlertDialog open={!!markingPaid} onOpenChange={(v) => !v && setMarkingPaid(null)}>
        <AlertDialogContent className="bg-[#0c0c0c] border-white/10 text-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Mark commission as paid?</AlertDialogTitle>
            <AlertDialogDescription className="text-neutral-400">
              Confirm you&apos;ve received {fmtPrice(markingPaid?.commission_amount || 0, markingPaid?.currency || "INR")} from
              <span className="text-white"> {markingPaid?.vendor_business_name}</span>. This closes the invoice and it will
              move to the &ldquo;Paid&rdquo; view.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-transparent border-white/10 text-neutral-400">Cancel</AlertDialogCancel>
            <AlertDialogAction data-testid="adm-mark-paid-confirm" onClick={confirmPaid} className="bg-[#84CC16] hover:bg-[#65A30D] text-black">
              Yes, mark paid
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
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
