import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function PlayerLogin() {
  const nav = useNavigate();
  const { } = useAuth();
  const [form, setForm] = useState({ mobile: "", password: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/players/login", form);
      toast.success(`Welcome, ${data.name}`);
      // hard reload to refresh auth context
      window.location.href = "/players/me";
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Login failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-md mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Players</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">PLAYER SIGN IN</h1>
        <form onSubmit={submit} className="mt-10 space-y-4">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Mobile number</Label>
            <Input data-testid="player-login-mobile" required value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
            <Input data-testid="player-login-password" required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <Button data-testid="player-login-submit" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm">
            {busy ? "Signing in..." : "Sign in"}
          </Button>
          <div className="text-xs text-neutral-500 text-center space-y-1">
            <p>New here? <Link to="/players/signup" className="text-[#84CC16] hover:underline">Create player account</Link></p>
            <p><Link data-testid="player-forgot-link" to="/players/forgot-password" className="text-[#06B6D4] hover:underline">Forgot password?</Link></p>
          </div>
        </form>
      </div>
    </div>
  );
}
