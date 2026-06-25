import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { ShieldCheck, Mail, Loader2 } from "lucide-react";

const OTP_TTL_SECONDS = 600;
const RESEND_COOLDOWN_SECONDS = 60;

export default function SignupCompany() {
  const { signupCompany } = useAuth();
  const nav = useNavigate();

  const [form, setForm] = useState({
    company_name: "",
    admin_name: "",
    admin_email: "",
    admin_password: "",
    contact_phone: "",
    address_line: "",
    area: "",
    city: "",
    state: "",
    pincode: "",
  });
  const [step, setStep] = useState("details"); // details → verify
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [otpTtl, setOtpTtl] = useState(0);
  const [resendIn, setResendIn] = useState(0);

  // Countdown timers
  useEffect(() => {
    if (step !== "verify") return;
    const t = setInterval(() => {
      setOtpTtl((s) => Math.max(0, s - 1));
      setResendIn((s) => Math.max(0, s - 1));
    }, 1000);
    return () => clearInterval(t);
  }, [step]);

  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  const requestOtp = async () => {
    if (!form.admin_email.trim() || !form.company_name.trim()) {
      return toast.error("Please fill in your company name and work email first");
    }
    if (form.admin_password.length < 6) {
      return toast.error("Password must be at least 6 characters");
    }
    setBusy(true);
    try {
      await api.post("/companies/signup/request-otp", {
        admin_email: form.admin_email.trim().toLowerCase(),
        company_name: form.company_name.trim(),
      });
      toast.success(`Verification code sent to ${form.admin_email}`);
      setStep("verify");
      setOtpTtl(OTP_TTL_SECONDS);
      setResendIn(RESEND_COOLDOWN_SECONDS);
      setOtp("");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not send verification code");
    } finally {
      setBusy(false);
    }
  };

  const resendOtp = async () => {
    if (resendIn > 0) return;
    setBusy(true);
    try {
      await api.post("/companies/signup/request-otp", {
        admin_email: form.admin_email.trim().toLowerCase(),
        company_name: form.company_name.trim(),
      });
      toast.success("New verification code sent");
      setOtpTtl(OTP_TTL_SECONDS);
      setResendIn(RESEND_COOLDOWN_SECONDS);
      setOtp("");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not resend code");
    } finally {
      setBusy(false);
    }
  };

  const completeSignup = async (e) => {
    e.preventDefault();
    if (otp.trim().length !== 6) return toast.error("Enter the 6-digit verification code");
    setBusy(true);
    const r = await signupCompany({ ...form, otp: otp.trim() });
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
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ For HR teams</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">ONBOARD YOUR COMPANY</h1>
        <p className="text-neutral-400 mt-3 text-sm">
          Spin up your own private Kreeda Nation — run internal tournaments, hire services, and bring your teams together. Free to start.
        </p>

        {/* Step indicator */}
        <div className="flex items-center gap-3 mt-8 text-xs font-mono uppercase tracking-widest">
          <span className={step === "details" ? "text-[#84CC16]" : "text-neutral-500"}>① Details</span>
          <span className="text-neutral-700">/</span>
          <span className={step === "verify" ? "text-[#84CC16]" : "text-neutral-500"}>② Verify email</span>
        </div>

        {step === "details" && (
          <form
            onSubmit={(e) => { e.preventDefault(); requestOtp(); }}
            className="mt-8 space-y-4"
          >
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Company name</Label>
              <Input
                data-testid="signup-company-name"
                required
                value={form.company_name}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                className="mt-2 bg-[#141414] border-white/10 text-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Admin name</Label>
                <Input
                  data-testid="signup-admin-name"
                  required
                  value={form.admin_name}
                  onChange={(e) => setForm({ ...form, admin_name: e.target.value })}
                  className="mt-2 bg-[#141414] border-white/10 text-white"
                />
              </div>
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Phone</Label>
                <Input
                  data-testid="signup-phone"
                  value={form.contact_phone}
                  onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
                  className="mt-2 bg-[#141414] border-white/10 text-white"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Work email</Label>
              <Input
                data-testid="signup-email"
                type="email"
                required
                value={form.admin_email}
                onChange={(e) => setForm({ ...form, admin_email: e.target.value })}
                placeholder="you@your-company.com"
                className="mt-2 bg-[#141414] border-white/10 text-white"
              />
              <p className="text-[11px] text-neutral-500 mt-1.5 flex items-center gap-1.5">
                <ShieldCheck className="w-3 h-3 text-[#84CC16]" /> Use your official company email — Gmail, Yahoo, Outlook etc. aren&apos;t supported.
              </p>
            </div>
            {/* Company address — used to surface nearby verified venues when this
                HR creates events. Optional but encouraged. */}
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Company address (optional)</Label>
              <Input
                data-testid="signup-address-line"
                value={form.address_line}
                onChange={(e) => setForm({ ...form, address_line: e.target.value })}
                placeholder="Building / street"
                className="mt-2 bg-[#141414] border-white/10 text-white"
              />
              <div className="grid grid-cols-2 gap-3 mt-2">
                <Input
                  data-testid="signup-area"
                  value={form.area}
                  onChange={(e) => setForm({ ...form, area: e.target.value })}
                  placeholder="Area (e.g. Kharadi)"
                  className="bg-[#141414] border-white/10 text-white"
                />
                <Input
                  data-testid="signup-city"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  placeholder="City (e.g. Pune)"
                  className="bg-[#141414] border-white/10 text-white"
                />
                <Input
                  data-testid="signup-state"
                  value={form.state}
                  onChange={(e) => setForm({ ...form, state: e.target.value })}
                  placeholder="State"
                  className="bg-[#141414] border-white/10 text-white"
                />
                <Input
                  data-testid="signup-pincode"
                  value={form.pincode}
                  onChange={(e) => setForm({ ...form, pincode: e.target.value })}
                  placeholder="Pincode"
                  className="bg-[#141414] border-white/10 text-white"
                />
              </div>
              <p className="text-[11px] text-neutral-500 mt-1.5">
                Helps us suggest nearby verified venues when you create tournaments. You can update this later from your dashboard.
              </p>
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Password</Label>
              <Input
                data-testid="signup-password"
                type="password"
                required
                minLength={6}
                value={form.admin_password}
                onChange={(e) => setForm({ ...form, admin_password: e.target.value })}
                className="mt-2 bg-[#141414] border-white/10 text-white"
              />
            </div>
            <Button
              data-testid="signup-request-otp"
              type="submit"
              disabled={busy}
              className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Send verification code"}
            </Button>
            <p className="text-xs text-neutral-500 text-center">
              Already have an account? <Link to="/login" className="text-[#84CC16] hover:underline">Sign in</Link>
            </p>
          </form>
        )}

        {step === "verify" && (
          <form onSubmit={completeSignup} className="mt-8 space-y-5">
            <div className="border border-[#84CC16]/30 rounded-sm bg-[#84CC16]/5 p-5 flex items-start gap-3" data-testid="signup-otp-banner">
              <Mail className="w-5 h-5 text-[#84CC16] shrink-0 mt-0.5" />
              <div className="text-sm">
                <p>We&apos;ve emailed a 6-digit code to</p>
                <p className="font-mono text-[#84CC16] mt-1">{form.admin_email}</p>
                <p className="text-xs text-neutral-400 mt-2">
                  Code expires in <span className="text-white font-mono">{fmt(otpTtl)}</span>. Check your inbox (and spam folder).
                </p>
              </div>
            </div>

            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Verification code</Label>
              <Input
                data-testid="signup-otp-input"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                autoFocus
                required
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="000000"
                className="mt-2 bg-[#141414] border-white/10 text-white text-center text-3xl tracking-[0.5em] font-mono h-16"
              />
            </div>

            <div className="flex gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setStep("details")}
                className="flex-1 text-neutral-400"
                data-testid="signup-otp-back"
              >
                ← Edit details
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={resendOtp}
                disabled={resendIn > 0 || busy}
                className="flex-1 text-[#84CC16]"
                data-testid="signup-otp-resend"
              >
                {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
              </Button>
            </div>

            <Button
              type="submit"
              disabled={busy || otpTtl === 0}
              className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm"
              data-testid="signup-otp-submit"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify & create company"}
            </Button>
            {otpTtl === 0 && (
              <p className="text-xs text-red-400 text-center">Code expired. Please resend.</p>
            )}
          </form>
        )}
      </div>
      <Footer />
    </div>
  );
}
