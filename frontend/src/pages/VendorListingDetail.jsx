import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { fmtPrice } from "@/lib/currency";
import { MapPin, BadgeCheck, Sparkles } from "lucide-react";
import VerifiedBadge from "@/components/VerifiedBadge";
import { BookingModal } from "./VendorMarket";

// Sets / clears an OG or Twitter meta tag by attribute (property or name).
function upsertMeta(attr, key, value) {
  if (!value) return null;
  let el = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", value);
  return el;
}

// Public listing detail page. Purpose: give every verified listing a
// shareable URL with rich OG previews (WhatsApp / Instagram / X / LinkedIn),
// driven by the QR poster and vendor social sharing.
export default function VendorListingDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user, ready } = useAuth();
  const [listing, setListing] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({ requested_date: "", start_time: "18:00", hours: 2, notes: "", apply_membership_id: "" });

  useEffect(() => {
    api.get(`/vendor-listings/${id}`)
      .then((r) => setListing(r.data))
      .catch(() => setNotFound(true));
  }, [id]);

  // Inject SEO + OpenGraph + Twitter Card meta tags for social share previews.
  useEffect(() => {
    if (!listing) return;
    const desc = (listing.description || `Book ${listing.title} on Kreeda Nation — ${listing.city}. ${listing.sports?.join(", ") || ""}`).slice(0, 200);
    const image = listing.images?.[0] || `${window.location.origin}/logo512.png`;
    const url = window.location.href;
    const title = `${listing.title} · ${listing.city} · Kreeda Nation`;

    const originalTitle = document.title;
    document.title = title;

    const created = [
      upsertMeta("name", "description", desc),
      upsertMeta("property", "og:title", title),
      upsertMeta("property", "og:description", desc),
      upsertMeta("property", "og:image", image),
      upsertMeta("property", "og:url", url),
      upsertMeta("property", "og:type", "website"),
      upsertMeta("name", "twitter:card", "summary_large_image"),
      upsertMeta("name", "twitter:title", title),
      upsertMeta("name", "twitter:description", desc),
      upsertMeta("name", "twitter:image", image),
    ].filter(Boolean);

    return () => {
      document.title = originalTitle;
      // Remove only the tags we created so we don't stomp any global defaults.
      created.forEach((el) => el.remove());
    };
  }, [listing]);

  const openBooking = () => {
    if (ready && !user) {
      nav(`/login?next=/vendor-listing/${id}`);
      return;
    }
    setSelected(listing);
  };

  const submitBooking = async () => {
    if (!form.hours || form.hours < 1) return toast.error("Hours must be at least 1");
    if (!form.requested_date) return toast.error("Pick a date");
    try {
      await api.post("/vendor-bookings", {
        listing_id: listing.id,
        requested_date: form.requested_date,
        start_time: form.start_time,
        hours: Number(form.hours),
        sport: listing.sports?.[0] || "",
        notes: form.notes,
        apply_membership_id: form.apply_membership_id || null,
      });
      toast.success(form.apply_membership_id
        ? "Booked using your membership — vendor will confirm shortly"
        : "Booking request sent — admin will confirm with the vendor");
      setSelected(null);
      nav("/bookings");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  if (notFound) {
    return (
      <div className="bg-[#0a0a0a] min-h-screen text-white">
        <Nav />
        <div className="max-w-3xl mx-auto px-6 pt-24 pb-40 text-center">
          <div className="font-display text-4xl tracking-wider">Listing not found</div>
          <p className="text-neutral-400 mt-3">This venue is no longer available or has been unlisted.</p>
          <Button data-testid="vld-browse-more" onClick={() => nav("/hire")} className="mt-6 bg-[#84CC16] text-black hover:bg-[#65A30D]">Browse other venues</Button>
        </div>
        <Footer />
      </div>
    );
  }

  if (!listing) {
    return (
      <div className="bg-[#0a0a0a] min-h-screen text-white">
        <Nav />
        <div className="max-w-3xl mx-auto px-6 pt-24 text-center text-neutral-400">Loading…</div>
      </div>
    );
  }

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-5xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ VENUE</div>
        <div className="grid lg:grid-cols-5 gap-8 mt-3">
          {/* Gallery + info */}
          <div className="lg:col-span-3 space-y-4">
            <div className="aspect-video bg-black/40 border border-white/10 rounded-sm overflow-hidden">
              {listing.images?.[0] && <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />}
            </div>
            {listing.images?.length > 1 && (
              <div className="grid grid-cols-4 gap-2">
                {listing.images.slice(1, 5).map((src) => (
                  <div key={src} className="aspect-square bg-black/40 border border-white/10 rounded-sm overflow-hidden">
                    <img src={src} alt="" className="w-full h-full object-cover" />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Sticky booking card */}
          <div className="lg:col-span-2 border border-white/10 rounded-sm bg-[#141414] p-6 h-fit lg:sticky lg:top-24 space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 data-testid="vld-title" className="font-display text-3xl tracking-wider">{listing.title}</h1>
              {listing.verified && (
                <span data-testid="vld-verified" className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-sm bg-[#84CC16] text-black font-semibold">
                  <BadgeCheck className="w-3 h-3" /> Verified
                </span>
              )}
              <VerifiedBadge listing={listing} />
            </div>
            <div className="text-xs font-mono text-neutral-400 uppercase flex items-center gap-1">
              <MapPin className="w-3 h-3" /> {listing.city}
            </div>
            <p className="text-sm text-neutral-300 whitespace-pre-wrap">{listing.description}</p>
            <div className="flex items-baseline gap-2">
              <div className="font-mono text-3xl text-[#84CC16]">{fmtPrice(listing.price, listing.currency)}</div>
              <div className="text-[10px] font-mono uppercase text-neutral-500">{listing.price_unit}</div>
            </div>
            {listing.sports?.length > 0 && (
              <div className="text-[10px] font-mono uppercase text-neutral-400">Sports: {listing.sports.join(" · ")}</div>
            )}
            {listing.cheapest_membership && (
              <div data-testid="vld-memb" className="flex items-center gap-2 rounded-sm border border-[#EC4899]/40 bg-[#EC4899]/10 p-3">
                <Sparkles className="w-4 h-4 text-[#EC4899] shrink-0" />
                <div className="text-xs text-neutral-200">
                  Membership from <span className="text-[#EC4899] font-semibold">{fmtPrice(listing.cheapest_membership.price, listing.cheapest_membership.currency)}</span>
                </div>
              </div>
            )}
            <Button data-testid="vld-book-cta" onClick={openBooking} className="w-full bg-[#84CC16] text-black hover:bg-[#65A30D] font-semibold h-11 rounded-sm">
              {ready && !user ? "Sign in to book" : "Book this venue"}
            </Button>
            <div className="text-[10px] font-mono uppercase text-neutral-500 text-center">Powered by Kreeda Nation</div>
          </div>
        </div>
      </div>

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
