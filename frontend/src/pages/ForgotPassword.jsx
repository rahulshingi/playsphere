import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function ForgotPassword() {
  const loc = useLocation();
  const isPlayerFlow = loc.pathname.startsWith("/players/");
  const backTo = isPlayerFlow ? "/players/login" : "/login";

  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
      toast.success("If the email matches an account, a reset link has been generated");
    } catch {
      toast.error("Something went wrong");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-md mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Reset</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">FORGOT PASSWORD</h1>
        <p className="text-xs text-neutral-500 mt-3">{isPlayerFlow ? "For player accounts." : "Works for company HR, vendors, and platform admin."}</p>
        {sent ? (
          <div className="mt-8 border border-white/10 rounded-sm bg-[#141414] p-5 text-sm text-neutral-300">
            <p data-testid="forgot-sent">Check your email for the reset link. The link is valid for 1 hour.</p>
            <p className="text-xs text-neutral-500 mt-3">If you don't receive an email shortly, ask your admin to fetch the reset link from the backend logs (email integration is being set up).</p>
            <Link to={backTo} className="text-[#84CC16] hover:underline text-xs mt-4 inline-block">← Back to sign in</Link>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-10 space-y-4">
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Registered email</Label>
              <Input data-testid="forgot-email" required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <Button data-testid="forgot-submit" disabled={busy} className="w-full bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold h-12 rounded-sm">
              {busy ? "Sending…" : "Send reset link"}
            </Button>
            <p className="text-xs text-neutral-500 text-center"><Link to={backTo} className="text-[#84CC16] hover:underline">← Back to sign in</Link></p>
          </form>
        )}
      </div>
    </div>
  );
}
