import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

export default function PlayerSignup() {
  const nav = useNavigate();
  const [companies, setCompanies] = useState([]);
  const [form, setForm] = useState({ name: "", mobile: "", password: "", company_id: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/companies/public").then((r) => setCompanies(r.data)); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/players/register", form);
      toast.success("Welcome to Kreeda Nation!");
      // hard reload to refresh auth context (matches PlayerLogin pattern)
      window.location.href = "/players/me";
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Sign up failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-md mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Players</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">JOIN AS A PLAYER</h1>
        <p className="text-neutral-400 mt-3 text-sm">
          One profile, every tournament. Mobile number is your universal ID — change companies any time without losing your stats.
        </p>

        <form onSubmit={submit} className="mt-8 space-y-4">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Full name</Label>
            <Input data-testid="player-signup-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Mobile number</Label>
            <Input data-testid="player-signup-mobile" required value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value })} placeholder="+91 9876543210" className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
            <Input data-testid="player-signup-password" required type="password" minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Your company</Label>
            <Select value={form.company_id} onValueChange={(v) => setForm({ ...form, company_id: v })}>
              <SelectTrigger data-testid="player-signup-company" className="mt-2 bg-[#141414] border-white/10 text-white"><SelectValue placeholder="Select your company (optional)" /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10 max-h-80">
                {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <p className="text-[10px] text-neutral-500 mt-1">Don't see your company? <Link to="/signup-company" className="text-[#84CC16] underline">Onboard it →</Link></p>
          </div>
          <Button data-testid="player-signup-submit" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm">
            {busy ? "Creating..." : "Create player account"}
          </Button>
          <p className="text-xs text-neutral-500 text-center">
            Already registered? <Link to="/players/login" className="text-[#84CC16] hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
      <Footer />
    </div>
  );
}
