import { useEffect, useState } from "react";
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
import { Plus, Trash2 } from "lucide-react";
import { CURRENCIES, fmtPrice } from "@/lib/currency";

const SPORTS = ["cricket", "football", "badminton", "tennis", "basketball", "volleyball", "tabletennis"];

export default function VendorDashboard() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [vendor, setVendor] = useState(null);
  const [listings, setListings] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [editing, setEditing] = useState(null);

  const load = () => {
    api.get("/vendors/me").then((r) => setVendor(r.data));
    api.get("/vendors/me/listings").then((r) => setListings(r.data));
    api.get("/vendor-bookings").then((r) => setBookings(r.data));
  };

  useEffect(() => {
    if (ready && (!user || user.role !== "vendor")) { nav("/login"); return; }
    if (ready) load();
  }, [ready, user]);

  const blank = { title: "", description: "", images: [""], city: vendor?.city || "", sports: [], price: 0, currency: "INR", price_unit: "per hour", capacity: null, facilities: [], active: true };

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
          <Button data-testid="vendor-new-listing" onClick={() => setEditing({ ...blank, city: vendor.city })} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
            <Plus className="w-4 h-4 mr-1" /> New listing
          </Button>
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
                  <div className="text-xs font-mono text-neutral-500 mt-1 uppercase">{l.city} · {fmtPrice(l.price, l.currency)} {l.price_unit}</div>
                  <div className="flex gap-2 mt-3">
                    <Button size="sm" variant="ghost" onClick={() => setEditing({ ...l, images: l.images?.length ? l.images : [""] })} className="text-[#84CC16]">Edit</Button>
                    <Button size="sm" variant="ghost" onClick={() => remove(l.id)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                  </div>
                </div>
              </div>
            ))}
            {listings.length === 0 && <div className="col-span-full text-neutral-500 text-sm">No listings yet. Click "New listing".</div>}
          </div>
        </div>

        <div className="mt-12">
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Booking requests ({bookings.length})</div>
          <div className="border border-white/10 rounded-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
                <tr><th className="text-left px-4 py-3">Listing</th><th className="text-left px-3 py-3">Company</th><th className="text-left px-3 py-3">Date / Time</th><th className="text-right px-3 py-3">Price</th><th className="text-left px-3 py-3">Status</th><th></th></tr>
              </thead>
              <tbody>
                {bookings.map((b) => (
                  <tr key={b.id} className="border-t border-white/5">
                    <td className="px-4 py-3">{b.listing_title}</td>
                    <td className="px-3 py-3 font-mono text-neutral-300">{b.company_name}</td>
                    <td className="px-3 py-3 font-mono text-neutral-300">{b.requested_date} · {b.start_time}–{b.end_time}</td>
                    <td className="px-3 py-3 text-right font-mono">{fmtPrice(b.price, b.currency)}</td>
                    <td className="px-3 py-3"><span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${b.status === "confirmed" ? "text-[#84CC16] border-[#84CC16]/40" : b.status === "declined" ? "text-[#FF3B30] border-[#FF3B30]/40" : b.status === "cancelled" ? "text-neutral-500 border-white/10" : "text-amber-400 border-amber-500/40"}`}>{b.status}</span></td>
                    <td className="px-3 py-3 text-right">
                      {b.status === "pending" && (
                        <div className="flex gap-1 justify-end">
                          <Button size="sm" data-testid={`vb-confirm-${b.id}`} onClick={() => respondBooking(b.id, "confirmed")} className="bg-[#84CC16] hover:bg-[#65A30D] text-black h-7 rounded-sm">Confirm</Button>
                          <Button size="sm" variant="outline" data-testid={`vb-decline-${b.id}`} onClick={() => respondBooking(b.id, "declined")} className="border-white/10 bg-transparent text-[#FF3B30] h-7 rounded-sm">Decline</Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {bookings.length === 0 && <tr><td colSpan={6} className="text-center py-10 text-neutral-500">No booking requests yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {editing && <ListingEditor listing={editing} setListing={setEditing} onSave={save} onClose={() => setEditing(null)} />}

      <Footer />
    </div>
  );
}

function ListingEditor({ listing, setListing, onSave, onClose }) {
  const upd = (patch) => setListing({ ...listing, ...patch });
  const addImage = () => upd({ images: [...(listing.images || []), ""] });
  const updImage = (i, v) => { const next = [...listing.images]; next[i] = v; upd({ images: next }); };
  const delImage = (i) => upd({ images: listing.images.filter((_, idx) => idx !== i) });
  const toggleSport = (s) => upd({ sports: listing.sports?.includes(s) ? listing.sports.filter((x) => x !== s) : [...(listing.sports || []), s] });

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6">
      <div className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-2xl my-10 p-6 space-y-4 text-white">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-3xl tracking-wider">{listing.id ? "EDIT LISTING" : "NEW LISTING"}</h2>
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Close</Button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label className="text-xs font-mono uppercase text-neutral-500">Title *</Label>
            <Input data-testid="vl-title" value={listing.title} onChange={(e) => upd({ title: e.target.value })} placeholder="e.g., Whitefield Cricket Turf — Floodlit" className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div className="col-span-2">
            <Label className="text-xs font-mono uppercase text-neutral-500">Description</Label>
            <Textarea data-testid="vl-desc" value={listing.description} onChange={(e) => upd({ description: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">City *</Label>
            <Input data-testid="vl-city" value={listing.city} onChange={(e) => upd({ city: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Capacity</Label>
            <Input type="number" value={listing.capacity || ""} onChange={(e) => upd({ capacity: e.target.value ? Number(e.target.value) : null })} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
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
            <Input data-testid="vl-price-unit" value={listing.price_unit} onChange={(e) => upd({ price_unit: e.target.value })} placeholder="per hour" className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
        </div>

        <div>
          <Label className="text-xs font-mono uppercase text-neutral-500">Suitable sports</Label>
          <div className="flex flex-wrap gap-2 mt-2">
            {SPORTS.map((s) => (
              <button key={s} type="button" onClick={() => toggleSport(s)} data-testid={`vl-sport-${s}`}
                className={`px-3 py-1.5 text-xs font-mono uppercase rounded-sm border ${listing.sports?.includes(s) ? "bg-[#84CC16] text-black border-[#84CC16]" : "border-white/10 text-neutral-400"}`}>
                {s}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <Label className="text-xs font-mono uppercase text-neutral-500">Images (5–10 recommended)</Label>
            <Button size="sm" variant="ghost" onClick={addImage} className="text-[#84CC16]">+ Add</Button>
          </div>
          <div className="space-y-2 mt-2">
            {(listing.images || []).map((img, i) => (
              <div key={i} className="flex gap-2 items-center">
                <Input data-testid={`vl-img-${i}`} value={img} onChange={(e) => updImage(i, e.target.value)} placeholder="https://…" className="bg-black/40 border-white/10 text-white" />
                {img && <img src={img} alt="" className="w-10 h-10 object-cover rounded-sm" />}
                <Button size="sm" variant="ghost" onClick={() => delImage(i)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Cancel</Button>
          <Button data-testid="vl-save" onClick={onSave} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save listing</Button>
        </div>
      </div>
    </div>
  );
}
