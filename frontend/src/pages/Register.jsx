import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await register(form.email, form.password, form.name);
    setBusy(false);
    if (r.ok) { toast.success("Welcome to PlaySphere"); nav("/"); }
    else toast.error(r.error);
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-md mx-auto px-6 py-20">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Create account</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">JOIN PLAYSPHERE</h1>
        <form onSubmit={submit} className="mt-10 space-y-4">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Name</Label>
            <Input data-testid="register-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Email</Label>
            <Input data-testid="register-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
            <Input data-testid="register-password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <Button data-testid="register-submit" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm h-11">
            {busy ? "Creating..." : "Create account"}
          </Button>
        </form>
        <p className="text-xs text-neutral-500 mt-6 text-center">
          Already a member? <Link to="/login" className="text-[#84CC16] hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
