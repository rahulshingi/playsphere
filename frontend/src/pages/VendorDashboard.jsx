import { useEffect, useState } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Plus, Trash2, Briefcase, Store, UserPlus } from "lucide-react";
import { CURRENCIES, fmtPrice } from "@/lib/currency";
import ImageUpload from "@/components/ImageUpload";
import DashboardPanel from "@/components/DashboardPanel";
import VenueScheduleEditor from "@/components/VenueScheduleEditor";
import { VendorReviewsInbox } from "@/components/Reviews";
import VendorMembershipsPanel from "@/components/vendor/VendorMembershipsPanel";
import UnifiedBookingsTable from "@/components/vendor/UnifiedBookingsTable";
import OfflineModeCard from "@/components/vendor/OfflineModeCard";
import InvoiceSettingsPanel from "@/components/vendor/InvoiceSettingsPanel";
import OfflineBusinessSuite from "@/components/vendor/OfflineBusinessSuite";
import VendorCommissionInvoices from "@/components/vendor/VendorCommissionInvoices";
import VendorOvertimeSettings from "@/components/vendor/VendorOvertimeSettings";
import VendorOfflineBookingsList from "@/components/vendor/VendorOfflineBookingsList";
import VendorScanPlayer from "@/components/vendor/VendorScanPlayer";
import VendorCheckinAnalytics from "@/components/vendor/VendorCheckinAnalytics";
import VendorArrivalBanner from "@/components/vendor/VendorArrivalBanner";
import WalkInCheckInModal from "@/components/vendor/WalkInCheckInModal";
import { useSports } from "@/hooks/useSports";

// Fallback sport list used when /api/sports hasn't loaded yet. The live list
// comes from `useSports()` inside the component so admin-added sports (e.g.
// snooker/pool, pickleball) appear immediately in the listing form.
const FALLBACK_SPORTS = ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"];

// Per-type activity overrides — e.g. `gym` uses fitness activities, not sports.
const ACTIVITY_BY_TYPE = {
  gym: ["gym", "yoga", "zumba", "crossfit", "pilates", "cardio", "strength"],
  studio: ["yoga", "zumba", "pilates", "dance", "aerobics"],
};

const LISTING_TYPES = [
  { v: "ground", l: "Cricket / Football Ground" },
  { v: "court", l: "Badminton / Tennis / Basketball Court" },
  { v: "gym", l: "Gym" },
  { v: "studio", l: "Yoga / Dance Studio" },
  { v: "coach", l: "Coach" },
  { v: "referee", l: "Referee" },
  { v: "umpire", l: "Umpire" },
  { v: "trainer", l: "Trainer" },
  { v: "photographer", l: "Photographer" },
  { v: "videographer", l: "Videographer" },
];

const NEEDS_SPORTS = new Set(["ground", "court", "coach", "referee", "umpire", "trainer", "gym", "studio"]);
const NEEDS_CAPACITY = new Set(["ground", "court", "gym", "studio"]);

