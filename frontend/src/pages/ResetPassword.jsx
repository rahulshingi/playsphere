import { useState } from "react";
import { Link, useLocation, useSearchParams, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const loc = useLocation();
  const nav = useNavigate();
  const isPlayerFlow = loc.pathname.startsWith("/players/");
  const backTo = isPlayerFlow ? "/players/login" : "/login";
  const token = params.get("token") || "";
  const [pwd, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!token) return toast.error("Missing or invalid reset token");
    if (pwd.length < 6) return toast.error("Password must be at least 6 characters");
    if (pwd !== confirm) return toast.error("Passwords do not match");
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pwd });
      toast.success("Password updated. You can sign in now.");
      nav(backTo);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Reset failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-md mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Reset</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">SET NEW PASSWORD</h1>
        {!token && <p className="text-[#FF3B30] mt-4 text-sm">No token in the URL. Use the reset link from your email.</p>}
        <form onSubmit={submit} className="mt-10 space-y-4">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">New password</Label>
            <Input data-testid="reset-pwd" required type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Confirm password</Label>
            <Input data-testid="reset-confirm" required type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <Button data-testid="reset-submit" disabled={busy || !token} className="w-full bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold h-12 rounded-sm">
            {busy ? "Saving…" : "Update password"}
          </Button>
          <p className="text-xs text-neutral-500 text-center"><Link to={backTo} className="text-[#84CC16] hover:underline">← Back to sign in</Link></p>
        </form>
      </div>
    </div>
  );
}
