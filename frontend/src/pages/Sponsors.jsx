import { useEffect, useState } from "react";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";

const tierMeta = {
  title:  { label: "TITLE PARTNER", color: "#007AFF", size: "lg" },
  gold:   { label: "GOLD",          color: "#F59E0B", size: "md" },
  silver: { label: "SILVER",        color: "#A3A3A3", size: "md" },
  bronze: { label: "BRONZE",        color: "#A16207", size: "sm" },
};

export default function Sponsors() {
  const [sponsors, setSponsors] = useState([]);
  useEffect(() => { api.get("/sponsors").then((r) => setSponsors(r.data)); }, []);

  const grouped = ["title", "gold", "silver", "bronze"].map((t) => ({
    tier: t, list: sponsors.filter((s) => s.tier === t),
  }));

  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] tracking-[0.3em] text-[#007AFF] uppercase">/ Partners</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">OUR SPONSORS</h1>
        <p className="text-neutral-400 mt-3 max-w-2xl">PlaySphere stands on the shoulders of brands that believe in workplace play.</p>

        {grouped.map(({ tier, list }) => list.length > 0 && (
          <section key={tier} className="mt-16">
            <div className="flex items-center gap-3 mb-6">
              <span className="w-8 h-1 rounded-full" style={{ background: tierMeta[tier].color }} />
              <span className="font-mono text-xs tracking-[0.3em] uppercase" style={{ color: tierMeta[tier].color }}>{tierMeta[tier].label}</span>
            </div>
            <div className={`grid gap-5 ${tier === "title" ? "grid-cols-1 md:grid-cols-2" : "grid-cols-2 md:grid-cols-3 lg:grid-cols-4"}`}>
              {list.map((s) => (
                <a
                  href={s.website || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  key={s.id}
                  data-testid={`sponsor-card-${s.id}`}
                  className="group border border-white/10 rounded-sm bg-[#141414] p-6 hover-lift block"
                >
                  <div className="flex items-center gap-4">
                    <img src={s.logo_url} alt={s.name} className={`object-cover rounded-sm ${tier === "title" ? "w-20 h-20" : "w-14 h-14"}`} />
                    <div>
                      <div className={`font-semibold ${tier === "title" ? "text-2xl" : "text-base"}`}>{s.name}</div>
                      <div className="text-xs font-mono uppercase text-neutral-500 mt-1">{tierMeta[tier].label}</div>
                    </div>
                  </div>
                  {s.description && <p className="text-sm text-neutral-400 mt-4">{s.description}</p>}
                </a>
              ))}
            </div>
          </section>
        ))}

        {sponsors.length === 0 && (
          <div className="text-center text-neutral-500 py-32">No sponsors listed yet.</div>
        )}

        <div className="mt-24 border border-white/10 rounded-sm p-10 bg-gradient-to-r from-[#007AFF]/10 to-transparent">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#007AFF]">/ Become a sponsor</div>
          <h2 className="font-display text-4xl tracking-wide mt-3">PUT YOUR BRAND IN THE GAME</h2>
          <p className="text-neutral-300 mt-3 max-w-xl">Reach engaged professionals across every tournament. Email partnerships@playsphere.io</p>
        </div>
      </div>
      <Footer />
    </div>
  );
}
