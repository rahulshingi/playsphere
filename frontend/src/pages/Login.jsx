import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("admin@playsphere.com");
  const [password, setPassword] = useState("admin123");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await login(email, password);
    setBusy(false);
    if (r.ok) {
      toast.success("Welcome back");
      // Role-aware redirect happens here; r contains user (returned from /auth/login via context)
      // Re-fetch user from /me would be slow; rely on local state via reloading after a tick.
      const role = r.user?.role || (r && r.user ? r.user.role : null);
      if (role === "platform_admin" || role === "admin") nav("/platform-admin");
      else if (role === "company_admin") nav("/dashboard");
      else nav("/");
    }
    else toast.error(r.error);
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-md mx-auto px-6 py-20">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Sign in</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">ENTER THE ARENA</h1>
        <p className="text-neutral-400 mt-2 text-sm">Admin access to manage events, teams and live scoring.</p>

        <form onSubmit={submit} className="mt-10 space-y-4">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Email</Label>
            <Input data-testid="login-email" value={email} onChange={(e) => setEmail(e.target.value)} required type="email" className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
            <Input data-testid="login-password" value={password} onChange={(e) => setPassword(e.target.value)} required type="password" className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <Button data-testid="login-submit" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm h-11">
            {busy ? "Signing in..." : "Sign in"}
          </Button>
        </form>

        <p className="text-xs text-neutral-500 mt-6 text-center">
          New here? <Link to="/register" className="text-[#84CC16] hover:underline">Create account</Link>
        </p>
        <div className="mt-6 p-3 border border-white/10 rounded-sm text-[11px] font-mono text-neutral-400 leading-relaxed">
          Demo admin · admin@playsphere.com / admin123
        </div>
      </div>
    </div>
  );
}
