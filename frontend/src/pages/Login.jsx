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
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await login(email, password);
    setBusy(false);
    if (r.ok) {
      toast.success("Welcome back");
      const role = r.user?.role || (r && r.user ? r.user.role : null);
      if (role === "platform_admin" || role === "admin") nav("/platform-admin");
      else if (role === "company_admin" || role === "organiser") nav("/dashboard");
      else if (role === "vendor") nav("/vendor/dashboard");
      else if (role === "player") nav("/players/me");
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
            <Label className="text-xs font-mono uppercase text-neutral-500">Email or mobile number</Label>
            <Input data-testid="login-email" value={email} onChange={(e) => setEmail(e.target.value)} required type="text" autoComplete="username" placeholder="you@company.com or 98765..." className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
            <Input data-testid="login-password" value={password} onChange={(e) => setPassword(e.target.value)} required type="password" className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <Button data-testid="login-submit" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm h-11">
            {busy ? "Signing in..." : "Sign in"}
          </Button>
        </form>

        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px bg-white/10" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">or</span>
          <div className="flex-1 h-px bg-white/10" />
        </div>

        <button
          data-testid="login-google"
          onClick={() => {
            const redirect = `${window.location.origin}/auth/callback`;
            window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirect)}`;
          }}
          className="w-full bg-white text-[#0a0a0a] font-semibold rounded-sm h-11 flex items-center justify-center gap-3 hover:bg-neutral-200 transition-colors"
        >
          <svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
            <path fill="#EA4335" d="M24 9.5c3.9 0 7.4 1.35 10.1 3.6l7.5-7.5C36.8 1.8 30.8-.5 24-.5 14.6-.5 6.4 4.9 2.5 12.7l8.7 6.7C13.2 13.1 18.1 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.5 24.5c0-1.6-.15-3.15-.4-4.65H24v9.3h12.7c-.6 3-2.35 5.55-5 7.3l7.75 6c4.5-4.15 7.05-10.25 7.05-17.95z"/>
            <path fill="#FBBC05" d="M11.2 28.6c-.5-1.5-.8-3.1-.8-4.6s.3-3.1.8-4.6l-8.7-6.7C.9 16.1 0 20 0 24s.9 7.9 2.5 11.3l8.7-6.7z"/>
            <path fill="#34A853" d="M24 48.5c6.8 0 12.5-2.25 16.7-6.1l-7.75-6c-2.15 1.45-4.9 2.3-8.95 2.3-5.9 0-10.8-3.6-12.8-8.9l-8.7 6.7C6.4 43.6 14.6 48.5 24 48.5z"/>
          </svg>
          Sign in with Google
        </button>

        <p className="text-xs text-neutral-500 mt-6 text-center">
          New here? <Link to="/register" className="text-[#84CC16] hover:underline">Create account</Link>
        </p>
        <p className="text-xs text-neutral-500 mt-1 text-center">
          <Link data-testid="login-forgot-link" to="/forgot-password" className="text-[#06B6D4] hover:underline">Forgot password?</Link>
        </p>
      </div>
    </div>
  );
}
