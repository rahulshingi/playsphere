import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Receipt } from "lucide-react";

/**
 * InvoiceSettingsPanel — vendor edits the fields that appear on every generated invoice
 * (GSTIN, business name override, billing address, phone, email, tax %, footer note).
 * Mounted below OfflineModeCard on the vendor dashboard.
 */
export default function InvoiceSettingsPanel({ vendor, onSaved }) {
  const [form, setForm] = useState({
    gstin: "", invoice_business_name: "", invoice_address: "",
    invoice_phone: "", invoice_email: "", invoice_tax_percent: 18,
    invoice_footer_note: "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!vendor) return;
    setForm({
      gstin: vendor.gstin || "",
      invoice_business_name: vendor.invoice_business_name || "",
      invoice_address: vendor.invoice_address || "",
      invoice_phone: vendor.invoice_phone || "",
      invoice_email: vendor.invoice_email || "",
      invoice_tax_percent: vendor.invoice_tax_percent ?? 18,
      invoice_footer_note: vendor.invoice_footer_note || "",
    });
  }, [vendor]);

  const save = async () => {
    setBusy(true);
    try {
      await api.patch("/vendors/me", { ...form, invoice_tax_percent: Number(form.invoice_tax_percent) || 0 });
      toast.success("Invoice settings saved");
      onSaved?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  if (!vendor?.offline_mode) return null;

  return (
    <div data-testid="invoice-settings" className="mt-6 border border-[#FACC15]/30 rounded-sm bg-gradient-to-br from-[#FACC15]/5 to-transparent p-5">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15] mb-2 flex items-center gap-1.5">
        <Receipt className="w-3 h-3" /> / Invoice settings
      </div>
      <p className="text-xs text-neutral-400 mb-3">These fields appear on every invoice you generate from the Offline business tab.</p>
      <div className="grid md:grid-cols-2 gap-3">
        <Fld label="GSTIN"><Input data-testid="inv-set-gstin" value={form.gstin} onChange={(e) => setForm({ ...form, gstin: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
        <Fld label="Business name (as printed)"><Input data-testid="inv-set-bname" placeholder="Defaults to your vendor business name" value={form.invoice_business_name} onChange={(e) => setForm({ ...form, invoice_business_name: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
        <Fld label="Phone"><Input data-testid="inv-set-phone" value={form.invoice_phone} onChange={(e) => setForm({ ...form, invoice_phone: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
        <Fld label="Email"><Input data-testid="inv-set-email" value={form.invoice_email} onChange={(e) => setForm({ ...form, invoice_email: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
        <Fld label="Tax % (default GST)"><Input data-testid="inv-set-tax" type="number" min="0" max="100" step="0.5" value={form.invoice_tax_percent} onChange={(e) => setForm({ ...form, invoice_tax_percent: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld>
        <div className="md:col-span-2"><Fld label="Billing address"><Textarea data-testid="inv-set-address" rows={2} value={form.invoice_address} onChange={(e) => setForm({ ...form, invoice_address: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld></div>
        <div className="md:col-span-2"><Fld label="Footer note (T&amp;C, thank-you line)"><Textarea data-testid="inv-set-footer" rows={2} value={form.invoice_footer_note} onChange={(e) => setForm({ ...form, invoice_footer_note: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Fld></div>
      </div>
      <Button data-testid="inv-set-save" onClick={save} disabled={busy} className="mt-3 bg-[#FACC15] hover:bg-[#eab308] text-black font-semibold rounded-sm">{busy ? "Saving…" : "Save invoice settings"}</Button>
    </div>
  );
}

function Fld({ label, children }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}
