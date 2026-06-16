import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmtPrice } from "@/lib/currency";
import { X, MapPin } from "lucide-react";

export default function VenuePicker({ open, onClose, onPick }) {
  const [city, setCity] = useState("");
  const [cities, setCities] = useState([]);
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (!open) return;
    api.get("/vendor-listings/cities?vendor_type=ground").then((r) => setCities(r.data)).catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const params = new URLSearchParams();
    if (city) params.set("city", city);
    if (q) params.set("q", q);
    api.get(`/venues/suggest?${params.toString()}`).then((r) => setResults(r.data)).catch(() => setResults([]));
  }, [city, q, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6" onClick={onClose}>
      <div data-testid="venue-picker" className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-2xl my-10 text-white" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h3 className="font-display text-2xl tracking-wider">PICK A VERIFIED VENUE</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-white"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-6 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <Select value={city} onValueChange={setCity}>
              <SelectTrigger data-testid="vp-city" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="City" /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                <SelectItem value=" ">Any city</SelectItem>
                {cities.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
            <Input data-testid="vp-query" placeholder="Search venue name…" value={q} onChange={(e) => setQ(e.target.value)} className="bg-black/40 border-white/10 text-white" />
          </div>
          <div className="space-y-2 max-h-[440px] overflow-auto">
            {results.length === 0 && <div className="text-center text-neutral-500 py-8 text-sm">No verified venues match.</div>}
            {results.map((v) => (
              <button key={v.id} data-testid={`vp-result-${v.id}`} onClick={() => { onPick(v); onClose(); }} className="w-full text-left border border-white/10 rounded-sm bg-[#141414] hover:bg-black/40 p-3 flex items-center justify-between">
                <div>
                  <div className="font-semibold">{v.title}</div>
                  <div className="text-[11px] font-mono text-neutral-500 flex items-center gap-1"><MapPin className="w-3 h-3" />{v.city} · {(v.sports || []).slice(0, 3).join(" · ")}</div>
                </div>
                <div className="font-mono text-[#84CC16]">{fmtPrice(v.price, v.currency)}/hr</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
