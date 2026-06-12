import { useEffect, useState } from "react";
import api from "@/lib/api";

export default function SponsorBanner() {
  const [sponsors, setSponsors] = useState([]);
  useEffect(() => {
    api.get("/sponsors").then((r) => setSponsors(r.data.filter((s) => s.show_in_banner))).catch(() => {});
  }, []);
  if (!sponsors.length) return null;
  return (
    <section data-testid="sponsor-banner" className="border-y border-white/10 bg-[#0c0c0c]">
      <div className="max-w-7xl mx-auto px-6 py-6 flex items-center gap-8">
        <span className="font-mono text-[10px] tracking-[0.25em] text-neutral-500 uppercase shrink-0">
          Powered by
        </span>
        <div className="flex items-center gap-10 overflow-x-auto scrollbar-thin flex-1">
          {sponsors.map((s) => (
            <div
              key={s.id}
              data-testid={`sponsor-logo-${s.id}`}
              className="flex items-center gap-3 shrink-0 grayscale opacity-70 hover:opacity-100 hover:grayscale-0 transition"
            >
              <img src={s.logo_url} alt={s.name} className="w-10 h-10 object-cover rounded-sm" />
              <div>
                <div className="text-sm font-semibold text-white">{s.name}</div>
                <div className="text-[10px] font-mono uppercase text-neutral-500">{s.tier}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
