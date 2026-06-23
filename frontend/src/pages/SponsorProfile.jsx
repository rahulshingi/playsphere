import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Save, Building2 } from "lucide-react";
import ImageUpload from "@/components/ImageUpload";

const SPONSOR_INTERESTS = [
  "cricket", "football", "badminton", "basketball", "volleyball", "tabletennis",
  "chess", "quiz", "hackathon",
  "corporate-sports", "employee-engagement", "family-day", "sports-day",
];
const EVENT_TYPES = ["corporate-sports", "inter-company", "single-company", "family-day", "sports-day", "tournament-series"];

function MultiChip({ options, value, onChange, testid }) {
  const set = new Set(value || []);
  return (
    <div className="flex flex-wrap gap-1.5" data-testid={testid}>
      {options.map((o) => {
        const on = set.has(o);
        return (
          <button
            type="button"
            key={o}
            data-testid={`${testid}-${o}`}
            onClick={() => onChange(on ? (value || []).filter((x) => x !== o) : [...(value || []), o])}
            className={`text-[11px] font-mono uppercase px-2.5 py-1 rounded-sm border transition-colors ${
              on ? "bg-[#FACC15] text-black border-transparent" : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
            }`}
          >
            {o.replace(/-/g, " ")}
          </button>
        );
      })}
    </div>
  );
}

// Free-form token input: type a value and press Enter/Comma (or blur) to add it as a chip.
// Backspace on an empty input removes the last chip. Used for things like target locations
// where the options are open-ended (any city, country, etc).
function TokenInput({ value, onChange, placeholder, testid }) {
  const [draft, setDraft] = useState("");
  const list = value || [];

  const commit = (raw) => {
    const next = (raw || "").trim().replace(/,$/, "").trim();
    if (!next) { setDraft(""); return; }
    if (list.some((x) => x.toLowerCase() === next.toLowerCase())) { setDraft(""); return; }
    onChange([...list, next]);
    setDraft("");
  };

  const remove = (idx) => onChange(list.filter((_, i) => i !== idx));

  const onKeyDown = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit(draft);
    } else if (e.key === "Backspace" && !draft && list.length) {
      e.preventDefault();
      remove(list.length - 1);
    }
  };

  return (
    <div data-testid={testid}
      className="mt-1.5 bg-black/40 border border-white/10 rounded-sm px-2 py-1.5 flex flex-wrap gap-1.5 items-center focus-within:border-white/30">
      {list.map((tok, i) => (
        <span key={`${tok}-${i}`} data-testid={`${testid}-chip-${i}`}
          className="inline-flex items-center gap-1 text-[11px] font-mono uppercase px-2 py-0.5 rounded-sm bg-[#FACC15] text-black">
          {tok}
          <button type="button" onClick={() => remove(i)} data-testid={`${testid}-remove-${i}`}
            className="hover:text-[#0a0a0a]/70 leading-none">×</button>
        </span>
      ))}
      <input
        data-testid={`${testid}-input`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => commit(draft)}
        placeholder={list.length === 0 ? placeholder : ""}
        className="flex-1 min-w-[120px] bg-transparent outline-none text-white text-sm py-0.5"
      />
    </div>
  );
}

