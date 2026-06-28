import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { fmtPrice } from "@/lib/currency";
import { SPORTS } from "@/lib/sports";
import { MapPin, BadgeCheck, ChevronRight, Calendar, Clock, Sparkles } from "lucide-react";
import VerifiedBadge from "@/components/VerifiedBadge";
import { todayLocalISO, minTimeForDate, validateFutureDateTime } from "@/lib/dateConstraints";

const VENDOR_TYPE_LABEL = {
  ground: "Grounds", court: "Courts", coach: "Coaches", referee: "Referees",
  umpire: "Umpires", trainer: "Trainers", photographer: "Photographers", videographer: "Videographers",
};

// Categories that are bookable by sport/location (vs people whose flow is different)
const VENUE_TYPES = ["ground", "court"];

export default function VendorMarket() {
  const { ready, isCompanyAdmin } = useAuth();
  const nav = useNavigate();

  // Wizard state
  const [vendorType, setVendorType] = useState("ground");
  const [sport, setSport] = useState("");
  const [city, setCity] = useState("");
  const [cities, setCities] = useState([]);
  const [listings, setListings] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({ requested_date: "", start_time: "18:00", hours: 2, notes: "" });

  useEffect(() => {
    if (ready && !isCompanyAdmin) nav("/login");
  }, [ready, isCompanyAdmin, nav]);

  // When sport is picked, fetch cities
  useEffect(() => {
    if (!sport) { setCities([]); setCity(""); setListings([]); return; }
    api.get(`/vendor-listings/cities?sport=${encodeURIComponent(sport)}&vendor_type=${vendorType}`)
      .then((r) => setCities(r.data))
      .catch(() => {});
    setCity("");
    setListings([]);
  }, [sport, vendorType]);

  // When city is picked, fetch listings
  useEffect(() => {
    if (!(sport && city)) { setListings([]); return; }
    api.get(`/vendor-listings?vendor_type=${vendorType}&sport=${encodeURIComponent(sport)}&city=${encodeURIComponent(city)}`)
      .then((r) => setListings(r.data))
      .catch(() => {});
  }, [sport, city, vendorType]);

  const step = useMemo(() => {
    if (!sport) return 1;
    if (!city) return 2;
    if (!selected) return 3;
    return 4;
  }, [sport, city, selected]);

  const submitBooking = async () => {
    const err = validateFutureDateTime(form.requested_date, form.start_time);
    if (err) return toast.error(err);
    if (!form.hours || form.hours < 1) return toast.error("Hours must be at least 1");
    try {
      await api.post("/vendor-bookings", {
        listing_id: selected.id,
        requested_date: form.requested_date,
        start_time: form.start_time,
        hours: Number(form.hours),
        sport,
        notes: form.notes,
      });
      toast.success("Booking request sent — admin will confirm with the vendor");
      setSelected(null);
      nav("/bookings");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  // Surface chips: render the sports list for cricket/football/etc.
  const isVenueFlow = VENUE_TYPES.includes(vendorType);

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Hire</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">BOOK A GROUND OR HIRE TALENT</h1>
        <p className="text-neutral-400 mt-2 text-sm max-w-2xl">Pick a sport and city to see verified Kreeda Nation venues with live rates. Submit a request — admin confirms with the vendor and you&apos;ll see the status update on your bookings page.</p>

        {/* Vendor type selector — top bar */}
        <div className="mt-8 flex flex-wrap gap-2">
          {Object.entries(VENDOR_TYPE_LABEL).map(([v, l]) => (
            <button
              key={v}
              data-testid={`vm-vtype-${v}`}
              onClick={() => { setVendorType(v); setSport(""); setCity(""); setSelected(null); }}
              className={`px-4 py-2 rounded-sm text-xs font-mono uppercase tracking-widest border transition ${
                vendorType === v
                  ? "bg-[#84CC16] text-black border-[#84CC16]"
                  : "bg-[#141414] text-neutral-400 border-white/10 hover:text-white"
              }`}
            >{l}</button>
          ))}
        </div>

        {/* Stepper */}
        <div className="mt-10 flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-neutral-500">
          <StepPill n="1" label="Sport" active={step === 1} done={step > 1} />
          <ChevronRight className="w-3 h-3" />
          <StepPill n="2" label="Location" active={step === 2} done={step > 2} />
          <ChevronRight className="w-3 h-3" />
          <StepPill n="3" label="Pick venue" active={step === 3} done={step > 3} />
          <ChevronRight className="w-3 h-3" />
          <StepPill n="4" label="Date & rate" active={step === 4} done={false} />
        </div>

        {/* Step 1: Sport */}
        {isVenueFlow ? (
          <SectionTitle n="1" title="Pick a sport / surface" />
        ) : (
          <SectionTitle n="1" title="Pick a sport" />
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {SPORTS.map((s) => (
            <button
              key={s.value}
              data-testid={`vm-sport-${s.value}`}
              onClick={() => setSport(s.value)}
              className={`px-4 py-2 rounded-sm text-sm border transition ${
                sport === s.value
                  ? "bg-[#06B6D4] text-black border-[#06B6D4] font-semibold"
                  : "bg-[#141414] text-neutral-300 border-white/10 hover:text-white"
              }`}
            >{s.label}</button>
          ))}
        </div>

        {/* Step 2: City */}
        {sport && (
          <>
            <SectionTitle n="2" title="Pick a location" />
            <div className="mt-3 flex flex-wrap gap-2">
              {cities.length === 0 && <span className="text-neutral-500 text-sm">No verified vendors yet for this sport.</span>}
              {cities.map((c) => (
                <button
                  key={c}
                  data-testid={`vm-city-${c}`}
                  onClick={() => setCity(c)}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-sm text-sm border transition ${
                    city === c
                      ? "bg-[#EC4899] text-black border-[#EC4899] font-semibold"
                      : "bg-[#141414] text-neutral-300 border-white/10 hover:text-white"
                  }`}
                ><MapPin className="w-3.5 h-3.5" /> {c}</button>
              ))}
            </div>
          </>
        )}

        {/* Step 3: Listings */}
        {sport && city && (
          <>
            <SectionTitle n="3" title={`Available ${VENDOR_TYPE_LABEL[vendorType].toLowerCase()} in ${city}`} />
            <div className="mt-3 grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {listings.length === 0 && <div className="col-span-full text-center text-neutral-500 py-10">No verified listings here yet.</div>}
              {listings.map((l) => (
                <button
                  key={l.id}
                  data-testid={`vm-listing-${l.id}`}
                  onClick={() => setSelected(l)}
                  className="text-left border border-white/10 rounded-sm bg-[#141414] overflow-hidden hover-lift"
                >
                  <div className="h-40 bg-black/40 relative">
                    {l.images?.[0] && <img src={l.images[0]} alt="" className="w-full h-full object-cover" />}
                    <span className="absolute top-2 left-2 text-[10px] font-mono uppercase px-2 py-0.5 rounded-sm bg-black/60 text-white">{l.city}</span>
                    {l.verified && (
                      <span data-testid={`vm-verified-${l.id}`} className="absolute top-2 right-2 inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-sm bg-[#84CC16] text-black font-semibold shadow-[0_2px_8px_rgba(132,204,22,0.35)]">
                        <BadgeCheck className="w-3 h-3" /> Verified
                      </span>
                    )}
                  </div>
                  <div className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-semibold">{l.title}</div>
                      {(l.rating_count ?? 0) > 0 && <VerifiedBadge listing={l} />}
                    </div>
                    <div className="text-xs text-neutral-400 mt-1 line-clamp-2">{l.description}</div>
                    {l.cheapest_membership && (
                      <div data-testid={`vm-memb-${l.id}`}
                        className="mt-2 inline-flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest px-2 py-1 rounded-sm bg-[#EC4899]/15 text-[#EC4899] border border-[#EC4899]/40">
                        <Sparkles className="w-3 h-3" /> Membership from {fmtPrice(l.cheapest_membership.price, l.cheapest_membership.currency)}
                      </div>
                    )}
                    <div className="flex items-end justify-between mt-3">
                      <div>
                        <div className="font-mono text-xl text-[#84CC16]">{fmtPrice(l.price, l.currency)}</div>
                        <div className="text-[10px] font-mono uppercase text-neutral-500">{l.price_unit}</div>
                      </div>
                      {l.sports?.length > 0 && <div className="text-[10px] font-mono uppercase text-neutral-400">{l.sports.slice(0, 3).join(" · ")}</div>}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Step 4: Booking modal */}
      {selected && (
        <BookingModal
          listing={selected}
          form={form}
          setForm={setForm}
          onSubmit={submitBooking}
          onClose={() => setSelected(null)}
        />
      )}

      <Footer />
    </div>
  );
}

function StepPill({ n, label, active, done }) {
  return (
    <span data-testid={`vm-step-${n}`} className={`px-2 py-1 rounded-sm border ${
      active ? "bg-white/10 text-white border-white/20" : done ? "bg-[#84CC16]/15 text-[#84CC16] border-[#84CC16]/30" : "border-white/10 text-neutral-600"
    }`}>{n}. {label}</span>
  );
}

function SectionTitle({ n, title }) {
  return (
    <div className="mt-10 flex items-end gap-3">
      <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Step {n}</span>
      <span className="font-display text-2xl tracking-wider">{title.toUpperCase()}</span>
    </div>
  );
}

function BookingModal({ listing, form, setForm, onSubmit, onClose }) {
  const total = useMemo(() => Number(listing.price) * Number(form.hours || 0), [listing.price, form.hours]);
  const [availability, setAvailability] = useState(null);

  useEffect(() => {
    if (!form.requested_date) { setAvailability(null); return; }
    let cancelled = false;
    api.get(`/vendor-listings/${listing.id}/availability?date=${form.requested_date}`)
      .then((r) => { if (!cancelled) setAvailability(r.data); })
      .catch(() => { if (!cancelled) setAvailability(null); });
    return () => { cancelled = true; };
  }, [form.requested_date, listing.id]);

  const pickSlot = (s) => {
    if (s.status !== "available") return;
    setForm({ ...form, start_time: s.time });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6" onClick={onClose}>
      <div className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-2xl my-10 text-white" onClick={(e) => e.stopPropagation()}>
        <div className="aspect-video bg-black/40 relative">
          {listing.images?.[0] && <img src={listing.images[0]} alt="" className="w-full h-full object-cover" />}
        </div>
        <div className="p-6 space-y-4">
          <div>
            <div className="font-display text-3xl tracking-wider flex items-center gap-3 flex-wrap">
              {listing.title}
              <VerifiedBadge listing={listing} size="lg" />
            </div>
            <div className="text-xs font-mono text-neutral-500 uppercase mt-1">{listing.city} · {listing.sports?.join(" · ") || ""}</div>
            <p className="text-sm text-neutral-300 mt-2">{listing.description}</p>
            {listing.cheapest_membership && (
              <div data-testid="vm-detail-memb"
                className="mt-3 border border-[#EC4899]/40 bg-gradient-to-r from-[#EC4899]/10 to-transparent rounded-sm p-3 flex items-center gap-3">
                <Sparkles className="w-5 h-5 text-[#EC4899] shrink-0" />
                <div className="text-sm">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[#EC4899]">/ Recommended membership</div>
                  <div className="text-neutral-200">
                    Save vs hourly rates — memberships from
                    <span className="text-[#EC4899] font-semibold ml-1">{fmtPrice(listing.cheapest_membership.price, listing.cheapest_membership.currency)}</span>.
                    Ask the venue desk to sign up; online purchase coming soon.
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500 flex items-center gap-1"><Calendar className="w-3 h-3" />Date *</Label>
              <Input data-testid="vm-book-date" type="date" min={todayLocalISO()} value={form.requested_date} onChange={(e) => setForm({ ...form, requested_date: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500 flex items-center gap-1"><Clock className="w-3 h-3" />Start</Label>
              <Input data-testid="vm-book-start" type="time" min={minTimeForDate(form.requested_date)} value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Hours *</Label>
              <Select value={String(form.hours)} onValueChange={(v) => setForm({ ...form, hours: Number(v) })}>
                <SelectTrigger data-testid="vm-book-hours" className="mt-2 bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  {[1, 2, 3, 4, 5, 6, 8, 10, 12].map((h) => <SelectItem key={h} value={String(h)}>{h} hour{h > 1 ? "s" : ""}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* SLOT GRID */}
          {availability && (
            <div data-testid="vm-slot-grid">
              <Label className="text-xs font-mono uppercase text-neutral-500">Available slots {availability.is_weekend && <span className="ml-2 text-[#F59E0B]">· weekend pricing</span>}</Label>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {availability.slots.map((s) => (
                  <button
                    key={s.time}
                    data-testid={`vm-slot-${s.time.replace(":", "")}`}
                    onClick={() => pickSlot(s)}
                    disabled={s.status !== "available"}
                    title={`${fmtPrice(s.price, availability.currency)} / hr · ${s.status}`}
                    className={`text-[11px] font-mono px-2 py-1 rounded-sm border transition ${
                      form.start_time === s.time
                        ? "bg-[#06B6D4] text-black border-[#06B6D4] font-semibold"
                        : s.status === "available"
                        ? "bg-[#84CC16]/10 text-[#84CC16] border-[#84CC16]/30 hover:bg-[#84CC16]/20"
                        : s.status === "booked"
                        ? "bg-[#FF3B30]/10 text-[#FF3B30]/60 border-[#FF3B30]/30 cursor-not-allowed"
                        : "bg-neutral-900 text-neutral-600 border-white/10 cursor-not-allowed"
                    }`}>
                    {s.time}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Notes</Label>
            <Textarea data-testid="vm-book-notes" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Tournament name, slot preference, etc." className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div className="border-t border-white/10 pt-4 flex items-end justify-between">
            <div>
              <div className="text-[10px] font-mono uppercase text-neutral-500">Rate · {listing.price_unit}</div>
              <div className="font-mono text-base text-neutral-300">{fmtPrice(listing.price, listing.currency)}</div>
              <div className="text-[10px] font-mono uppercase text-neutral-500 mt-1">Estimated total ({form.hours || 0}h)</div>
              <div data-testid="vm-book-total" className="font-display text-3xl text-[#84CC16]">{fmtPrice(total, listing.currency)}</div>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={onClose} className="text-neutral-400">Cancel</Button>
              <Button data-testid="vm-book-submit" onClick={onSubmit} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Send request</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
