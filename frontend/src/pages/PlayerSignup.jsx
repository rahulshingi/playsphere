import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import OtpVerifyStep from "@/components/OtpVerifyStep";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { CheckCircle2, Building2 } from "lucide-react";

/**
 * PlayerSignup — 3-step flow (Jul 2026 update).
 *
 *   1. Details   — personal email + password (no corporate email restriction).
 *   2. Verify    — OTP to personal email.
 *   3. Company   — OPTIONAL: enter work email + verify with OTP so HR at
 *                  that company can add the player to tournaments. Player
 *                  can skip.
 *
 * `?ref_vendor=` still stamps offline-source (unchanged).
 */
export default function PlayerSignup() {
  const [form, setForm] = useState({ name: "", mobile: "", email: "", password: "" });
  const [step, setStep] = useState("details"); // details | verify | company | done
  const [busy, setBusy] = useState(false);
  const [searchParams] = useSearchParams();
  const refVendor = searchParams.get("ref_vendor") || "";

  // Corporate email substate
  const [corpEmail, setCorpEmail] = useState("");
  const [corpOtpSent, setCorpOtpSent] = useState(false);
  const [corpOtp, setCorpOtp] = useState("");
  const [linkResult, setLinkResult] = useState(null);

  const requestOtp = async () => {
    if (form.password.length < 6) return toast.error("Password must be at least 6 characters");
    setBusy(true);
    try {
      await api.post("/players/signup/request-otp", {
        email: form.email.trim().toLowerCase(), name: form.name.trim(),
      });
      toast.success(`Verification code sent to ${form.email}`);
      setStep("verify");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not send verification code");
    } finally { setBusy(false); }
  };

  const resendOtp = async () => {
    try {
      await api.post("/players/signup/request-otp", {
        email: form.email.trim().toLowerCase(), name: form.name.trim(),
      });
      toast.success("New verification code sent");
      return true;
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not resend");
      return false;
    }
  };

  const completeSignup = async (otp) => {
    setBusy(true);
    try {
      await api.post("/players/register", {
        ...form, email: form.email.trim().toLowerCase(), otp,
        ref_vendor: refVendor || undefined,
      });
      toast.success("Account created — one last optional step");
      setStep("company");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Sign up failed");
    } finally { setBusy(false); }
  };

  const requestCorpOtp = async () => {
    if (!corpEmail.includes("@")) return toast.error("Enter your work email first");
    setBusy(true);
    try {
      await api.post("/players/me/corporate-email/request-otp", { corporate_email: corpEmail.trim().toLowerCase() });
      toast.success(`Code sent to ${corpEmail}`);
      setCorpOtpSent(true);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not send code");
    } finally { setBusy(false); }
  };

  const verifyCorpOtp = async () => {
    if (corpOtp.length < 4) return toast.error("Enter the 6-digit code");
    setBusy(true);
    try {
      const { data } = await api.post("/players/me/corporate-email/verify", {
        corporate_email: corpEmail.trim().toLowerCase(),
        otp: corpOtp.trim(),
      });
      setLinkResult(data);
      toast.success(data.message);
      setStep("done");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Verification failed");
    } finally { setBusy(false); }
  };

  const skipCompany = () => { window.location.href = "/players/me"; };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-md mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Players</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">JOIN AS A PLAYER</h1>
        <p className="text-neutral-400 mt-3 text-sm">
          One profile, every tournament. Sign up with your personal email — link your work email later so HR can find you.
        </p>

        <div className="flex items-center gap-2 mt-8 text-[10px] font-mono uppercase tracking-widest flex-wrap" data-testid="signup-steps">
          <span className={step === "details" ? "text-[#84CC16]" : "text-neutral-500"}>① Details</span>
          <span className="text-neutral-700">/</span>
          <span className={step === "verify" ? "text-[#84CC16]" : "text-neutral-500"}>② Verify email</span>
          <span className="text-neutral-700">/</span>
          <span className={step === "company" || step === "done" ? "text-[#84CC16]" : "text-neutral-500"}>③ Link company (optional)</span>
        </div>

        {step === "details" && (
          <form onSubmit={(e) => { e.preventDefault(); requestOtp(); }} className="mt-8 space-y-4">
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Full name</Label>
              <Input data-testid="player-signup-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Mobile number</Label>
              <Input data-testid="player-signup-mobile" required value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value })} placeholder="+91 9876543210" className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Personal email</Label>
              <Input data-testid="player-signup-email" required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@gmail.com" className="mt-2 bg-[#141414] border-white/10 text-white" />
              <p className="text-[10px] text-neutral-500 mt-1">Use any email — Gmail, Yahoo, personal domain. This is your login.</p>
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
              <Input data-testid="player-signup-password" required type="password" minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <Button type="submit" data-testid="player-signup-request-otp" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm">
              {busy ? "Sending code..." : "Send verification code"}
            </Button>
            <p className="text-xs text-neutral-500 text-center">
              Already registered? <Link to="/players/login" className="text-[#84CC16] hover:underline">Sign in</Link>
            </p>
          </form>
        )}

        {step === "verify" && (
          <div className="mt-8">
            <OtpVerifyStep
              email={form.email}
              busy={busy}
              onSubmit={completeSignup}
              onResend={resendOtp}
              onBack={() => setStep("details")}
              testidPrefix="player-signup-otp"
            />
          </div>
        )}

        {step === "company" && (
          <div className="mt-8 space-y-4" data-testid="player-signup-company-step">
            <div className="border border-[#06B6D4]/30 bg-[#06B6D4]/5 rounded-sm p-4 flex gap-3">
              <Building2 className="w-5 h-5 text-[#06B6D4] shrink-0 mt-0.5" />
              <div className="text-xs text-neutral-300 leading-relaxed">
                <div className="font-semibold text-white mb-1">Optional · but recommended</div>
                Add your <b>work email</b> to link this profile to your company. When your HR joins Kreeda Nation, you&rsquo;ll show up in their player search — instantly eligible for corporate tournaments, wellness events and sponsored leagues. You can always add / change this later from your profile.
              </div>
            </div>

            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Work email</Label>
              <Input
                data-testid="player-signup-corp-email"
                type="email"
                placeholder="you@yourcompany.com"
                value={corpEmail}
                onChange={(e) => setCorpEmail(e.target.value)}
                disabled={corpOtpSent}
                className="mt-2 bg-[#141414] border-white/10 text-white disabled:opacity-70"
              />
              <p className="text-[10px] text-neutral-500 mt-1">We&rsquo;ll send a 6-digit code here.</p>
            </div>

            {!corpOtpSent && (
              <div className="flex gap-2">
                <Button data-testid="player-signup-corp-request" onClick={requestCorpOtp} disabled={busy} className="flex-1 bg-[#06B6D4] hover:bg-[#0891B2] text-white font-semibold h-11 rounded-sm">
                  {busy ? "Sending…" : "Send code"}
                </Button>
                <Button variant="outline" data-testid="player-signup-corp-skip" onClick={skipCompany} className="border-white/10 text-neutral-300 h-11">
                  Skip for now
                </Button>
              </div>
            )}

            {corpOtpSent && (
              <>
                <div>
                  <Label className="text-xs font-mono uppercase text-neutral-500">Enter 6-digit code</Label>
                  <Input
                    data-testid="player-signup-corp-otp"
                    value={corpOtp}
                    onChange={(e) => setCorpOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    maxLength={6}
                    className="mt-2 bg-[#141414] border-white/10 text-white text-center text-2xl tracking-[0.5em] font-mono"
                  />
                </div>
                <div className="flex gap-2">
                  <Button data-testid="player-signup-corp-verify" onClick={verifyCorpOtp} disabled={busy} className="flex-1 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-11 rounded-sm">
                    {busy ? "Verifying…" : "Verify & link"}
                  </Button>
                  <Button variant="outline" data-testid="player-signup-corp-resend" onClick={requestCorpOtp} disabled={busy} className="border-white/10 text-neutral-300 h-11">
                    Resend
                  </Button>
                </div>
                <button data-testid="player-signup-corp-skip2" onClick={skipCompany} className="w-full text-xs text-neutral-500 hover:text-neutral-300 py-2">
                  Or skip — link later from profile
                </button>
              </>
            )}
          </div>
        )}

        {step === "done" && (
          <div className="mt-8 space-y-4" data-testid="player-signup-done">
            <div className="border border-[#84CC16]/30 bg-[#84CC16]/5 rounded-sm p-6 text-center">
              <CheckCircle2 className="w-10 h-10 text-[#84CC16] mx-auto mb-3" />
              <div className="text-lg font-semibold">All set!</div>
              <p className="text-sm text-neutral-400 mt-2">{linkResult?.message}</p>
              {linkResult?.linked_company_name && (
                <p className="text-xs text-[#06B6D4] mt-2 font-mono uppercase">Linked to {linkResult.linked_company_name}</p>
              )}
            </div>
            <Button data-testid="player-signup-go-profile" onClick={() => (window.location.href = "/players/me")} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm">
              Go to my profile
            </Button>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