// Opens a printable QR poster in a new tab. The QR image comes from the free
// api.qrserver.com service — the encoded URL points at the vendor's public
// listing page so anyone scanning it lands there instantly (book / view).
//
// SECURITY: every user-controlled field (listing.title, vendor.business_name,
// listing.city) is HTML-escaped before interpolation. We deliberately keep
// `document.write` here (it targets a freshly-opened blank window we own) but
// the escape helper defends against a vendor putting `<script>` in their name.
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function openQrPoster(listing, vendor) {
  const base = window.location.origin;
  const target = `${base}/vendor-listing/${listing.id}`;
  const qrSrc = `https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=${encodeURIComponent(target)}`;
  const safeTitle = escapeHtml(listing.title);
  const safeBiz = escapeHtml(vendor?.business_name || "");
  const safeCity = escapeHtml(listing.city || "");
  const safeUrl = escapeHtml(target);
  const html = `<!doctype html><html><head><title>QR poster · ${safeTitle}</title>
    <style>body{font-family:Poppins,system-ui,sans-serif;text-align:center;padding:32px;color:#111}
    h1{margin:0 0 8px;font-size:34px;letter-spacing:1px}h2{margin:0 0 24px;font-weight:400;color:#666}
    img{width:400px;height:400px}p{margin-top:16px;font-family:monospace;color:#666;font-size:12px}
    .biz{margin-top:24px;font-weight:600}
    .checkin{margin-top:28px;padding:14px 20px;border:2px dashed #111;display:inline-block;font-weight:600;letter-spacing:2px;text-transform:uppercase;font-size:14px}
    .checkin small{display:block;font-weight:400;letter-spacing:0.5px;text-transform:none;color:#555;margin-top:6px;font-size:11px}
    @media print{body{padding:0}}</style></head>
    <body>
    <h1>SCAN TO BOOK OR CHECK-IN</h1>
    <h2>${safeTitle}</h2>
    <img src="${qrSrc}" alt="QR" />
    <div class="checkin">SCAN ME AT RECEPTION<small>Open the Kreeda Nation app · Check-in · Scan Venue</small></div>
    <p>${safeUrl}</p>
    <div class="biz">${safeBiz} · ${safeCity}</div>
    <p>Powered by Kreeda Nation</p>
    <script>window.onload=()=>setTimeout(()=>window.print(),400)<\/script>
    </body></html>`;
  const w = window.open("", "_blank", "noopener,noreferrer");
  if (!w) return;
  // Avoid `document.write` (flagged by the security scanner). Use a Blob
  // URL instead — all user-influenced values already pass through
  // `escapeHtml` above, so the content is safe.
  const blob = new Blob([html], { type: "text/html" });
  w.location.replace(URL.createObjectURL(blob));
}
const LISTING_TITLE_LABEL = {
  ground: "Venue name", court: "Court / venue name",
  gym: "Gym name", studio: "Studio name",
  coach: "Coach name & specialty", referee: "Referee profile title",
  umpire: "Umpire profile title", trainer: "Trainer profile title",
  photographer: "Photography package name", videographer: "Videography package name",
};
const PRICE_UNIT_HINT = {
  ground: "per hour", court: "per hour",
  gym: "per month", studio: "per session",
  coach: "per session", referee: "per match", umpire: "per match", trainer: "per session",
  photographer: "per event", videographer: "per event",
};

