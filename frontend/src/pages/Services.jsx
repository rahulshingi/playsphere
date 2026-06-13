import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";

const categoryMeta = {
  streaming:   { label: "STREAMING",   color: "#EC4899" },
  apparel:     { label: "APPAREL",     color: "#A855F7" },
  merchandise: { label: "MERCH",       color: "#06B6D4" },
  awards:      { label: "AWARDS",      color: "#F59E0B" },
  venue:       { label: "VENUE",       color: "#84CC16" },
  equipment:   { label: "EQUIPMENT",   color: "#10B981" },
  training:    { label: "TRAINING",    color: "#FF3B30" },
  other:       { label: "OTHER",       color: "#737373" },
};

export default function Services() {
  const [services, setServices] = useState([]);
  const [filter, setFilter] = useState("all");

  useEffect(() => { api.get("/services").then((r) => setServices(r.data)); }, []);

  const cats = ["all", ...Object.keys(categoryMeta).filter((k) => services.some((s) => s.category === k))];
  const filtered = filter === "all" ? services : services.filter((s) => s.category === filter);

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Marketplace</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">SERVICES</h1>
        <p className="text-neutral-400 mt-3 max-w-2xl">
          Everything you need to run a flagship tournament — from broadcast and merchandise to grounds and trophies. Hire on-demand for your event.
        </p>

        <div className="flex gap-2 mt-10 border-b border-white/10 pb-4 overflow-x-auto scrollbar-thin">
          {cats.map((c) => (
            <button
              key={c}
              data-testid={`services-filter-${c}`}
              onClick={() => setFilter(c)}
              className={`px-3 py-1.5 text-xs font-mono uppercase tracking-widest rounded-sm transition shrink-0 ${
                filter === c ? "bg-[#84CC16] text-black" : "text-neutral-400 hover:text-white"
              }`}
            >
              {c === "all" ? "ALL" : categoryMeta[c]?.label || c}
            </button>
          ))}
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 mt-8">
          {filtered.map((s) => {
            const meta = categoryMeta[s.category] || categoryMeta.other;
            return (
              <Link key={s.id} to={`/services/${s.id}`} data-testid={`service-card-${s.id}`} className="group border border-white/10 rounded-sm bg-[#141414] overflow-hidden hover-lift">
                <div className="h-44 relative overflow-hidden">
                  <img src={s.images?.[0] || "https://images.unsplash.com/photo-1517649763962-0c623066013b?w=900"} className="w-full h-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-700" alt="" />
                  <span className="absolute top-3 left-3 font-mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm border bg-black/60" style={{ borderColor: meta.color, color: meta.color }}>{meta.label}</span>
                </div>
                <div className="p-5">
                  <h3 className="text-lg font-semibold group-hover:text-[#84CC16]">{s.name}</h3>
                  <p className="text-sm text-neutral-400 mt-2 line-clamp-2">{s.description}</p>
                  <div className="flex items-end justify-between mt-4">
                    <div>
                      <div className="font-mono text-2xl text-white">${s.base_price.toFixed(0)}</div>
                      <div className="text-[10px] font-mono uppercase text-neutral-500">{s.price_unit}</div>
                    </div>
                    {s.variants?.length > 0 && (
                      <div className="text-[10px] font-mono uppercase text-[#84CC16]">{s.variants.length} options</div>
                    )}
                  </div>
                </div>
              </Link>
            );
          })}
          {filtered.length === 0 && <div className="col-span-full text-neutral-500 text-center py-20">No services here yet.</div>}
        </div>
      </div>
      <Footer />
    </div>
  );
}
