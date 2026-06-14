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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { fmtPrice } from "@/lib/currency";
import { MapPin, Search, BadgeCheck } from "lucide-react";

const VENDOR_TYPE_LABEL = {
  ground: "Grounds", court: "Courts", coach: "Coaches", referee: "Referees",
  umpire: "Umpires", trainer: "Trainers", photographer: "Photographers", videographer: "Videographers",
};

export default function VendorMarket() {
  const { user, ready, isCompanyAdmin } = useAuth();
  const nav = useNavigate();
  const [tab, setTab] = useState("ground");
  const [city, setCity] = useState("");
  const [listings, setListings] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({ requested_date: "", start_time: "09:00", end_time: "12:00", notes: "" });

  useEffect(() => {
    if (ready && !isCompanyAdmin) { nav("/login"); return; }
    if (ready) load();
  }, [ready, tab, city]);

  const load = () => {
    let url = `/vendor-listings?vendor_type=${tab}`;
    if (city) url += `&city=${encodeURIComponent(city)}`;
    api.get(url).then((r) => setListings(r.data));
  };

  const submitBooking = async () => {
    if (!form.requested_date) { toast.error("Pick a date"); return; }
    try {
      await api.post("/vendor-bookings", { listing_id: selected.id, ...form });
      toast.success("Booking request sent");
      setSelected(null);
      nav("/bookings");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Hire</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">SERVICE PROVIDERS</h1>
        <p className="text-neutral-400 mt-2 text-sm max-w-xl">Hire venues and on-ground talent from PlaySphere's verified partners. Provider details stay private — only their inventory & pricing shown.</p>

        <div className="mt-8 flex gap-3 items-center flex-wrap">
          <div className="relative flex-1 max-w-sm">
            <MapPin className="absolute left-3 top-2.5 w-4 h-4 text-neutral-500" />
            <Input data-testid="vm-city" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Filter by city" className="pl-9 bg-[#141414] border-white/10 text-white" />
          </div>
          <Button data-testid="vm-search" onClick={load} variant="outline" className="border-white/10 bg-transparent text-white rounded-sm"><Search className="w-4 h-4 mr-1" /> Search</Button>
        </div>

        <Tabs value={tab} onValueChange={setTab} className="mt-6">
          <TabsList className="bg-[#141414] border border-white/10 rounded-sm overflow-x-auto flex-wrap">
            {Object.entries(VENDOR_TYPE_LABEL).map(([v, l]) => (
              <TabsTrigger key={v} value={v} data-testid={`vm-tab-${v}`} className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">{l}</TabsTrigger>
            ))}
          </TabsList>

          {Object.keys(VENDOR_TYPE_LABEL).map((v) => (
            <TabsContent key={v} value={v} className="mt-6">
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {listings.map((l) => (
                  <div key={l.id} data-testid={`vm-listing-${l.id}`} onClick={() => setSelected(l)}
                    className="border border-white/10 rounded-sm bg-[#141414] overflow-hidden hover-lift cursor-pointer">
                    <div className="h-40 bg-black/40 relative">
                      {l.images?.[0] && <img src={l.images[0]} alt="" className="w-full h-full object-cover" />}
                      <span className="absolute top-2 left-2 text-[10px] font-mono uppercase px-2 py-0.5 rounded-sm bg-black/60 text-white">{l.city}</span>
                      <span data-testid={`vm-verified-${l.id}`} className="absolute top-2 right-2 inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-sm bg-[#84CC16] text-black font-semibold shadow-[0_2px_8px_rgba(132,204,22,0.35)]">
                        <BadgeCheck className="w-3 h-3" /> Verified
                      </span>
                    </div>
                    <div className="p-4">
                      <div className="font-semibold">{l.title}</div>
                      <div className="text-xs text-neutral-400 mt-1 line-clamp-2">{l.description}</div>
                      <div className="flex items-end justify-between mt-3">
                        <div>
                          <div className="font-mono text-xl text-[#84CC16]">{fmtPrice(l.price, l.currency)}</div>
                          <div className="text-[10px] font-mono uppercase text-neutral-500">{l.price_unit}</div>
                        </div>
                        {l.sports?.length > 0 && <div className="text-[10px] font-mono uppercase text-neutral-400">{l.sports.slice(0, 2).join(" · ")}</div>}
                      </div>
                    </div>
                  </div>
                ))}
                {listings.length === 0 && <div className="col-span-full text-center text-neutral-500 py-16">No approved providers here yet.</div>}
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6">
          <div className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-2xl my-10 text-white">
            <div className="aspect-video bg-black/40 relative">
              {selected.images?.[0] && <img src={selected.images[0]} alt="" className="w-full h-full object-cover" />}
            </div>
            {selected.images?.length > 1 && (
              <div className="grid grid-cols-5 gap-1 p-1">
                {selected.images.slice(1, 6).map((img, i) => <img key={i} src={img} alt="" className="aspect-square object-cover rounded-sm" />)}
              </div>
            )}
            <div className="p-6 space-y-4">
              <div>
                <div className="font-display text-3xl tracking-wider">{selected.title}</div>
                <div className="text-xs font-mono text-neutral-500 uppercase mt-1">{selected.city} · {selected.sports?.join(" · ") || ""}</div>
                <p className="text-sm text-neutral-300 mt-2">{selected.description}</p>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-xs font-mono uppercase text-neutral-500">Date *</Label>
                  <Input data-testid="vm-book-date" type="date" value={form.requested_date} onChange={(e) => setForm({ ...form, requested_date: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
                </div>
                <div>
                  <Label className="text-xs font-mono uppercase text-neutral-500">From</Label>
                  <Input data-testid="vm-book-start" type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
                </div>
                <div>
                  <Label className="text-xs font-mono uppercase text-neutral-500">To</Label>
                  <Input data-testid="vm-book-end" type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} className="mt-2 bg-black/40 border-white/10 text-white" />
                </div>
              </div>
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Notes</Label>
                <Textarea data-testid="vm-book-notes" rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Tournament name, slot preference, etc." className="mt-2 bg-black/40 border-white/10 text-white" />
              </div>
              <div className="flex items-end justify-between">
                <div>
                  <div className="font-display text-3xl text-[#84CC16]">{fmtPrice(selected.price, selected.currency)}</div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500">{selected.price_unit}</div>
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" onClick={() => setSelected(null)} className="text-neutral-400">Cancel</Button>
                  <Button data-testid="vm-book-submit" onClick={submitBooking} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Request booking</Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