export default function SponsorProfile() {
  const { user, ready, canSponsor } = useAuth();
  const nav = useNavigate();
  const [profile, setProfile] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && !canSponsor) { nav("/login"); return; }
    if (ready) {
      api.get("/sponsor-profile/me").then((r) => setProfile(r.data)).catch(() => {});
    }
  }, [ready, canSponsor]);

  const upd = (patch) => setProfile({ ...profile, ...patch });

  const save = async () => {
    setBusy(true);
    try {
      const { data } = await api.patch("/sponsor-profile/me", profile);
      setProfile(data);
      toast.success("Sponsor profile saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  if (!profile) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-4xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FACC15] flex items-center gap-2">
          <Building2 className="w-3 h-3" /> Sponsor profile
        </div>
        <h1 className="font-display text-5xl tracking-wide mt-2">{(profile.company_name || "SPONSOR").toUpperCase()}</h1>
        <p className="text-neutral-400 text-sm mt-2">
          Filling out your profile helps us match you with relevant events and gives organisers context when they
          review your sponsorship interest.
        </p>

        <div className="grid md:grid-cols-3 gap-6 mt-10">
          <div className="border border-white/10 rounded-sm bg-[#141414] p-5">
            <div className="aspect-square rounded-sm overflow-hidden bg-black/40 border border-white/10">
              {profile.logo_url ? (
                <img src={profile.logo_url} alt="" className="w-full h-full object-contain p-4" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-neutral-600 text-xs font-mono">No logo</div>
              )}
            </div>
            <Label className="text-[10px] font-mono uppercase text-neutral-500 mt-4 block">Logo</Label>
            <div className="mt-1.5"><ImageUpload value={profile.logo_url} onChange={(v) => upd({ logo_url: v })} testid="sponsor-logo" placeholder="https://… or upload logo" /></div>
          </div>

          <div className="md:col-span-2 border border-white/10 rounded-sm bg-[#141414] p-5 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <FieldEditor label="Company name *" testid="sponsor-company" value={profile.company_name} onChange={(v) => upd({ company_name: v })} />
              <FieldEditor label="Contact person" testid="sponsor-contact" value={profile.contact_person} onChange={(v) => upd({ contact_person: v })} />
              <FieldEditor label="Industry" testid="sponsor-industry" value={profile.industry} onChange={(v) => upd({ industry: v })} placeholder="Real Estate, Banking…" />
              <FieldEditor label="Location" testid="sponsor-location" value={profile.location} onChange={(v) => upd({ location: v })} placeholder="Bangalore, India" />
              <FieldEditor label="Budget range" testid="sponsor-budget" value={profile.budget_range} onChange={(v) => upd({ budget_range: v })} placeholder="₹10,000 – ₹5,00,000" />
              <FieldEditor label="Website" testid="sponsor-website" value={profile.website} onChange={(v) => upd({ website: v })} placeholder="https://…" />
            </div>

            <div>
              <Label className="text-[10px] font-mono uppercase text-neutral-500">Target audience description</Label>
              <Textarea data-testid="sponsor-audience" rows={2} value={profile.target_audience || ""}
                onChange={(e) => upd({ target_audience: e.target.value })} placeholder="Mid-senior IT professionals, 25-45 yrs, urban India"
                className="mt-1.5 bg-black/40 border-white/10 text-white" />
            </div>

            <div>
              <Label className="text-[10px] font-mono uppercase text-neutral-500">Target locations</Label>
              <p className="text-[10px] text-neutral-500 mt-1">Type a city and press <span className="font-mono">Enter</span> or <span className="font-mono">,</span> to add. Click × to remove.</p>
              <TokenInput
                testid="sponsor-target-locations"
                value={profile.target_locations}
                onChange={(v) => upd({ target_locations: v })}
                placeholder="Bangalore, Mumbai, Hyderabad…"
              />
            </div>

            <div>
              <Label className="text-[10px] font-mono uppercase text-neutral-500">Sponsor interests</Label>
              <p className="text-[10px] text-neutral-500 mt-1">Pick what your brand wants to attach itself to.</p>
              <div className="mt-2"><MultiChip options={SPONSOR_INTERESTS} value={profile.sponsor_interests} onChange={(v) => upd({ sponsor_interests: v })} testid="sponsor-interests" /></div>
            </div>

            <div>
              <Label className="text-[10px] font-mono uppercase text-neutral-500">Target event types</Label>
              <div className="mt-2"><MultiChip options={EVENT_TYPES} value={profile.target_event_types} onChange={(v) => upd({ target_event_types: v })} testid="sponsor-target-types" /></div>
            </div>

            <Button data-testid="sponsor-save" disabled={busy} onClick={save}
              className="bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm">
              <Save className="w-4 h-4 mr-1" /> {busy ? "Saving…" : "Save sponsor profile"}
            </Button>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

function FieldEditor({ label, testid, value, onChange, placeholder }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase text-neutral-500">{label}</Label>
      <Input data-testid={testid} value={value || ""} placeholder={placeholder} onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 bg-black/40 border-white/10 text-white" />
    </div>
  );
}
