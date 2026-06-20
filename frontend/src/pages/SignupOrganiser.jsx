import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import OtpVerifyStep from "@/components/OtpVerifyStep";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Trophy } from "lucide-react";

export default function SignupOrganiser() {
  const { signupOrganiser } = useAuth();
  const nav = useNavigate();

  const [form, setForm] = useState({
    company_name: "",
    admin_name: "",
    admin_email: "",
    admin_password: "",
    contact_phone: "",
  });
  const [step, setStep] = useState("details");
  const [busy, setBusy] = useState(false);

  const requestOtp = async () => {
    if (!form.admin_email.trim() || !form.company_name.trim()) {
      return toast.error("Please enter your organiser name and email first");
    }
    if (form.admin_password.length < 6) return toast.error("Password must be at least 6 characters");
    setBusy(true);
    try {
      await api.post("/organisers/signup/request-otp", {
        admin_email: form.admin_email.trim().toLowerCase(),
        organiser_name: form.company_name.trim(),
      });
      toast.success(`Verification code sent to ${form.admin_email}`);
      setStep("verify");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not send code");
    } finally { setBusy(false); }
  };

  const resendOtp = async () => {
    try {
      await api.post("/organisers/signup/request-otp", {
        admin_email: form.admin_email.trim().toLowerCase(),
        organiser_name: form.company_name.trim(),
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
    const r = await signupOrganiser({ ...form, admin_email: form.admin_email.trim().toLowerCase(), otp });
    setBusy(false);
    if (r.ok) {
      toast.success(`Welcome, ${r.user.company_name}!`);
      nav("/dashboard");
    } else {
      toast.error(r.error);
    }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ For tournament organisers</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">JOIN AS AN ORGANISER</h1>
        <p className="text-neutral-400 mt-3 text-sm">
          Run open tournaments, book grounds, hire vendors, manage fixtures and live-score — all from one Kreeda Nation workspace. No company required.
        </p>

        <div className="flex items-center gap-3 mt-8 text-xs font-mono uppercase tracking-widest">
          <span className={step === "details" ? "text-[#06B6D4]" : "text-neutral-500"}>① Details</span>
          <span className="text-neutral-700">/</span>
          <span className={step === "verify" ? "text-[#06B6D4]" : "text-neutral-500"}>② Verify email</span>
        </div>

        {step === "details" && (
          <form onSubmit={(e) => { e.preventDefault(); requestOtp(); }} className="mt-8 space-y-4">
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Organiser / brand name</Label>
              <Input data-testid="org-signup-name" required value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Your name</Label>
                <Input data-testid="org-signup-admin-name" required value={form.admin_name} onChange={(e) => setForm({ ...form, admin_name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Phone</Label>
                <Input data-testid="org-signup-phone" value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
              </div>
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Email</Label>
              <Input data-testid="org-signup-email" type="email" required value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} placeholder="you@example.com" className="mt-2 bg-[#141414] border-white/10 text-white" />
              <p className="text-[11px] text-neutral-500 mt-1.5 flex items-center gap-1.5">
                <Trophy className="w-3 h-3 text-[#06B6D4]" /> Any email works — Gmail, Yahoo and custom domains are all fine.
              </p>
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
              <Input data-testid="org-signup-password" type="password" required minLength={6} value={form.admin_password} onChange={(e) => setForm({ ...form, admin_password: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <Button type="submit" data-testid="org-signup-request-otp" disabled={busy} className="w-full bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold h-12 rounded-sm">
              {busy ? "Sending code..." : "Send verification code"}
            </Button>
            <p className="text-xs text-neutral-500 text-center">
              Already onboarded? <Link to="/login" className="text-[#06B6D4] hover:underline">Sign in</Link>
            </p>
          </form>
        )}

        {step === "verify" && (
          <div className="mt-8">
            <OtpVerifyStep
              email={form.admin_email}
              busy={busy}
              onSubmit={completeSignup}
              onResend={resendOtp}
              onBack={() => setStep("details")}
              testidPrefix="org-signup-otp"
            />
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