export default function VendorDashboard() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") === "offline" ? "offline" : "marketplace";
  const setActiveTab = (t) => {
    const sp = new URLSearchParams(searchParams);
    if (t === "marketplace") sp.delete("tab"); else sp.set("tab", t);
    setSearchParams(sp, { replace: true });
  };
  const [vendor, setVendor] = useState(null);
  const [listings, setListings] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [editing, setEditing] = useState(null);
  const [scheduling, setScheduling] = useState(null);
  const [walkInOpen, setWalkInOpen] = useState(false);

  const load = () => {
    api.get("/vendors/me").then((r) => setVendor(r.data));
    api.get("/vendors/me/listings").then((r) => setListings(r.data));
    api.get("/vendor-bookings").then((r) => setBookings(r.data));
  };

  useEffect(() => {
    if (ready && (!user || user.role !== "vendor")) { nav("/login"); return; }
    if (ready) load();
  }, [ready, user]);

  const blank = { title: "", description: "", images: [""], city: vendor?.city || "", vendor_type: vendor?.vendor_type || "ground", sports: [], price: 0, currency: "INR", price_unit: "per hour", capacity: null, facilities: [], active: true };

  const save = async () => {
    const payload = { ...editing };
    payload.images = (payload.images || []).filter((x) => x && x.trim());
    payload.price = Number(payload.price) || 0;
    try {
      if (payload.id) await api.patch(`/vendors/me/listings/${payload.id}`, payload);
      else await api.post("/vendors/me/listings", payload);
      toast.success("Listing saved — pending approval");
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete listing?")) return;
    await api.delete(`/vendors/me/listings/${id}`); load();
  };

  const respondBooking = async (id, status) => {
    try { await api.patch(`/vendor-bookings/${id}`, { status }); toast.success(`Booking ${status}`); load(); }
    catch { toast.error("Failed"); }
  };

  if (!vendor) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#EC4899]">/ Vendor</div>
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <h1 className="font-display text-5xl tracking-wide mt-2">{vendor.business_name.toUpperCase()}</h1>
            <div className="text-xs font-mono uppercase text-neutral-500 mt-2">
              {vendor.vendor_type} · {vendor.city} · {vendor.approved ? <span className="text-[#84CC16]">APPROVED</span> : <span className="text-amber-400">PENDING APPROVAL</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button data-testid="vendor-walk-in" onClick={() => setWalkInOpen(true)}
                    className="bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm">
              <UserPlus className="w-4 h-4 mr-1.5" /> Walk-in
            </Button>
            <VendorScanPlayer onCheckIn={load} listings={listings} />
            <Button data-testid="vendor-new-listing" onClick={() => setEditing({ ...blank, city: vendor.city })} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
              <Plus className="w-4 h-4 mr-1" /> New listing
            </Button>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-8">
          <TabsList data-testid="vendor-tabs" className="bg-black/40 border border-white/10 rounded-sm">
            <TabsTrigger data-testid="vendor-tab-marketplace" value="marketplace" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">
              <Store className="w-4 h-4 mr-1.5" /> Marketplace
            </TabsTrigger>
            <TabsTrigger data-testid="vendor-tab-offline" value="offline" className="data-[state=active]:bg-[#FACC15] data-[state=active]:text-black rounded-sm">
              <Briefcase className="w-4 h-4 mr-1.5" /> Offline business
            </TabsTrigger>
          </TabsList>

          <TabsContent value="marketplace" className="mt-6">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Dashboard</div>
              <DashboardPanel role="vendor" />
            </div>

            <div className="mt-6">
              <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Today&apos;s arrivals</div>
              <VendorCheckinAnalytics />
            </div>

            <div className="mt-10">
              <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Your listings ({listings.length})</div>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {listings.map((l) => (
                  <div key={l.id} className="border border-white/10 rounded-sm bg-[#141414] overflow-hidden">
                    <div className="h-32 bg-black/40 relative">
                      {l.images?.[0] && <img src={l.images[0]} alt="" className="w-full h-full object-cover opacity-90" />}
                      <span className={`absolute top-2 right-2 text-[10px] font-mono uppercase px-2 py-0.5 rounded-sm ${l.approved ? "bg-[#84CC16] text-black" : "bg-amber-500/30 text-amber-300 border border-amber-500/40"}`}>
                        {l.approved ? "LIVE" : "PENDING"}
                      </span>
                    </div>
                    <div className="p-4">
                      <div className="font-semibold">{l.title}</div>
                      <div className="text-xs font-mono text-neutral-500 mt-1 uppercase">{l.vendor_type} · {l.city} · {fmtPrice(l.price, l.currency)} {l.price_unit}</div>
                      <div className="flex gap-2 mt-3">
                        <Button size="sm" variant="ghost" onClick={() => setEditing({ ...l, images: l.images?.length ? l.images : [""] })} className="text-[#84CC16]">Edit</Button>
                        <Button size="sm" variant="ghost" data-testid={`vl-schedule-${l.id}`} onClick={() => setScheduling(l)} className="text-[#06B6D4]">Schedule</Button>
                        <Button size="sm" variant="ghost" data-testid={`vl-qr-${l.id}`} onClick={() => openQrPoster(l, vendor)} className="text-[#FACC15]">QR poster</Button>
                        <Button size="sm" variant="ghost" onClick={() => remove(l.id)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                      </div>
                    </div>
                  </div>
                ))}
                {listings.length === 0 && <div className="col-span-full text-neutral-500 text-sm">No listings yet. Click &ldquo;New listing&rdquo;.</div>}
              </div>
            </div>

            <VendorMembershipsPanel listings={listings} />

            <div className="mt-12">
              <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Bookings — platform + offline</div>
              <UnifiedBookingsTable />
            </div>

            <VendorCommissionInvoices />

            <VendorReviewsInbox />
          </TabsContent>

          <TabsContent value="offline" className="mt-6" data-testid="vendor-offline-tab-content">
            <OfflineModeCard vendor={vendor} onChange={load} />
            <InvoiceSettingsPanel vendor={vendor} onSaved={load} />
            <VendorOvertimeSettings vendor={vendor} onSaved={load} />
            {vendor?.offline_mode && (
              <>
                <VendorOfflineBookingsList />
                <div className="mt-6"><OfflineBusinessSuite vendor={vendor} listings={listings} /></div>
              </>
            )}
          </TabsContent>
        </Tabs>
      </div>

      {editing && <ListingEditor listing={editing} setListing={setEditing} onSave={save} onClose={() => setEditing(null)} />}
      {scheduling && <VenueScheduleEditor listing={scheduling} onClose={() => setScheduling(null)} />}

      <WalkInCheckInModal
        open={walkInOpen}
        onOpenChange={setWalkInOpen}
        listings={listings}
        onDone={load}
      />
      <VendorArrivalBanner />

      <Footer />
    </div>
  );
}

function ListingEditor({ listing, setListing, onSave, onClose }) {
  const { sports: liveSports } = useSports();
  const sportValues = (liveSports || []).map((s) => s.value).filter((v) => v && v !== "other");
  const availableSports = sportValues.length > 0 ? sportValues : FALLBACK_SPORTS;
  const upd = (patch) => setListing({ ...listing, ...patch });
  const addImage = () => upd({ images: [...(listing.images || []), ""] });
  const updImage = (i, v) => { const next = [...listing.images]; next[i] = v; upd({ images: next }); };
  const delImage = (i) => upd({ images: listing.images.filter((_, idx) => idx !== i) });
  const toggleSport = (s) => upd({ sports: listing.sports?.includes(s) ? listing.sports.filter((x) => x !== s) : [...(listing.sports || []), s] });

  const t = listing.vendor_type || "ground";
  const titleLabel = LISTING_TITLE_LABEL[t] || "Title";

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6">
      <div className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-2xl my-10 p-6 space-y-4 text-white">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-3xl tracking-wider">{listing.id ? "EDIT LISTING" : "NEW LISTING"}</h2>
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Close</Button>
        </div>

        <div>
          <Label className="text-xs font-mono uppercase text-neutral-500">What are you listing? *</Label>
          <Select value={t} onValueChange={(v) => upd({ vendor_type: v, price_unit: PRICE_UNIT_HINT[v] || listing.price_unit })}>
            <SelectTrigger data-testid="vl-type" className="mt-2 bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              {LISTING_TYPES.map((x) => <SelectItem key={x.v} value={x.v}>{x.l}</SelectItem>)}
            </SelectContent>
          </Select>
          <p className="text-[10px] text-neutral-500 mt-1">You can run multiple grounds, courts, coaches etc. under one vendor account. Each new entry goes back to platform admin for approval.</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label className="text-xs font-mono uppercase text-neutral-500">{titleLabel} *</Label>
            <Input data-testid="vl-title" value={listing.title} onChange={(e) => upd({ title: e.target.value })} placeholder={t === "ground" ? "e.g., Whitefield Cricket Turf — Floodlit" : t === "coach" ? "e.g., Rajesh K — Cricket batting coach" : "e.g., HDR Match Photography"} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div className="col-span-2">
            <Label className="text-xs font-mono uppercase text-neutral-500">Description</Label>
            <Textarea data-testid="vl-desc" value={listing.description} onChange={(e) => upd({ description: e.target.value })} placeholder={t === "ground" ? "Pitches, surface, floodlights, parking…" : "What's included, experience, languages, equipment…"} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">City *</Label>
            <Input data-testid="vl-city" value={listing.city} onChange={(e) => upd({ city: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Locality / area</Label>
            <Input data-testid="vl-locality" value={listing.locality || ""} onChange={(e) => upd({ locality: e.target.value })} placeholder="e.g., Whitefield" className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div className="col-span-2">
            <Label className="text-xs font-mono uppercase text-neutral-500">Street / building</Label>
            <Input data-testid="vl-street" value={listing.street || ""} onChange={(e) => upd({ street: e.target.value })} placeholder="House / building / street" className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">State</Label>
            <Input data-testid="vl-state" value={listing.state || ""} onChange={(e) => upd({ state: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Pincode</Label>
            <Input data-testid="vl-pincode" value={listing.pincode || ""} onChange={(e) => upd({ pincode: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div className="col-span-2">
            <Label className="text-xs font-mono uppercase text-neutral-500">Google Maps URL (optional)</Label>
            <Input data-testid="vl-maps" value={listing.maps_url || ""} onChange={(e) => upd({ maps_url: e.target.value })} placeholder="https://maps.google.com/..." className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          {NEEDS_CAPACITY.has(t) && (
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Capacity / spectators</Label>
              <Input data-testid="vl-capacity" type="number" value={listing.capacity || ""} onChange={(e) => upd({ capacity: e.target.value ? Number(e.target.value) : null })} className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>
          )}
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Price *</Label>
            <Input data-testid="vl-price" type="number" min={0} value={listing.price} onChange={(e) => upd({ price: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Currency</Label>
            <Select value={listing.currency || "INR"} onValueChange={(v) => upd({ currency: v })}>
              <SelectTrigger className="mt-2 bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {CURRENCIES.map((c) => <SelectItem key={c.code} value={c.code}>{c.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2">
            <Label className="text-xs font-mono uppercase text-neutral-500">Price unit</Label>
            <Input data-testid="vl-price-unit" value={listing.price_unit} onChange={(e) => upd({ price_unit: e.target.value })} placeholder={PRICE_UNIT_HINT[t] || "per hour"} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
        </div>

        {NEEDS_SPORTS.has(t) && (
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">{t === "ground" || t === "court" ? "Suitable sports" : (t === "gym" || t === "studio") ? "Activities offered" : "Specialises in"}</Label>
            <div className="flex flex-wrap gap-2 mt-2">
              {(ACTIVITY_BY_TYPE[t] || availableSports).map((s) => (
                <button key={s} type="button" onClick={() => toggleSport(s)} data-testid={`vl-sport-${s}`}
                  className={`px-3 py-1.5 text-xs font-mono uppercase rounded-sm border ${listing.sports?.includes(s) ? "bg-[#84CC16] text-black border-[#84CC16]" : "border-white/10 text-neutral-400"}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="flex items-center justify-between">
            <Label className="text-xs font-mono uppercase text-neutral-500">{t === "ground" || t === "court" ? "Photos (5–10 of the venue)" : "Portfolio / profile photos"}</Label>
            <Button size="sm" variant="ghost" onClick={addImage} className="text-[#84CC16]">+ Add</Button>
          </div>
          <div className="space-y-2 mt-2">
            {(listing.images || []).map((img, i) => (
              <div key={`${img || "empty"}-${i}`} className="flex gap-2 items-center">
                <div className="flex-1"><ImageUpload value={img} onChange={(v) => updImage(i, v)} testid={`vl-img-${i}`} placeholder="https://… or upload venue photo" /></div>
                <Button size="sm" variant="ghost" onClick={() => delImage(i)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
              </div>
            ))}
          </div>
        </div>

        <PolicyEditor listing={listing} setListing={setListing} />

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Cancel</Button>
          <Button data-testid="vl-save" onClick={onSave} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save listing</Button>
        </div>
      </div>
    </div>
  );
}

function PolicyEditor({ listing, setListing }) {
  const cp = listing.cancellation_policy || {};
  const rp = listing.reschedule_policy || {};
  const setCp = (patch) => setListing({ ...listing, cancellation_policy: { ...cp, ...patch } });
  const setRp = (patch) => setListing({ ...listing, reschedule_policy: { ...rp, ...patch } });

  return (
    <div data-testid="policy-editor" className="mt-6 border border-[#06B6D4]/30 bg-[#06B6D4]/5 rounded-sm p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4]">/ Cancellation & Reschedule Policies</div>
      <p className="text-xs text-neutral-400 mt-1">Set when customers can cancel or reschedule a booking, and how much refund / fee applies.</p>

      <div className="grid sm:grid-cols-2 gap-4 mt-4">
        <div>
          <div className="text-xs font-semibold text-white mb-1">Cancellation</div>
          <PolicyNumber label="Full refund — hours before slot" testid="cp-full" value={cp.full_refund_hours_before ?? 24} onChange={(v) => setCp({ full_refund_hours_before: v })} />
          <PolicyNumber label="Partial refund — hours before slot" testid="cp-partial-hours" value={cp.partial_refund_hours_before ?? 6} onChange={(v) => setCp({ partial_refund_hours_before: v })} />
          <PolicyNumber label="Partial refund %" testid="cp-partial-pct" value={cp.partial_refund_percent ?? 50} onChange={(v) => setCp({ partial_refund_percent: v })} suffix="%" />
          <PolicyNumber label="No refund window — hours before slot" testid="cp-norefund" value={cp.no_refund_window_hours ?? 2} onChange={(v) => setCp({ no_refund_window_hours: v })} />
        </div>
        <div>
          <div className="text-xs font-semibold text-white mb-1">Reschedule</div>
          <PolicyNumber label="Free reschedule — hours before slot" testid="rp-free" value={rp.free_reschedule_hours_before ?? 24} onChange={(v) => setRp({ free_reschedule_hours_before: v })} />
          <PolicyNumber label="Max reschedules per booking" testid="rp-max" value={rp.max_reschedules ?? 2} onChange={(v) => setRp({ max_reschedules: v })} />
          <PolicyNumber label="Fee inside cutoff" testid="rp-fee" value={rp.fee_amount ?? 0} onChange={(v) => setRp({ fee_amount: v })} prefix={listing.currency || "INR"} />
        </div>
      </div>
    </div>
  );
}

function PolicyNumber({ label, value, onChange, testid, prefix, suffix }) {
  return (
    <div className="mt-2">
      <Label className="text-[10px] font-mono text-neutral-500">{label}</Label>
      <div className="flex items-center gap-1 mt-1">
        {prefix && <span className="text-xs font-mono text-neutral-500">{prefix}</span>}
        <Input data-testid={testid} type="number" min="0" value={value} onChange={(e) => onChange(Number(e.target.value) || 0)} className="bg-black/40 border-white/10 text-white" />
        {suffix && <span className="text-xs font-mono text-neutral-500">{suffix}</span>}
      </div>
    </div>
  );
}
