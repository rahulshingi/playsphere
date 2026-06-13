import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Check } from "lucide-react";
import { fmtPrice } from "@/lib/currency";

export default function ServiceDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { isCompanyAdmin, isPlatformAdmin, user } = useAuth();
  const [service, setService] = useState(null);
  const [events, setEvents] = useState([]);
  const [variantId, setVariantId] = useState(null);
  const [config, setConfig] = useState({});
  const [customText, setCustomText] = useState("");
  const [notes, setNotes] = useState("");
  const [eventId, setEventId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get(`/services/${id}`).then((r) => {
      setService(r.data);
      const defaults = {};
      (r.data.config_fields || []).forEach((f) => {
        if (f.default !== undefined && f.default !== null) defaults[f.key] = f.default;
      });
      setConfig(defaults);
      if (r.data.variants?.length) setVariantId(r.data.variants[0].id);
    });
    if (isCompanyAdmin) {
      api.get(`/events?company_id=${user.company_id}`).then((r) => setEvents(r.data));
    }
  }, [id, isCompanyAdmin]);

  const selectedVariant = useMemo(
    () => service?.variants?.find((v) => v.id === variantId) || null,
    [service, variantId]
  );

  const total = useMemo(() => {
    if (!service) return 0;
    const extra = selectedVariant ? selectedVariant.extra_price : 0;
    return (service.base_price + extra) * (Number(quantity) || 1);
  }, [service, selectedVariant, quantity]);

  if (!service) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  const submit = async (e) => {
    e.preventDefault();
    if (!isCompanyAdmin) {
      toast.error("Please sign in as a company admin to book");
      nav("/signup-company");
      return;
    }
    setBusy(true);
    try {
      await api.post("/bookings", {
        service_id: service.id,
        event_id: eventId || null,
        quantity: Number(quantity) || 1,
        variant_id: variantId || null,
        config,
        custom_text: customText,
        notes,
      });
      toast.success("Booking request submitted!");
      nav("/bookings");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <Link to="/services" className="text-xs font-mono text-neutral-400 hover:text-white">← All services</Link>

        <div className="grid lg:grid-cols-5 gap-10 mt-6">
          {/* LEFT: gallery + variants */}
          <div className="lg:col-span-3 space-y-6">
            <div className="rounded-sm border border-white/10 overflow-hidden bg-[#141414] aspect-video relative">
              <img src={(selectedVariant?.image_url) || service.images?.[0]} alt="" className="w-full h-full object-cover" />
            </div>

            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16]">/ {service.category}</div>
              <h1 data-testid="service-name" className="font-display text-5xl tracking-wide mt-2">{service.name.toUpperCase()}</h1>
              <p className="text-neutral-300 mt-4 leading-relaxed">{service.description}</p>
            </div>

            {service.variants?.length > 0 && (
              <div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Choose a design</div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {service.variants.map((v) => {
                    const active = variantId === v.id;
                    return (
                      <button
                        key={v.id}
                        type="button"
                        data-testid={`variant-${v.id}`}
                        onClick={() => setVariantId(v.id)}
                        className={`group text-left border rounded-sm overflow-hidden bg-[#141414] transition ${active ? "border-[#84CC16] ring-2 ring-[#84CC16]/40" : "border-white/10 hover:border-white/30"}`}
                      >
                        <div className="relative aspect-square">
                          <img src={v.image_url} className="w-full h-full object-cover" alt="" />
                          {active && <span className="absolute top-2 right-2 bg-[#84CC16] text-black rounded-full w-6 h-6 grid place-items-center"><Check className="w-3.5 h-3.5" /></span>}
                        </div>
                        <div className="p-3">
                          <div className="text-sm font-medium">{v.name}</div>
                          <div className="font-mono text-xs text-neutral-400 mt-0.5">
                            {v.extra_price === 0 ? "Included" : v.extra_price > 0 ? `+ ${fmtPrice(v.extra_price, service.currency)}` : `- ${fmtPrice(Math.abs(v.extra_price), service.currency)}`}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* RIGHT: booking form */}
          <form onSubmit={submit} className="lg:col-span-2 border border-white/10 rounded-sm bg-[#141414] p-6 h-fit lg:sticky lg:top-24 space-y-4">
            <div className="flex items-end justify-between">
              <div>
                <div className="font-display text-4xl tracking-wider">{fmtPrice(total, service.currency)}</div>
                <div className="text-[10px] font-mono uppercase text-neutral-500">{service.price_unit}{quantity > 1 ? ` × ${quantity}` : ""}</div>
              </div>
              <div className="font-mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm bg-[#84CC16]/10 text-[#84CC16] border border-[#84CC16]/30">Request Quote</div>
            </div>

            {!isCompanyAdmin && !isPlatformAdmin && (
              <div className="text-xs text-amber-400 border border-amber-500/30 bg-amber-500/5 rounded-sm p-3">
                Sign in as a company admin to book this service.{" "}
                <Link to="/signup-company" className="underline">Onboard your company →</Link>
              </div>
            )}

            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Quantity</Label>
              <Input data-testid="booking-quantity" type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>

            {isCompanyAdmin && events.length > 0 && (
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">For tournament (optional)</Label>
                <Select value={eventId} onValueChange={setEventId}>
                  <SelectTrigger data-testid="booking-event-select" className="mt-2 bg-black/40 border-white/10 text-white"><SelectValue placeholder="Not linked" /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    {events.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Dynamic fields */}
            {(service.config_fields || []).map((f) => (
              <div key={f.key}>
                <Label className="text-xs font-mono uppercase text-neutral-500">{f.label}{f.required && " *"}</Label>
                {f.type === "select" ? (
                  <Select value={String(config[f.key] ?? "")} onValueChange={(v) => setConfig({ ...config, [f.key]: v })}>
                    <SelectTrigger data-testid={`field-${f.key}`} className="mt-2 bg-black/40 border-white/10 text-white"><SelectValue placeholder="Select…" /></SelectTrigger>
                    <SelectContent className="bg-[#141414] text-white border-white/10">
                      {(f.options || []).map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                    </SelectContent>
                  </Select>
                ) : f.type === "textarea" ? (
                  <Textarea data-testid={`field-${f.key}`} value={config[f.key] || ""} onChange={(e) => setConfig({ ...config, [f.key]: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
                ) : (
                  <Input data-testid={`field-${f.key}`} type={f.type === "number" ? "number" : "text"} min={f.min} max={f.max} required={f.required} value={config[f.key] ?? ""} onChange={(e) => setConfig({ ...config, [f.key]: f.type === "number" ? Number(e.target.value) : e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
                )}
                {f.help_text && <p className="text-[10px] text-neutral-500 mt-1">{f.help_text}</p>}
              </div>
            ))}

            {service.allow_custom_text && (
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">{service.custom_text_label || "Custom text"}</Label>
                <Textarea data-testid="booking-custom-text" rows={2} value={customText} onChange={(e) => setCustomText(e.target.value)} placeholder="e.g., Best Batsman — Spring Cup 2026" className="mt-2 bg-black/40 border-white/10 text-white" />
              </div>
            )}

            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Internal notes</Label>
              <Textarea data-testid="booking-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>

            <Button data-testid="booking-submit" disabled={busy} type="submit" className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-11 rounded-sm">
              {busy ? "Submitting..." : "Submit booking request"}
            </Button>
          </form>
        </div>
      </div>
      <Footer />
    </div>
  );
}
