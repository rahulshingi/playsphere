import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Nav from "@/components/Nav";
import SEO from "@/components/SEO";
import Footer from "@/components/Footer";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Sparkles, ArrowRight, Package, CheckCircle2, Info } from "lucide-react";

/**
 * CorporateServices (customer-facing) — Phase 1 stub.
 *
 * HR / Organiser see the category+package catalogue read-only. The full
 * package customiser + RFQ submission flow lands in Phase 2. Other roles
 * (players, vendors, anonymous) get a soft-gate explaining what this is.
 */
export default function CorporateServices() {
  const nav = useNavigate();
  const { user, isCompanyAdmin, ready } = useAuth();
  const [categories, setCategories] = useState([]);
  const [packages, setPackages] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ready) return;
    if (!isCompanyAdmin) return;  // gate — no fetch
    (async () => {
      try {
        const cats = (await api.get("/corporate-services/categories")).data || [];
        setCategories(cats);
        const packByCat = {};
        await Promise.all(cats.map(async (c) => {
          const r = await api.get(`/corporate-services/packages?category_id=${c.id}`);
          packByCat[c.id] = r.data || [];
        }));
        setPackages(packByCat);
      } catch { /* soft-fail */ } finally { setLoading(false); }
    })();
  }, [ready, isCompanyAdmin]);

  // Shared SEO meta — must render across all branches (guest, wrong-role, HR)
  // so search-engine crawlers get consistent title/description regardless of
  // the auth gate they land on.
  const seo = (
    <SEO
      title="Corporate Services — Custom Employee Engagement Events | Kreeda Nation"
      description="Curated tournament, yoga, wellness and offsite packages for HR teams. Customise, submit an RFQ, and get a tailored quote within 24 hours."
      canonical="/corporate-services"
    />
  );

  // Not signed in → nudge to login
  if (ready && !user) {
    return (
      <div className="bg-[#0a0a0a] min-h-screen text-white">
        {seo}
        <Nav />
        <Gate title="Sign in to view Corporate Services" body="Corporate Services are available to HR and Organiser accounts only. Sign in to browse curated event packages and request a quote." ctaLabel="Sign in" onClick={() => nav("/login")} />
        <Footer />
      </div>
    );
  }
  // Signed in but wrong role → gate
  if (ready && user && !isCompanyAdmin) {
    return (
      <div className="bg-[#0a0a0a] min-h-screen text-white">
        {seo}
        <Nav />
        <Gate title="Not available for your account" body="Corporate Services are curated event packages for Company HR and Event Organisers. Your account doesn't have access." ctaLabel="Back to home" onClick={() => nav("/")} />
        <Footer />
      </div>
    );
  }

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      {seo}
      <Nav />
      <div className="max-w-6xl mx-auto px-6 pt-14 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Corporate Services</div>
        <h1 className="font-display text-4xl md:text-5xl tracking-wide mt-2">CURATED EVENT PACKAGES</h1>
        <p className="text-neutral-400 mt-3 text-sm max-w-2xl">
          Pick a category, choose a package, tell us what you need. Our team returns a quotation within 24 hours. No pricing shown up front — every quote is tailored to your event size, venue and add-ons.
        </p>

        <div className="mt-4 inline-flex items-center gap-2 border border-[#FACC15]/30 bg-[#FACC15]/5 rounded-sm px-3 py-2 text-xs text-neutral-300">
          <Sparkles className="w-3.5 h-3.5 text-[#FACC15]" />
          <span>Pick a package below, customise services and add-ons, tell us about your event — we&rsquo;ll return a tailored quotation within 24 hours.</span>
          <Link to="/rfqs" className="ml-2 text-[#FACC15] hover:underline font-mono uppercase text-[10px]">My RFQs →</Link>
        </div>

        {loading && <div className="text-neutral-500 text-sm mt-10">Loading catalogue…</div>}

        {!loading && categories.length === 0 && (
          <div data-testid="cs-empty" className="text-neutral-500 text-sm mt-10 text-center border border-dashed border-white/10 rounded-sm p-10">
            <Info className="w-6 h-6 mx-auto text-neutral-500 mb-2" />
            No categories published yet. Check back soon — the platform admin is finalising the catalogue.
          </div>
        )}

        {!loading && categories.map((c) => (
          <section key={c.id} data-testid={`cs-cat-${c.id}`} className="mt-12">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16]">/ Category</div>
                <h2 className="text-2xl font-display tracking-wide mt-1">{c.name}</h2>
                {c.description && <p className="text-sm text-neutral-400 mt-1 max-w-2xl">{c.description}</p>}
              </div>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
              {(packages[c.id] || []).map((p) => (
                <div key={p.id} data-testid={`cs-pkg-${p.id}`} className="border border-white/10 bg-[#141414] rounded-sm p-4 hover:border-white/25 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4]">{p.tier || "package"}</div>
                      <div className="font-semibold text-lg mt-0.5">{p.name}</div>
                    </div>
                    <Package className="w-4 h-4 text-neutral-500" />
                  </div>
                  {p.description && <p className="text-xs text-neutral-400 mt-2 leading-relaxed line-clamp-3">{p.description}</p>}
                  {p.included_services?.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {p.included_services.slice(0, 4).map((s) => (
                        <li key={s.id} className="text-xs text-neutral-300 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3 h-3 text-[#84CC16] shrink-0" /> {s.name}
                        </li>
                      ))}
                      {p.included_services.length > 4 && (
                        <li className="text-[10px] font-mono text-neutral-500">+ {p.included_services.length - 4} more</li>
                      )}
                    </ul>
                  )}
                  <Button data-testid={`cs-request-${p.id}`} onClick={() => nav(`/corporate-services/customize/${p.id}`)} className="w-full mt-4 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
                    Customise & request quote <ArrowRight className="ml-1 w-3 h-3" />
                  </Button>
                </div>
              ))}
              {(packages[c.id] || []).length === 0 && (
                <div className="text-neutral-500 text-xs col-span-full">No packages yet in this category.</div>
              )}
            </div>
          </section>
        ))}
      </div>
      <Footer />
    </div>
  );
}

function Gate({ title, body, ctaLabel, onClick }) {
  return (
    <div className="max-w-md mx-auto px-6 pt-24 pb-24 text-center">
      <Sparkles className="w-10 h-10 text-[#06B6D4] mx-auto" />
      <h1 className="font-display text-3xl tracking-wide mt-4">{title}</h1>
      <p className="text-neutral-400 mt-3 text-sm">{body}</p>
      <Button onClick={onClick} className="mt-6 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm h-11 px-6">{ctaLabel}</Button>
    </div>
  );
}
