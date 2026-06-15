import { useEffect, useState } from "react";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Linkedin, Twitter, Globe } from "lucide-react";

export default function About() {
  const [a, setA] = useState(null);
  useEffect(() => { api.get("/about").then((r) => setA(r.data)); }, []);
  if (!a) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-6xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ About Kreeda Nation</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">WHO WE ARE</h1>
        {a.company_description && <p className="text-neutral-300 mt-5 max-w-3xl text-lg leading-relaxed">{a.company_description}</p>}

        <div className="grid md:grid-cols-2 gap-6 mt-16">
          {a.mission && (
            <div className="border border-white/10 rounded-sm bg-[#141414] p-7">
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#EC4899]">/ Mission</div>
              <p className="text-neutral-200 mt-3 leading-relaxed">{a.mission}</p>
            </div>
          )}
          {a.vision && (
            <div className="border border-white/10 rounded-sm bg-[#141414] p-7">
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4]">/ Vision</div>
              <p className="text-neutral-200 mt-3 leading-relaxed">{a.vision}</p>
            </div>
          )}
        </div>

        {(a.founders?.length > 0) && (
          <section className="mt-20">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Founders</div>
            <h2 className="font-display text-4xl tracking-wide mt-2 mb-8">THE PEOPLE BEHIND KREEDA NATION</h2>
            <PeopleGrid people={a.founders} />
          </section>
        )}

        {(a.directors?.length > 0) && (
          <section className="mt-20">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Leadership</div>
            <h2 className="font-display text-4xl tracking-wide mt-2 mb-8">BOARD &amp; DIRECTORS</h2>
            <PeopleGrid people={a.directors} />
          </section>
        )}
      </div>
      <Footer />
    </div>
  );
}

function PeopleGrid({ people }) {
  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
      {people.map((p, i) => (
        <div key={i} data-testid={`about-person-${i}`} className="border border-white/10 rounded-sm bg-[#141414] overflow-hidden">
          <div className="aspect-[4/3] bg-black/40">
            {p.image_url && <img src={p.image_url} className="w-full h-full object-cover" alt="" />}
          </div>
          <div className="p-5">
            <div className="text-xl font-semibold">{p.name}</div>
            <div className="text-xs font-mono uppercase text-[#84CC16] mt-1">{p.role}</div>
            {p.bio && <p className="text-sm text-neutral-400 mt-3 leading-relaxed">{p.bio}</p>}
            <div className="flex gap-2 mt-4">
              {p.linkedin_url && <a href={p.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-neutral-400 hover:text-[#84CC16]"><Linkedin className="w-4 h-4" /></a>}
              {p.twitter_url && <a href={p.twitter_url} target="_blank" rel="noopener noreferrer" className="text-neutral-400 hover:text-[#84CC16]"><Twitter className="w-4 h-4" /></a>}
              {p.website_url && <a href={p.website_url} target="_blank" rel="noopener noreferrer" className="text-neutral-400 hover:text-[#84CC16]"><Globe className="w-4 h-4" /></a>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
