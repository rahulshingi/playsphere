import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
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
import { Eye, Save, Search } from "lucide-react";

const ROLES = ["any", "batsman", "bowler", "all-rounder", "wicket-keeper"];
const BATTING = ["right", "left"];
const BOWLING = [
  "none", "right-arm-fast", "right-arm-medium", "right-arm-spin",
  "left-arm-fast", "left-arm-medium", "left-arm-spin",
];

export default function PlayerProfile() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [profile, setProfile] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && (!user || user.role !== "player")) { nav("/players/login"); return; }
    if (ready) {
      api.get("/players/me").then((r) => setProfile(r.data));
      api.get("/companies/public").then((r) => setCompanies(r.data));
    }
  }, [ready, user]);

  const upd = (patch) => setProfile({ ...profile, ...patch });

  const save = async () => {
    setBusy(true);
    try {
      const body = { ...profile };
      ["id", "user_id", "mobile", "view_count", "created_at"].forEach((k) => delete body[k]);
      const { data } = await api.patch("/players/me", body);
      setProfile(data);
      toast.success("Profile saved");
    } catch { toast.error("Failed to save"); }
    finally { setBusy(false); }
  };

  if (!profile) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-5xl mx-auto px-6 pt-12 pb-24">
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Your Profile</div>
            <h1 className="font-display text-5xl tracking-wide mt-2">{profile.name.toUpperCase()}</h1>
            <p className="text-neutral-400 text-sm mt-2 font-mono">{profile.mobile}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="font-display text-3xl text-[#84CC16]">{profile.view_count || 0}</div>
              <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-widest flex items-center gap-1"><Eye className="w-3 h-3" /> Profile views</div>
            </div>
            <Link to="/players/profiles" data-testid="search-players-link"><Button variant="outline" className="border-white/10 bg-transparent text-white rounded-sm"><Search className="w-4 h-4 mr-1" /> Find players</Button></Link>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mt-10">
          {/* Avatar + identity */}
          <div className="border border-white/10 rounded-sm bg-[#141414] p-5">
            <div className="aspect-square rounded-sm overflow-hidden bg-black/40 border border-white/10">
              <img src={profile.photo_url || "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} alt="" className="w-full h-full object-cover" />
            </div>
            <Field label="Photo URL"><Input data-testid="pp-photo" value={profile.photo_url || ""} onChange={(e) => upd({ photo_url: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
            <Field label="Company (universal — change any time)">
              <Select value={profile.company_id || ""} onValueChange={(v) => upd({ company_id: v || null })}>
                <SelectTrigger data-testid="pp-company" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Independent" /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10 max-h-80">
                  <SelectItem value="">Independent</SelectItem>
                  {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>
          </div>

          {/* Cricket fields */}
          <div className="md:col-span-2 border border-white/10 rounded-sm bg-[#141414] p-5">
            <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-4">/ Playing details</div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Full name *"><Input data-testid="pp-name" value={profile.name} onChange={(e) => upd({ name: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
              <Field label="City"><Input data-testid="pp-city" value={profile.city || ""} onChange={(e) => upd({ city: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
              <Field label="Date of birth"><Input data-testid="pp-dob" type="date" value={profile.dob || ""} onChange={(e) => upd({ dob: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
              <Field label="Jersey number"><Input data-testid="pp-jersey" type="number" value={profile.jersey_number ?? ""} onChange={(e) => upd({ jersey_number: e.target.value ? Number(e.target.value) : null })} className="bg-black/40 border-white/10 text-white" /></Field>
              <Field label="Playing role">
                <Select value={profile.role || "any"} onValueChange={(v) => upd({ role: v })}>
                  <SelectTrigger data-testid="pp-role" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">{ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                </Select>
              </Field>
              <Field label="Batting hand">
                <Select value={profile.batting_hand || "right"} onValueChange={(v) => upd({ batting_hand: v })}>
                  <SelectTrigger data-testid="pp-batting" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">{BATTING.map((b) => <SelectItem key={b} value={b}>{b}</SelectItem>)}</SelectContent>
                </Select>
              </Field>
              <Field label="Bowling style">
                <Select value={profile.bowling_style || "none"} onValueChange={(v) => upd({ bowling_style: v })}>
                  <SelectTrigger data-testid="pp-bowling" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">{BOWLING.map((b) => <SelectItem key={b} value={b}>{b.replace(/-/g, " ")}</SelectItem>)}</SelectContent>
                </Select>
              </Field>
              <Field label="Cric Heroes profile URL"><Input data-testid="pp-cricheroes" value={profile.cricheroes_url || ""} placeholder="https://cricheroes.com/player/…" onChange={(e) => upd({ cricheroes_url: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
              <Field label="Height (cm)"><Input data-testid="pp-height" type="number" value={profile.height_cm ?? ""} onChange={(e) => upd({ height_cm: e.target.value ? Number(e.target.value) : null })} className="bg-black/40 border-white/10 text-white" /></Field>
              <Field label="Weight (kg)"><Input data-testid="pp-weight" type="number" value={profile.weight_kg ?? ""} onChange={(e) => upd({ weight_kg: e.target.value ? Number(e.target.value) : null })} className="bg-black/40 border-white/10 text-white" /></Field>
            </div>
            <Field label="Bio"><Textarea data-testid="pp-bio" rows={3} value={profile.bio || ""} onChange={(e) => upd({ bio: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
            <Button data-testid="pp-save" disabled={busy} onClick={save} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm mt-2">
              <Save className="w-4 h-4 mr-1" /> {busy ? "Saving…" : "Save profile"}
            </Button>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="mt-3">
      <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</Label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}
