import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CheckCircle2, Sparkles, ArrowRight, Package } from "lucide-react";

/**
 * PackageCustomiser (Phase 2) — HR/Organiser builds their event package from a
 * base template. They toggle included services and pick add-on quantities,
 * fill an event details form, and submit an RFQ. No pricing anywhere.
 */
export default function PackageCustomiser() {
  const { packageId } = useParams();
  const nav = useNavigate();
  const { user, isCompanyAdmin, ready } = useAuth();

  const [pkg, setPkg] = useState(null);
  const [category, setCategory] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [addons, setAddons] = useState({}); // {addon_id: quantity}
  const [event, setEvent] = useState({
    event_name: "", preferred_date: "", preferred_time: "",
    sport: "", venue: "", venue_required: true,
    num_players: "", num_spectators: "", city: "", state: "",
    special_instructions: "", budget: "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ready) return;
    if (!isCompanyAdmin) { nav("/corporate-services"); return; }
    (async () => {
      try {
        const cats = (await api.get("/corporate-services/categories")).data || [];
        const allPkgs = (await Promise.all(
          cats.map((c) => api.get(`/corporate-services/packages?category_id=${c.id}`).then((r) => r.data || []))
        )).flat();
        const p = allPkgs.find((x) => x.id === packageId);
        if (!p) { toast.error("Package not found"); nav("/corporate-services"); return; }
        setPkg(p);
        setCategory(cats.find((c) => c.id === p.category_id) || null);
        setSelected(new Set(p.included_service_ids || []));  // all pre-selected
      } catch { nav("/corporate-services"); }
    })();
  }, [ready, isCompanyAdmin, packageId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!pkg) return null;

  const toggleSvc = (id) => {
    const s = new Set(selected);
    s.has(id) ? s.delete(id) : s.add(id);
    setSelected(s);
  };
  const setAddonQty = (id, qty) => {
    const next = { ...addons };
    if (!qty || qty <= 0) delete next[id];
    else next[id] = Number(qty);
    setAddons(next);
  };

  const submit = async () => {
    if (!event.event_name || !event.preferred_date) return toast.error("Event name and preferred date are required");
    setBusy(true);
    try {
      const payload = {
        package_id: packageId,
        selected_service_ids: [...selected],
        selected_addons: Object.entries(addons).map(([addon_id, quantity]) => ({ addon_id, quantity })),
        event,
        expected_budget: event.budget,
        special_instructions: event.special_instructions,
        submit: true,
      };
      const { data } = await api.post("/rfqs", payload);
      toast.success("RFQ submitted — our team will send a quotation within 24 hours");
      nav(`/rfqs/${data.id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Submission failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-4xl mx-auto px-6 pt-14 pb-24">
        <Link to="/corporate-services" className="text-xs text-neutral-400 hover:text-white">← Back to catalogue</Link>
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4] mt-4">/ {category?.name || "Package"}</div>
        <div className="flex items-start justify-between gap-4 mt-1">
          <div>
            <h1 className="font-display text-3xl md:text-4xl tracking-wide">{pkg.name} <span className="text-lg text-[#06B6D4] font-mono uppercase ml-1">{pkg.tier}</span></h1>
            {pkg.description && <p className="text-sm text-neutral-400 mt-2 max-w-2xl">{pkg.description}</p>}
          </div>
          <Package className="w-6 h-6 text-neutral-500" />
        </div>

        {/* Included services */}
        <section className="mt-8">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#84CC16]">/ Included services · tap to toggle</div>
          <div className="mt-2 grid md:grid-cols-2 gap-2">
            {(pkg.included_services || []).map((s) => (
              <button
                key={s.id}
                data-testid={`cust-svc-${s.id}`}
                onClick={() => toggleSvc(s.id)}
                className={`text-left border rounded-sm p-3 text-sm ${selected.has(s.id) ? "border-[#84CC16] bg-[#84CC16]/10" : "border-white/10 bg-[#141414] text-neutral-500"}`}
              >
                <div className="flex justify-between items-start">
                  <div className={selected.has(s.id) ? "text-white" : "text-neutral-500"}>{s.name}</div>
                  {selected.has(s.id) ? <CheckCircle2 className="w-3.5 h-3.5 text-[#84CC16]" /> : <span className="text-[10px] text-neutral-600">removed</span>}
                </div>
                <div className="text-[10px] font-mono uppercase text-neutral-500 mt-1">{s.unit_type}</div>
              </button>
            ))}
            {(pkg.included_services || []).length === 0 && <div className="text-neutral-500 text-xs col-span-full">No default services on this package.</div>}
          </div>
        </section>

        {/* Optional add-ons */}
        {(pkg.optional_addons || []).length > 0 && (
          <section className="mt-8">
            <div className="text-[10px] font-mono uppercase tracking-widest text-[#EC4899]">/ Optional add-ons · set quantity</div>
            <div className="mt-2 grid md:grid-cols-2 gap-2">
              {pkg.optional_addons.map((a) => {
                const qty = addons[a.id] || 0;
                return (
                  <div key={a.id} data-testid={`cust-add-${a.id}`} className={`border rounded-sm p-3 flex items-center justify-between gap-3 ${qty > 0 ? "border-[#EC4899] bg-[#EC4899]/5" : "border-white/10 bg-[#141414]"}`}>
                    <div>
                      <div className="text-white text-sm">{a.name}</div>
                      <div className="text-[10px] font-mono uppercase text-neutral-500 mt-0.5">{a.unit_type}{!a.custom_quantity_enabled ? " · fixed qty" : ""}</div>
                    </div>
                    <Input
                      type="number"
                      min="0"
                      value={qty || ""}
                      placeholder="0"
                      disabled={!a.custom_quantity_enabled && qty > 0}
                      onChange={(e) => setAddonQty(a.id, e.target.value)}
                      className="w-20 bg-black/40 border-white/10 text-white text-center"
                    />
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Event details */}
        <section className="mt-8">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#FACC15]">/ Event details</div>
          <div className="mt-2 grid md:grid-cols-2 gap-3">
            <Field label="Event name *" value={event.event_name} onChange={(v) => setEvent({ ...event, event_name: v })} testid="cust-event-name" />
            <Field label="Sport" value={event.sport} onChange={(v) => setEvent({ ...event, sport: v })} />
            <Field label="Preferred date *" type="date" value={event.preferred_date} onChange={(v) => setEvent({ ...event, preferred_date: v })} testid="cust-event-date" />
            <Field label="Preferred time" type="time" value={event.preferred_time} onChange={(v) => setEvent({ ...event, preferred_time: v })} />
            <Field label="Number of players" type="number" value={event.num_players} onChange={(v) => setEvent({ ...event, num_players: v })} />
            <Field label="Number of spectators" type="number" value={event.num_spectators} onChange={(v) => setEvent({ ...event, num_spectators: v })} />
            <Field label="City" value={event.city} onChange={(v) => setEvent({ ...event, city: v })} />
            <Field label="State" value={event.state} onChange={(v) => setEvent({ ...event, state: v })} />
            <Field label="Venue (if you have one)" value={event.venue} onChange={(v) => setEvent({ ...event, venue: v })} className="md:col-span-2" />
            <Field label="Expected budget (optional)" value={event.budget} onChange={(v) => setEvent({ ...event, budget: v })} className="md:col-span-2" placeholder="e.g. ₹1.5L — leave blank if unsure" />
            <div className="md:col-span-2">
              <Label className="text-[10px] font-mono uppercase text-neutral-500">Special instructions</Label>
              <Textarea data-testid="cust-event-notes" value={event.special_instructions} onChange={(e) => setEvent({ ...event, special_instructions: e.target.value })} rows={3} className="mt-1 bg-black/40 border-white/10 text-white" />
            </div>
          </div>
        </section>

        {/* Submit */}
        <div className="mt-10 border border-[#06B6D4]/30 bg-[#06B6D4]/5 rounded-sm p-5">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-[#06B6D4] shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold">Ready to submit?</div>
              <p className="text-xs text-neutral-400 mt-1">Our team reviews every RFQ within 24 hours and returns a tailored quotation. You&rsquo;ll be able to accept, negotiate, or counter-offer inside this app.</p>
            </div>
            <Button data-testid="cust-submit" onClick={submit} disabled={busy} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-11 px-6 rounded-sm">
              {busy ? "Submitting…" : "Submit RFQ"} <ArrowRight className="ml-1 w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

function Field({ label, value, onChange, type = "text", testid, className = "", placeholder = "" }) {
  return (
    <div className={className}>
      <Label className="text-[10px] font-mono uppercase text-neutral-500">{label}</Label>
      <Input data-testid={testid} type={type} value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="mt-1 bg-black/40 border-white/10 text-white" />
    </div>
  );
}
