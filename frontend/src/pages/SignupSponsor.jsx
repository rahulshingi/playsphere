import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Megaphone } from "lucide-react";

export default function SignupSponsor() {
  const { refreshMe } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ company_name: "", contact_person: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.company_name.trim() || !form.email.trim()) return toast.error("Company name and email required");
    if (form.password.length < 6) return toast.error("Password must be at least 6 characters");
    setBusy(true);
    try {
      await api.post("/auth/sponsors/signup", {
        company_name: form.company_name.trim(),
        contact_person: form.contact_person.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
      });
      await refreshMe();
      toast.success("Sponsor account created");
      nav("/sponsors/me");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Sign-up failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-md mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FACC15] flex items-center gap-2">
          <Megaphone className="w-3 h-3" /> Sponsor sign-up
        </div>
        <h1 className="font-display text-4xl tracking-wide mt-3">BECOME A SPONSOR</h1>
        <p className="text-neutral-400 text-sm mt-3">
          Reach engaged corporate sports audiences. Browse live tournaments, pick sponsorship slots that match
          your budget &amp; brand goals, and lock them in with one click.
        </p>

        <form onSubmit={submit} className="space-y-4 mt-8">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Company name *</Label>
            <Input data-testid="sponsor-signup-company" value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })}
              placeholder="ACME Realty" className="mt-1 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Contact person</Label>
            <Input data-testid="sponsor-signup-contact" value={form.contact_person} onChange={(e) => setForm({ ...form, contact_person: e.target.value })}
              placeholder="Alice CMO" className="mt-1 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Work email *</Label>
            <Input data-testid="sponsor-signup-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="alice@acmerealty.com" className="mt-1 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Password *</Label>
            <Input data-testid="sponsor-signup-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="Minimum 6 characters" className="mt-1 bg-black/40 border-white/10 text-white" />
          </div>
          <Button data-testid="sponsor-signup-submit" type="submit" disabled={busy}
            className="w-full bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm">
            {busy ? "Creating account…" : "Create sponsor account"}
          </Button>
        </form>

        <div className="text-xs font-mono text-neutral-500 mt-6">
          Already registered? <Link to="/login" className="text-[#FACC15] hover:underline">Sign in</Link>
        </div>
        <div className="text-[10px] font-mono text-neutral-600 mt-2">
          Already running a company on Kreeda Nation? You can browse sponsorship opportunities directly from your existing company login — no separate account needed.
        </div>
      </div>
      <Footer />
    </div>
  );
}
