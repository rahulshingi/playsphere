import { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Package, Clock, CheckCircle2, XCircle, MessageSquare, ArrowRight, FileText } from "lucide-react";

/**
 * MyRFQs (Phase 2) — HR/Organiser list + detail of their Corporate Services
 * requests. Detail view shows the package snapshot, event details and
 * negotiation timeline. Quotation actions (approve / counter / message) land
 * in Phase 3.
 */
export function MyRFQsList() {
  const [rfqs, setRfqs] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const { user, isCompanyAdmin, ready } = useAuth();

  useEffect(() => {
    if (!ready) return;
    if (!isCompanyAdmin) return;
    api.get(`/rfqs/mine${filter === "all" ? "" : `?status=${filter}`}`)
      .then((r) => setRfqs(r.data || []))
      .catch(() => setRfqs([]))
      .finally(() => setLoading(false));
  }, [ready, isCompanyAdmin, filter]);

  if (ready && !user) {
    return (
      <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav />
        <div className="max-w-md mx-auto text-center pt-24 pb-24 px-6">
          <FileText className="w-10 h-10 mx-auto text-[#06B6D4]" />
          <h1 className="font-display text-3xl mt-4">Sign in to view your RFQs</h1>
          <Link to="/login" className="mt-6 inline-block px-6 py-3 bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm font-semibold">Sign in</Link>
        </div>
      <Footer /></div>
    );
  }
  if (ready && user && !isCompanyAdmin) {
    return (
      <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav />
        <div className="max-w-md mx-auto text-center pt-24 pb-24 px-6">
          <XCircle className="w-10 h-10 mx-auto text-[#FF3B30]" />
          <h1 className="font-display text-3xl mt-4">Not available for your account</h1>
          <p className="text-neutral-400 mt-2 text-sm">RFQs are for HR / Organiser accounts.</p>
        </div>
      <Footer /></div>
    );
  }

  const counts = rfqs.reduce((acc, r) => { acc[r.status] = (acc[r.status] || 0) + 1; return acc; }, {});
  const TABS = [
    { key: "all", label: `All (${rfqs.length})` },
    { key: "submitted", label: `Submitted (${counts.submitted || 0})` },
    { key: "under_review", label: `Under review (${counts.under_review || 0})` },
    { key: "quoted", label: `Quoted (${counts.quoted || 0})` },
    { key: "approved", label: `Approved (${counts.approved || 0})` },
    { key: "cancelled", label: `Cancelled (${counts.cancelled || 0})` },
  ];

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-5xl mx-auto px-6 pt-14 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Corporate Services</div>
        <h1 className="font-display text-4xl md:text-5xl tracking-wide mt-2">MY REQUESTS</h1>
        <p className="text-sm text-neutral-400 mt-2 max-w-2xl">Track your Corporate Services RFQs — from submission through admin review, quotation, negotiation and approval.</p>

        <div className="flex gap-1 flex-wrap mt-6" data-testid="rfq-status-tabs">
          {TABS.map((t) => (
            <button key={t.key} data-testid={`rfq-filter-${t.key}`} onClick={() => setFilter(t.key)}
              className={`text-[10px] font-mono uppercase px-2.5 py-1 rounded-sm border ${filter === t.key ? "bg-[#06B6D4] border-[#06B6D4] text-black" : "border-white/10 text-neutral-400 hover:bg-white/5"}`}>
              {t.label}
            </button>
          ))}
        </div>

        {loading && <div className="text-neutral-500 text-sm mt-8">Loading…</div>}

        {!loading && rfqs.length === 0 && (
          <div data-testid="rfq-empty" className="mt-8 border border-dashed border-white/10 rounded-sm p-10 text-center">
            <FileText className="w-8 h-8 mx-auto text-neutral-500" />
            <div className="text-neutral-400 mt-2 text-sm">No RFQs yet.</div>
            <Link to="/corporate-services" data-testid="rfq-empty-cta" className="mt-4 inline-flex items-center gap-1 text-[#06B6D4] hover:underline text-xs font-mono uppercase">
              Browse packages <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        )}

        <div className="mt-6 space-y-3">
          {rfqs.map((r) => (
            <Link to={`/rfqs/${r.id}`} key={r.id} data-testid={`rfq-row-${r.id}`} className="block border border-white/10 rounded-sm bg-[#141414] p-4 hover:border-white/25 transition-colors">
              <div className="flex justify-between items-start gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-2">
                    <Package className="w-4 h-4 text-[#06B6D4]" />
                    <span className="font-semibold text-white">{r.event?.event_name || "Untitled event"}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500 mt-1">
                    {r.package_name}
                    {r.event?.preferred_date && ` · ${r.event.preferred_date}`}
                    {r.event?.city && ` · ${r.event.city}`}
                    {" · "}{(r.selected_service_ids || []).length} services · {(r.selected_addons || []).length} add-ons
                  </div>
                </div>
                <div className="text-[10px] font-mono text-neutral-500 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Created {(r.created_at || "").slice(0, 10)}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
      <Footer />
    </div>
  );
}

export function RFQDetail() {
  const { rfqId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [rfq, setRfq] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => { api.get(`/rfqs/${rfqId}`).then((r) => setRfq(r.data)).catch(() => nav("/rfqs")); };
  useEffect(load, [rfqId]); // eslint-disable-line

  const cancel = async () => {
    if (!window.confirm("Cancel this RFQ?")) return;
    setBusy(true);
    try {
      await api.post(`/rfqs/${rfqId}/cancel`);
      toast.success("RFQ cancelled");
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Failed"); } finally { setBusy(false); }
  };

  if (!rfq) return null;
  const canCancel = ["submitted", "under_review", "quoted", "negotiation"].includes(rfq.status);

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-4xl mx-auto px-6 pt-14 pb-24">
        <Link to="/rfqs" className="text-xs text-neutral-400 hover:text-white">← All RFQs</Link>

        <div className="mt-4 flex items-center gap-3 flex-wrap">
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Corporate Services · RFQ</div>
          <StatusBadge status={rfq.status} />
        </div>
        <h1 className="font-display text-3xl md:text-4xl tracking-wide mt-2">{rfq.event?.event_name || "Untitled event"}</h1>
        <p className="text-sm text-neutral-400 mt-1">{rfq.package_name}</p>

        <section className="mt-8 grid md:grid-cols-2 gap-8">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#84CC16]">/ Included services ({(rfq.selected_service_ids || []).length})</div>
            <ul className="mt-2 space-y-1">
              {(rfq.included_services_snapshot || []).filter((s) => (rfq.selected_service_ids || []).includes(s.id)).map((s) => (
                <li key={s.id} className="text-sm text-neutral-200 flex items-center gap-2">
                  <CheckCircle2 className="w-3 h-3 text-[#84CC16]" /> {s.name}
                  <span className="text-[10px] font-mono uppercase text-neutral-500">{s.unit_type}</span>
                </li>
              ))}
              {(rfq.selected_service_ids || []).length === 0 && <li className="text-neutral-500 text-xs">No services in this RFQ</li>}
            </ul>
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#EC4899]">/ Add-ons ({(rfq.selected_addons || []).length})</div>
            <ul className="mt-2 space-y-1">
              {(rfq.selected_addons || []).map((a) => (
                <li key={a.addon_id} className="text-sm text-neutral-200 flex items-center gap-2">
                  <span className="text-[#EC4899]">•</span> {a.name} <span className="text-neutral-400">× {a.quantity}</span>
                  <span className="text-[10px] font-mono uppercase text-neutral-500">{a.unit_type}</span>
                </li>
              ))}
              {(rfq.selected_addons || []).length === 0 && <li className="text-neutral-500 text-xs">No add-ons requested</li>}
            </ul>
          </div>
        </section>

        <section className="mt-8">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#FACC15]">/ Event details</div>
          <div className="mt-2 grid md:grid-cols-2 gap-3 border border-white/10 bg-[#141414] rounded-sm p-4">
            <Detail label="Preferred date" value={rfq.event?.preferred_date} />
            <Detail label="Preferred time" value={rfq.event?.preferred_time || "—"} />
            <Detail label="Sport" value={rfq.event?.sport || "—"} />
            <Detail label="Players / spectators" value={`${rfq.event?.num_players || "—"} / ${rfq.event?.num_spectators || "—"}`} />
            <Detail label="City" value={rfq.event?.city || "—"} />
            <Detail label="State" value={rfq.event?.state || "—"} />
            <Detail label="Venue" value={rfq.event?.venue || "—"} className="md:col-span-2" />
            <Detail label="Expected budget" value={rfq.expected_budget || "—"} className="md:col-span-2" />
            {rfq.special_instructions && <Detail label="Special instructions" value={rfq.special_instructions} className="md:col-span-2" />}
          </div>
        </section>

        <section className="mt-8 border border-[#06B6D4]/30 bg-[#06B6D4]/5 rounded-sm p-5">
          <div className="flex items-start gap-3">
            <MessageSquare className="w-5 h-5 text-[#06B6D4] mt-0.5 shrink-0" />
            <div className="flex-1">
              <div className="font-semibold">Awaiting quotation</div>
              <p className="text-xs text-neutral-400 mt-1">The admin team is reviewing your RFQ. You&rsquo;ll receive an email once a quotation is ready. Negotiation + approval actions arrive in the next update.</p>
            </div>
            {canCancel && (
              <Button data-testid="rfq-cancel" disabled={busy} onClick={cancel} variant="outline" className="border-[#FF3B30]/40 bg-transparent text-[#FF3B30] hover:bg-[#FF3B30]/10 h-9 rounded-sm text-xs">
                <XCircle className="w-3.5 h-3.5 mr-1" /> Cancel RFQ
              </Button>
            )}
          </div>
        </section>
      </div>
      <Footer />
    </div>
  );
}

function StatusBadge({ status }) {
  const tone = {
    draft:         "bg-white/5 text-neutral-400 border-white/10",
    submitted:     "bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/40",
    under_review:  "bg-[#FACC15]/15 text-[#FACC15] border-[#FACC15]/40",
    quoted:        "bg-[#84CC16]/15 text-[#84CC16] border-[#84CC16]/40",
    negotiation:   "bg-[#EC4899]/15 text-[#EC4899] border-[#EC4899]/40",
    approved:      "bg-[#84CC16]/15 text-[#84CC16] border-[#84CC16]/40",
    rejected:      "bg-[#FF3B30]/15 text-[#FF3B30] border-[#FF3B30]/40",
    completed:     "bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/40",
    cancelled:     "bg-white/5 text-neutral-500 border-white/10",
  }[status] || "bg-white/5 text-neutral-400 border-white/10";
  return <Badge className={`border ${tone} text-[10px] font-mono uppercase tracking-widest`}>{(status || "").replace("_", " ")}</Badge>;
}

function Detail({ label, value, className = "" }) {
  return (
    <div className={className}>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="text-neutral-200 text-sm mt-0.5">{value}</div>
    </div>
  );
}
