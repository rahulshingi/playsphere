import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function SignupCompany() {
  const { signupCompany } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ company_name: "", admin_name: "", admin_email: "", admin_password: "", contact_phone: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await signupCompany(form);
    setBusy(false);
    if (r.ok) { toast.success(`Welcome, ${r.user.company_name}!`); nav("/dashboard"); }
    else toast.error(r.error);
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ For HR teams</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">ONBOARD YOUR COMPANY</h1>
        <p className="text-neutral-400 mt-3 text-sm">
          Spin up your own private Kreeda Nation — run internal tournaments, hire services, and bring your teams together. Free to start.
        </p>

        <form onSubmit={submit} className="mt-10 space-y-4">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Company name</Label>
            <Input data-testid="signup-company-name" required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Admin name</Label>
              <Input data-testid="signup-admin-name" required value={form.admin_name} onChange={(e) => setForm({ ...form, admin_name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Phone</Label>
              <Input data-testid="signup-phone" value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Work email</Label>
            <Input data-testid="signup-email" type="email" required value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
            <Input data-testid="signup-password" type="password" required minLength={6} value={form.admin_password} onChange={(e) => setForm({ ...form, admin_password: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <Button data-testid="signup-submit" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm">
            {busy ? "Setting up..." : "Create company account"}
          </Button>
          <p className="text-xs text-neutral-500 text-center">
            Already have an account? <Link to="/login" className="text-[#84CC16] hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
      <Footer />
    </div>
  );
}
