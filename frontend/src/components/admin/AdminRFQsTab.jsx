import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Inbox, ArrowLeft, Sparkles, Send, FileText, Save, Trash2, Calculator, MessageSquare } from "lucide-react";

/**
 * AdminRFQsTab — Phase 3: Admin RFQ inbox + Cost Sheet + Quotation Builder + Chat.
 *
 * List view = inbox (filter by status).
 * Detail view = one screen with three collapsible sections:
 *   1) RFQ + event details snapshot (read-only)
 *   2) Internal cost sheet (auto-suggest vendors, edit unit rates)
 *   3) Quotation builder (line-level pricing: markup % or fixed price)
 *   4) Chat (visible once first quote is sent)
 */
export default function AdminRFQsTab() {
  const [selected, setSelected] = useState(null);
  if (selected) return <RFQDetail rfqId={selected} onBack={() => setSelected(null)} />;
  return <RFQInbox onOpen={setSelected} />;
}

// ─────────────── Inbox ───────────────
function RFQInbox({ onOpen }) {
  const [rfqs, setRfqs] = useState([]);
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get(`/admin/rfqs${status === "all" ? "" : `?status=${status}`}`)
      .then((r) => setRfqs(r.data || []))
      .finally(() => setLoading(false));
  };
  useEffect(load, [status]); // eslint-disable-line

  const counts = useMemo(() => rfqs.reduce((a, r) => ({ ...a, [r.status]: (a[r.status] || 0) + 1 }), {}), [rfqs]);

  const TABS = [
    { key: "all", label: `All (${rfqs.length})`, color: "#06B6D4" },
    { key: "submitted", label: `New (${counts.submitted || 0})`, color: "#FACC15" },
    { key: "under_review", label: `Under review (${counts.under_review || 0})`, color: "#F59E0B" },
    { key: "quoted", label: `Quoted (${counts.quoted || 0})`, color: "#84CC16" },
    { key: "negotiation", label: `Negotiation (${counts.negotiation || 0})`, color: "#EC4899" },
    { key: "approved", label: `Approved (${counts.approved || 0})`, color: "#84CC16" },
    { key: "cancelled", label: `Cancelled (${counts.cancelled || 0})`, color: "#71717A" },
  ];

  return (
    <div data-testid="admin-rfqs" className="space-y-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Corporate Services · Admin RFQ Inbox</div>
        <h2 className="text-2xl font-display tracking-wide mt-1">Requests for Quote</h2>
        <p className="text-sm text-neutral-500 mt-1">Review incoming HR/Organiser RFQs, compose internal cost sheets and send priced quotations.</p>
      </div>

      <div className="flex gap-1 flex-wrap" data-testid="arfq-status-tabs">
        {TABS.map((t) => (
          <button key={t.key} data-testid={`arfq-filter-${t.key}`}
            onClick={() => setStatus(t.key)}
            className={`text-[10px] font-mono uppercase px-2.5 py-1 rounded-sm border ${status === t.key ? "text-black" : "border-white/10 text-neutral-400 hover:bg-white/5"}`}
            style={status === t.key ? { background: t.color, borderColor: t.color } : {}}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? <div className="text-neutral-500 text-sm">Loading…</div> : (
        <div className="border border-white/10 rounded-sm bg-[#0f0f0f] overflow-hidden">
          {rfqs.length === 0 && (
            <div className="text-neutral-500 text-sm p-10 text-center">
              <Inbox className="w-8 h-8 mx-auto text-neutral-600 mb-2" />
              No RFQs in this view.
            </div>
          )}
          {rfqs.map((r) => (
            <button key={r.id} data-testid={`arfq-row-${r.id}`} onClick={() => onOpen(r.id)}
              className="w-full text-left border-b border-white/5 px-4 py-3 hover:bg-white/[0.02] flex justify-between items-start gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-white font-semibold">{r.event?.event_name || "Untitled event"}</span>
                  <StatusBadge status={r.status} />
                  {r.latest_quote && (
                    <span className="text-[9px] font-mono uppercase text-[#84CC16] border border-[#84CC16]/40 rounded px-1">
                      v{r.latest_quote.version} · ₹{Number(r.latest_quote.total || 0).toLocaleString("en-IN")}
                    </span>
                  )}
                </div>
                <div className="text-[10px] font-mono text-neutral-500 mt-1">
                  {r.hr_name || r.hr_email} · {r.company_name || "—"} · {r.package_name}
                  {r.event?.city && ` · ${r.event.city}`}
                  {r.event?.preferred_date && ` · ${r.event.preferred_date}`}
                </div>
              </div>
              <div className="text-[10px] font-mono text-neutral-500 shrink-0">
                {(r.created_at || "").slice(0, 10)}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────── Detail ───────────────
function RFQDetail({ rfqId, onBack }) {
  const [rfq, setRfq] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.get(`/rfqs/${rfqId}`).then((r) => setRfq(r.data));
  useEffect(() => { load(); }, [rfqId]); // eslint-disable-line

  const markUnderReview = async () => {
    setBusy(true);
    try {
      await api.post(`/admin/rfqs/${rfqId}/mark-under-review`);
      toast.success("Marked under review"); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  if (!rfq) return <div className="text-neutral-500 text-sm">Loading…</div>;
  const chatOpen = ["quoted", "negotiation", "approved", "completed"].includes(rfq.status);

  return (
    <div data-testid="admin-rfq-detail" className="space-y-5">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <button onClick={onBack} className="text-xs text-neutral-400 hover:text-white inline-flex items-center gap-1">
          <ArrowLeft className="w-3 h-3" /> Back to inbox
        </button>
        <StatusBadge status={rfq.status} />
      </div>

      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ RFQ · {rfq.id.slice(0, 8)}</div>
        <h2 className="text-2xl font-display tracking-wide mt-1">{rfq.event?.event_name}</h2>
        <div className="text-xs text-neutral-500 mt-1">
          {rfq.package_name} · {rfq.hr_name || rfq.hr_email} · {rfq.company_name || "—"} · created {(rfq.created_at || "").slice(0, 10)}
        </div>
      </div>

      {rfq.status === "submitted" && (
        <Button data-testid="arfq-mark-review" disabled={busy} onClick={markUnderReview}
          className="bg-[#F59E0B] hover:bg-[#D97706] text-black rounded-sm">
          Start review
        </Button>
      )}

      <EventSnapshot rfq={rfq} />

      <CostSheet rfq={rfq} onChange={load} />

      <QuotationBuilder rfq={rfq} onChange={load} />

      {rfq.status === "approved" || rfq.status === "completed" ? (
        <InvoicePanel rfq={rfq} onChange={load} />
      ) : null}

      {chatOpen && <NegotiationChat rfqId={rfq.id} />}
    </div>
  );
}

// ─────────────── Invoice Panel (admin) ───────────────
function InvoicePanel({ rfq, onChange }) {
  const [inv, setInv] = useState(null);
  const [busy, setBusy] = useState(false);
  const backend = process.env.REACT_APP_BACKEND_URL;

  const load = () => api.get(`/rfqs/${rfq.id}/invoice`).then((r) => setInv(r.data)).catch(() => setInv(null));
  useEffect(() => { load(); }, [rfq.id]); // eslint-disable-line

  const generate = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/admin/rfqs/${rfq.id}/invoice`);
      setInv(r.data);
      toast.success(`Invoice ${r.data.invoice_number} generated`);
      onChange?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const markPaid = async () => {
    const note = window.prompt("Payment reference / note (bank txn ID, cheque #, etc.):", "");
    if (note === null) return;
    setBusy(true);
    try {
      const r = await api.post(`/admin/rfqs/${rfq.id}/invoice/mark-paid`, { note });
      setInv(r.data); toast.success("Invoice marked paid"); onChange?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const ensurePayLink = async () => {
    setBusy(true);
    try {
      const r = await api.post(`/rfqs/${rfq.id}/invoice/paylink`);
      setInv(r.data);
      if (r.data.pay_link_id === "mock") toast.warning("Razorpay keys missing — mock pay-link returned. Add RAZORPAY_KEY_ID + SECRET to backend/.env.");
      else toast.success("Pay-link ready");
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  return (
    <section className="border border-[#84CC16]/30 bg-[#84CC16]/5 rounded-sm p-4" data-testid="arfq-invoice">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16]">/ Invoice</div>
          {inv ? (
            <div className="mt-1 text-white text-sm font-semibold flex items-center gap-2 flex-wrap">
              <FileText className="w-4 h-4 text-[#84CC16]" />
              {inv.invoice_number} · ₹{Number(inv.amount).toLocaleString("en-IN")}
              <InvoiceStatusBadge status={inv.status} />
            </div>
          ) : (
            <div className="mt-1 text-neutral-400 text-xs">Invoice will be generated automatically once HR accepts. You can also generate manually below.</div>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          {!inv && (
            <Button data-testid="arfq-inv-generate" size="sm" disabled={busy} onClick={generate}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black"><FileText className="w-3.5 h-3.5 mr-1" /> Generate invoice</Button>
          )}
          {inv && (
            <>
              <a href={`${backend}/api/rfqs/${rfq.id}/invoice/pdf`} target="_blank" rel="noreferrer"
                data-testid="arfq-inv-download"
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-sm border border-white/20 text-xs text-white hover:bg-white/10">
                <FileText className="w-3.5 h-3.5" /> Download PDF
              </a>
              {!inv.pay_link_url && inv.status !== "paid" && (
                <Button size="sm" disabled={busy} onClick={ensurePayLink} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black">
                  Create pay-link
                </Button>
              )}
              {inv.pay_link_url && (
                <a href={inv.pay_link_url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-sm bg-[#06B6D4] text-black text-xs font-semibold hover:bg-[#0891B2]">
                  Pay-link ↗
                </a>
              )}
              {inv.status !== "paid" && (
                <Button data-testid="arfq-inv-mark-paid" size="sm" disabled={busy} onClick={markPaid}
                  variant="outline" className="border-[#84CC16]/40 bg-transparent text-[#84CC16] hover:bg-[#84CC16]/10">
                  Mark paid
                </Button>
              )}
            </>
          )}
        </div>
      </div>
      {inv && (
        <div className="mt-3 text-[10px] font-mono text-neutral-500 flex gap-4 flex-wrap">
          <span>issued {(inv.issued_at || "").slice(0, 10)}</span>
          <span>due {(inv.due_at || "").slice(0, 10)}</span>
          {inv.paid_at && <span className="text-[#84CC16]">paid {inv.paid_at.slice(0, 10)}</span>}
          {inv.razorpay_payment_id && <span>razorpay {inv.razorpay_payment_id}</span>}
          {inv.pay_link_id === "mock" && <span className="text-[#FACC15]">⚠ mock pay-link · add Razorpay keys</span>}
        </div>
      )}
    </section>
  );
}

function InvoiceStatusBadge({ status }) {
  const tone = {
    unpaid:   "bg-[#FACC15]/15 text-[#FACC15] border-[#FACC15]/40",
    paid:     "bg-[#84CC16]/15 text-[#84CC16] border-[#84CC16]/40",
    cancelled:"bg-white/5 text-neutral-500 border-white/10",
  }[status] || "bg-white/5 text-neutral-400 border-white/10";
  return <Badge className={`border ${tone} text-[9px] font-mono uppercase tracking-widest`}>{status}</Badge>;
}

// ─────────────── Event snapshot ───────────────
function EventSnapshot({ rfq }) {
  return (
    <section className="border border-white/10 bg-[#141414] rounded-sm p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15] mb-2">/ Event snapshot</div>
      <div className="grid md:grid-cols-3 gap-3 text-sm">
        <KV label="Date">{rfq.event?.preferred_date}</KV>
        <KV label="Time">{rfq.event?.preferred_time || "—"}</KV>
        <KV label="Sport">{rfq.event?.sport || "—"}</KV>
        <KV label="Players / Spectators">{`${rfq.event?.num_players || "—"} / ${rfq.event?.num_spectators || "—"}`}</KV>
        <KV label="City">{rfq.event?.city || "—"}</KV>
        <KV label="State">{rfq.event?.state || "—"}</KV>
        <KV label="Venue" className="md:col-span-2">{rfq.event?.venue || "—"}</KV>
        <KV label="Expected budget">{rfq.expected_budget || "—"}</KV>
      </div>
      {rfq.special_instructions && (
        <div className="mt-3 text-xs text-neutral-300 border-t border-white/5 pt-3">
          <span className="text-[10px] font-mono uppercase text-neutral-500">/ Instructions: </span>
          {rfq.special_instructions}
        </div>
      )}
    </section>
  );
}

// ─────────────── Cost Sheet with vendor auto-suggest ───────────────
function CostSheet({ rfq, onChange }) {
  const [sheet, setSheet] = useState(null);
  const [suggestMap, setSuggestMap] = useState({}); // service_id → suggestions[]
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const s = await api.get(`/admin/rfqs/${rfq.id}/cost-sheet`);
    setSheet(s.data);
    const g = await api.get(`/admin/rfqs/${rfq.id}/suggest-vendors`);
    const map = {};
    for (const svc of g.data.services || []) map[svc.service_id] = svc.suggestions || [];
    setSuggestMap(map);
  };
  useEffect(() => { load(); }, [rfq.id]); // eslint-disable-line

  const updateLine = (idx, patch) => {
    setSheet((s) => ({ ...s, lines: s.lines.map((l, i) => i === idx ? { ...l, ...patch } : l) }));
  };
  const applyVendor = (idx, suggestion) => {
    updateLine(idx, {
      vendor_id: suggestion.vendor_id,
      vendor_name: suggestion.vendor_name,
      unit_rate: suggestion.rate,
      unit_type: suggestion.unit_type,
    });
  };
  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put(`/admin/rfqs/${rfq.id}/cost-sheet`, { lines: sheet.lines });
      setSheet(r.data);
      toast.success("Cost sheet saved");
      onChange?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
    finally { setSaving(false); }
  };

  if (!sheet) return null;

  const total = sheet.lines.reduce((sum, l) => sum + (Number(l.quantity) || 0) * (Number(l.unit_rate) || 0), 0);

  return (
    <section className="border border-[#F59E0B]/30 bg-[#F59E0B]/5 rounded-sm p-4">
      <div className="flex items-start justify-between gap-3 flex-wrap mb-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#F59E0B]">/ Internal cost sheet</div>
          <div className="text-xs text-neutral-400 mt-1">Auto-suggest picks vendors by city → preferred → lowest rate. Internal only — never surfaced to HR.</div>
        </div>
        <Button data-testid="arfq-cs-save" size="sm" disabled={saving} onClick={save} className="bg-[#84CC16] hover:bg-[#65A30D] text-black">
          <Save className="w-3.5 h-3.5 mr-1" /> Save cost sheet
        </Button>
      </div>

      <div className="border border-white/10 rounded-sm bg-black/40 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left font-mono uppercase text-[10px] text-neutral-500 border-b border-white/10">
              <th className="px-3 py-2">Line</th>
              <th className="px-3 py-2 w-[220px]">Vendor</th>
              <th className="px-3 py-2 w-20">Qty</th>
              <th className="px-3 py-2 w-32">Unit ₹</th>
              <th className="px-3 py-2 w-24 text-right">Cost ₹</th>
            </tr>
          </thead>
          <tbody>
            {sheet.lines.map((l, idx) => {
              const suggestions = l.kind === "service" ? (suggestMap[l.service_id] || []) : [];
              return (
                <tr key={l.line_id} data-testid={`arfq-cs-line-${idx}`} className="border-b border-white/5">
                  <td className="px-3 py-2">
                    <div className="text-white">
                      {l.name}
                      <span className="ml-1 text-[9px] font-mono uppercase text-neutral-500">{l.kind}</span>
                    </div>
                    <div className="text-[10px] font-mono text-neutral-500">{l.unit_type}</div>
                  </td>
                  <td className="px-3 py-2">
                    <Select value={l.vendor_id || "__none"} onValueChange={(v) => {
                      if (v === "__none") { updateLine(idx, { vendor_id: null, vendor_name: null }); return; }
                      const sug = suggestions.find((s) => s.vendor_id === v);
                      if (sug) applyVendor(idx, sug);
                      else updateLine(idx, { vendor_id: v });
                    }}>
                      <SelectTrigger data-testid={`arfq-cs-vendor-${idx}`} className="bg-black/60 border-white/10 text-white h-8 text-xs">
                        <SelectValue placeholder="Assign vendor…" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#141414] text-white border-white/10 max-h-72">
                        <SelectItem value="__none">— None —</SelectItem>
                        {suggestions.map((s) => (
                          <SelectItem key={s.vendor_id} value={s.vendor_id}>
                            {s.city_match && "📍 "}
                            {s.preferred && "★ "}
                            {s.vendor_name} · ₹{s.rate} {s.unit_type}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {suggestions[0] && !l.vendor_id && (
                      <button onClick={() => applyVendor(idx, suggestions[0])}
                        data-testid={`arfq-cs-suggest-${idx}`}
                        className="text-[10px] font-mono uppercase text-[#06B6D4] hover:underline mt-1 inline-flex items-center gap-1">
                        <Sparkles className="w-3 h-3" /> auto-pick {suggestions[0].vendor_name}
                      </button>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <Input data-testid={`arfq-cs-qty-${idx}`} type="number" min="0" value={l.quantity}
                      onChange={(e) => updateLine(idx, { quantity: Number(e.target.value) || 0 })}
                      className="bg-black/60 border-white/10 text-white h-8 text-xs" />
                  </td>
                  <td className="px-3 py-2">
                    <Input data-testid={`arfq-cs-rate-${idx}`} type="number" min="0" step="0.01" value={l.unit_rate}
                      onChange={(e) => updateLine(idx, { unit_rate: Number(e.target.value) || 0 })}
                      className="bg-black/60 border-white/10 text-white h-8 text-xs" />
                  </td>
                  <td className="px-3 py-2 text-right text-white font-mono">
                    ₹{((l.quantity || 0) * (l.unit_rate || 0)).toFixed(2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-[#F59E0B]/40">
              <td colSpan={4} className="px-3 py-2 text-right font-mono uppercase text-[10px] text-neutral-400">Total internal cost</td>
              <td className="px-3 py-2 text-right text-[#F59E0B] font-bold" data-testid="arfq-cs-total">₹{total.toFixed(2)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

// ─────────────── Quotation Builder ───────────────
function QuotationBuilder({ rfq, onChange }) {
  const [quotes, setQuotes] = useState([]);
  const [sheet, setSheet] = useState(null);
  const [pricing, setPricing] = useState({}); // line_id → {pricing_mode, margin_percent, selling_price}
  const [defaults, setDefaults] = useState({ default_margin_percent: 25, discount: 0, tax_percent: 18, notes: "", valid_until: "" });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const [q, s] = await Promise.all([
      api.get(`/admin/rfqs/${rfq.id}/quotations`),
      api.get(`/admin/rfqs/${rfq.id}/cost-sheet`),
    ]);
    setQuotes(q.data || []);
    setSheet(s.data);
    // Initialise pricing map from cost-sheet lines
    const seed = {};
    for (const l of s.data.lines || []) {
      seed[l.line_id] = { pricing_mode: "markup", margin_percent: 25, selling_price: 0 };
    }
    setPricing(seed);
  };
  useEffect(() => { load(); }, [rfq.id]); // eslint-disable-line

  const setLinePricing = (line_id, patch) => setPricing((p) => ({ ...p, [line_id]: { ...p[line_id], ...patch } }));

  const preview = useMemo(() => {
    if (!sheet) return null;
    const rows = sheet.lines.map((l) => {
      const p = pricing[l.line_id] || { pricing_mode: "markup", margin_percent: defaults.default_margin_percent };
      const cost = (l.quantity || 0) * (l.unit_rate || 0);
      let selling;
      if (p.pricing_mode === "fixed") selling = Number(p.selling_price) || 0;
      else selling = cost * (1 + (Number(p.margin_percent) || 0) / 100);
      return { line_id: l.line_id, name: l.name, quantity: l.quantity, unit_type: l.unit_type, cost, selling: Math.round(selling * 100) / 100 };
    });
    const subtotal = rows.reduce((s, r) => s + r.selling, 0);
    const discount = Number(defaults.discount) || 0;
    const taxable = Math.max(0, subtotal - discount);
    const tax = taxable * (Number(defaults.tax_percent) || 0) / 100;
    const total = taxable + tax;
    const internal = rows.reduce((s, r) => s + r.cost, 0);
    return { rows, subtotal, discount, tax, total, internal, margin: total - internal };
  }, [sheet, pricing, defaults]);

  const buildDraft = async () => {
    if (!sheet?.lines?.length) return toast.error("Save the cost sheet first");
    setBusy(true);
    try {
      const payload = {
        default_margin_percent: Number(defaults.default_margin_percent) || 0,
        discount: Number(defaults.discount) || 0,
        tax_percent: Number(defaults.tax_percent) || 0,
        notes: defaults.notes,
        valid_until: defaults.valid_until,
        lines: sheet.lines.map((l) => ({
          line_id: l.line_id,
          pricing_mode: pricing[l.line_id]?.pricing_mode || "markup",
          margin_percent: Number(pricing[l.line_id]?.margin_percent) || 0,
          selling_price: Number(pricing[l.line_id]?.selling_price) || 0,
        })),
      };
      await api.post(`/admin/rfqs/${rfq.id}/quotations`, payload);
      toast.success("Draft quotation created");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const sendQuote = async (quoteId) => {
    if (!window.confirm("Send this quotation to HR? They will see prices and can Accept / Reject.")) return;
    setBusy(true);
    try {
      await api.post(`/admin/rfqs/${rfq.id}/quotations/${quoteId}/send`);
      toast.success("Quotation sent"); load(); onChange?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const deleteDraft = async (quoteId) => {
    if (!window.confirm("Delete this draft?")) return;
    await api.delete(`/admin/rfqs/${rfq.id}/quotations/${quoteId}`);
    toast.success("Draft deleted"); load();
  };

  if (!sheet) return null;

  return (
    <section className="border border-[#06B6D4]/30 bg-[#06B6D4]/5 rounded-sm p-4">
      <div className="flex items-start justify-between gap-3 flex-wrap mb-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4]">/ Quotation builder</div>
          <div className="text-xs text-neutral-400 mt-1">Per-line markup or fixed price. Preview updates live. Draft first, then Send when ready.</div>
        </div>
        <div className="flex gap-2">
          <Button data-testid="arfq-quote-build" size="sm" disabled={busy} onClick={buildDraft} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black">
            <Calculator className="w-3.5 h-3.5 mr-1" /> Create draft
          </Button>
        </div>
      </div>

      <div className="grid md:grid-cols-4 gap-2 mb-3">
        <F label="Default margin %">
          <Input data-testid="arfq-default-margin" type="number" step="0.1" value={defaults.default_margin_percent}
            onChange={(e) => setDefaults({ ...defaults, default_margin_percent: e.target.value })}
            className="bg-black/60 border-white/10 text-white text-xs h-8" />
        </F>
        <F label="Discount ₹">
          <Input data-testid="arfq-discount" type="number" step="1" value={defaults.discount}
            onChange={(e) => setDefaults({ ...defaults, discount: e.target.value })}
            className="bg-black/60 border-white/10 text-white text-xs h-8" />
        </F>
        <F label="Tax %">
          <Input data-testid="arfq-tax" type="number" step="0.1" value={defaults.tax_percent}
            onChange={(e) => setDefaults({ ...defaults, tax_percent: e.target.value })}
            className="bg-black/60 border-white/10 text-white text-xs h-8" />
        </F>
        <F label="Valid until">
          <Input type="date" value={defaults.valid_until}
            onChange={(e) => setDefaults({ ...defaults, valid_until: e.target.value })}
            className="bg-black/60 border-white/10 text-white text-xs h-8" />
        </F>
      </div>

      <div className="border border-white/10 rounded-sm bg-black/40 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left font-mono uppercase text-[10px] text-neutral-500 border-b border-white/10">
              <th className="px-3 py-2">Line</th>
              <th className="px-3 py-2 w-20 text-right">Cost</th>
              <th className="px-3 py-2 w-24">Mode</th>
              <th className="px-3 py-2 w-24">Margin %</th>
              <th className="px-3 py-2 w-28">Fixed ₹</th>
              <th className="px-3 py-2 w-24 text-right">Selling ₹</th>
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((r, idx) => {
              const p = pricing[r.line_id] || { pricing_mode: "markup", margin_percent: defaults.default_margin_percent };
              return (
                <tr key={r.line_id} className="border-b border-white/5">
                  <td className="px-3 py-2 text-white">
                    {r.name}
                    <span className="ml-1 text-[9px] font-mono uppercase text-neutral-500">× {r.quantity}</span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-neutral-400">₹{r.cost.toFixed(2)}</td>
                  <td className="px-3 py-2">
                    <Select value={p.pricing_mode} onValueChange={(v) => setLinePricing(r.line_id, { pricing_mode: v })}>
                      <SelectTrigger data-testid={`arfq-q-mode-${idx}`} className="bg-black/60 border-white/10 text-white h-8 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-[#141414] text-white border-white/10">
                        <SelectItem value="markup">Markup</SelectItem>
                        <SelectItem value="fixed">Fixed</SelectItem>
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="px-3 py-2">
                    <Input type="number" step="0.1" disabled={p.pricing_mode === "fixed"} value={p.margin_percent ?? defaults.default_margin_percent}
                      onChange={(e) => setLinePricing(r.line_id, { margin_percent: e.target.value })}
                      className="bg-black/60 border-white/10 text-white h-8 text-xs" />
                  </td>
                  <td className="px-3 py-2">
                    <Input type="number" step="0.01" disabled={p.pricing_mode === "markup"} value={p.selling_price || 0}
                      onChange={(e) => setLinePricing(r.line_id, { selling_price: e.target.value })}
                      className="bg-black/60 border-white/10 text-white h-8 text-xs" />
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-[#84CC16]">₹{r.selling.toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3">
        <Textarea rows={2} value={defaults.notes} onChange={(e) => setDefaults({ ...defaults, notes: e.target.value })}
          placeholder="Cover note / terms for the HR (optional)"
          className="bg-black/40 border-white/10 text-white text-sm" />
      </div>

      <div className="mt-3 grid md:grid-cols-2 gap-3">
        <div className="border border-white/10 rounded-sm bg-black/40 p-3 text-xs space-y-1">
          <TotalRow label="Subtotal">₹{preview.subtotal.toFixed(2)}</TotalRow>
          <TotalRow label={`Discount`}>− ₹{preview.discount.toFixed(2)}</TotalRow>
          <TotalRow label={`Tax (${defaults.tax_percent || 0}%)`}>₹{preview.tax.toFixed(2)}</TotalRow>
          <TotalRow label="Total for HR" bold accent="#06B6D4">
            <span data-testid="arfq-preview-total">₹{preview.total.toFixed(2)}</span>
          </TotalRow>
        </div>
        <div className="border border-[#84CC16]/30 rounded-sm bg-[#84CC16]/5 p-3 text-xs space-y-1">
          <div className="font-mono text-[10px] uppercase text-neutral-500">/ Admin-only</div>
          <TotalRow label="Internal cost">₹{preview.internal.toFixed(2)}</TotalRow>
          <TotalRow label="Gross margin" bold accent="#84CC16">
            ₹{preview.margin.toFixed(2)} <span className="text-[10px] text-neutral-500">
              ({preview.total > 0 ? ((preview.margin / preview.total) * 100).toFixed(1) : "0.0"}%)
            </span>
          </TotalRow>
        </div>
      </div>

      {quotes.length > 0 && (
        <div className="mt-5">
          <div className="font-mono text-[10px] uppercase text-neutral-500 mb-2">/ Quotation history</div>
          <div className="space-y-2">
            {quotes.map((q) => (
              <div key={q.id} data-testid={`arfq-quote-${q.version}`}
                className="border border-white/10 rounded-sm bg-black/40 p-3 flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-white text-sm font-semibold">v{q.version}</span>
                    <QuoteStatusBadge status={q.status} />
                    <span className="text-[10px] font-mono uppercase text-neutral-500">
                      total ₹{q.total_selling.toFixed(2)} · margin {q.gross_margin_percent}%
                    </span>
                  </div>
                  <div className="text-[10px] font-mono text-neutral-500 mt-1">
                    created {(q.created_at || "").slice(0, 10)}
                    {q.sent_at && ` · sent ${q.sent_at.slice(0, 10)}`}
                    {q.rejection_reason && ` · reason: ${q.rejection_reason.slice(0, 80)}`}
                  </div>
                </div>
                <div className="flex gap-2">
                  {q.status === "draft" && (
                    <>
                      <Button data-testid={`arfq-quote-send-${q.version}`} size="sm" onClick={() => sendQuote(q.id)}
                        className="bg-[#84CC16] hover:bg-[#65A30D] text-black">
                        <Send className="w-3.5 h-3.5 mr-1" /> Send to HR
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => deleteDraft(q.id)} className="text-[#FF3B30]">
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

// ─────────────── Chat ───────────────
function NegotiationChat({ rfqId }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");

  const load = () => api.get(`/rfqs/${rfqId}/messages`).then((r) => setMessages(r.data || []));
  useEffect(() => { load(); }, [rfqId]); // eslint-disable-line

  const send = async () => {
    if (!text.trim()) return;
    try {
      await api.post(`/rfqs/${rfqId}/messages`, { body: text });
      setText(""); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <section className="border border-[#EC4899]/30 bg-[#EC4899]/5 rounded-sm p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#EC4899] mb-3 flex items-center gap-2">
        <MessageSquare className="w-3.5 h-3.5" /> / Negotiation chat
      </div>
      <div className="border border-white/10 rounded-sm bg-black/40 max-h-72 overflow-y-auto p-3 space-y-2">
        {messages.length === 0 && <div className="text-neutral-500 text-xs text-center py-8">No messages yet.</div>}
        {messages.map((m) => (
          <div key={m.id} data-testid={`arfq-msg-${m.id}`} className={`flex ${m.sender_role === "admin" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[75%] rounded-sm px-3 py-2 text-sm ${m.sender_role === "admin" ? "bg-[#06B6D4]/15 text-[#e0f2fe] border border-[#06B6D4]/30" : "bg-white/5 text-neutral-200 border border-white/10"}`}>
              <div className="text-[9px] font-mono uppercase text-neutral-500 mb-1">
                {m.sender_role === "admin" ? "Admin" : (m.sender_name || "HR")} · {(m.created_at || "").slice(11, 16)}
              </div>
              <div className="whitespace-pre-wrap">{m.body}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-2">
        <Input data-testid="arfq-chat-input" value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Type reply…"
          className="bg-black/40 border-white/10 text-white text-sm" />
        <Button data-testid="arfq-chat-send" size="sm" onClick={send} className="bg-[#EC4899] hover:bg-[#db2777] text-white">
          <Send className="w-3.5 h-3.5" />
        </Button>
      </div>
    </section>
  );
}

// ─────────────── Helpers ───────────────
function StatusBadge({ status }) {
  const tone = {
    draft:         "bg-white/5 text-neutral-400 border-white/10",
    submitted:     "bg-[#FACC15]/15 text-[#FACC15] border-[#FACC15]/40",
    under_review:  "bg-[#F59E0B]/15 text-[#F59E0B] border-[#F59E0B]/40",
    quoted:        "bg-[#84CC16]/15 text-[#84CC16] border-[#84CC16]/40",
    negotiation:   "bg-[#EC4899]/15 text-[#EC4899] border-[#EC4899]/40",
    approved:      "bg-[#84CC16]/15 text-[#84CC16] border-[#84CC16]/40",
    rejected:      "bg-[#FF3B30]/15 text-[#FF3B30] border-[#FF3B30]/40",
    cancelled:     "bg-white/5 text-neutral-500 border-white/10",
  }[status] || "bg-white/5 text-neutral-400 border-white/10";
  return <Badge className={`border ${tone} text-[10px] font-mono uppercase tracking-widest`}>{(status || "").replace("_", " ")}</Badge>;
}
function QuoteStatusBadge({ status }) {
  const tone = {
    draft:      "bg-white/5 text-neutral-400 border-white/10",
    sent:       "bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/40",
    accepted:   "bg-[#84CC16]/15 text-[#84CC16] border-[#84CC16]/40",
    rejected:   "bg-[#FF3B30]/15 text-[#FF3B30] border-[#FF3B30]/40",
    superseded: "bg-white/5 text-neutral-500 border-white/10",
  }[status] || "bg-white/5 text-neutral-400 border-white/10";
  return <Badge className={`border ${tone} text-[9px] font-mono uppercase tracking-widest`}>{status}</Badge>;
}
function KV({ label, children, className = "" }) {
  return (
    <div className={className}>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="text-neutral-200 mt-0.5">{children || "—"}</div>
    </div>
  );
}
function F({ label, children }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase text-neutral-500">{label}</Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
function TotalRow({ label, children, bold, accent }) {
  return (
    <div className="flex items-center justify-between">
      <span className="font-mono uppercase text-[10px] text-neutral-500">{label}</span>
      <span className={`font-mono ${bold ? "text-sm font-bold" : ""}`} style={accent ? { color: accent } : {}}>{children}</span>
    </div>
  );
}
