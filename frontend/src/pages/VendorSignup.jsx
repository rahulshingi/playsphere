import { useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import OtpVerifyStep from "@/components/OtpVerifyStep";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

const VENDOR_TYPES = [
  { v: "ground", l: "Cricket / Football Ground" },
  { v: "court", l: "Badminton / Tennis Court" },
  { v: "gym", l: "Gym" },
  { v: "studio", l: "Yoga / Dance Studio" },
  { v: "coach", l: "Coach" },
  { v: "referee", l: "Referee" },
  { v: "umpire", l: "Umpire" },
  { v: "trainer", l: "Trainer" },
  { v: "photographer", l: "Photographer" },
  { v: "videographer", l: "Videographer" },
];

export default function VendorSignup() {
  const [form, setForm] = useState({ business_name: "", vendor_type: "ground", vendor_types: ["ground"], contact_name: "", mobile: "", email: "", password: "", city: "" });
  const [step, setStep] = useState("details");
  const [busy, setBusy] = useState(false);

  const toggleType = (v) => {
    const cur = form.vendor_types || [];
    const next = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v];
    // primary type is the first selected, falls back to existing
    setForm({ ...form, vendor_types: next, vendor_type: next[0] || form.vendor_type });
  };

  const requestOtp = async () => {
    if (form.password.length < 6) return toast.error("Password must be at least 6 characters");
    if (!(form.vendor_types && form.vendor_types.length)) return toast.error("Pick at least one vendor type");
    setBusy(true);
    try {
      await api.post("/vendors/signup/request-otp", {
        email: form.email.trim().toLowerCase(),
        business_name: form.business_name.trim(),
      });
      toast.success(`Verification code sent to ${form.email}`);
      setStep("verify");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Could not send verification code");
    } finally { setBusy(false); }
  };

  const resendOtp = async () => {
    try {
      await api.post("/vendors/signup/request-otp", {
        email: form.email.trim().toLowerCase(),
        business_name: form.business_name.trim(),
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
      await api.post("/vendors/signup", { ...form, email: form.email.trim().toLowerCase(), otp });
      toast.success("Vendor account created — pending platform approval");
      window.location.href = "/vendor/dashboard";
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Sign up failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#EC4899]">/ Service partners</div>
        <h1 className="font-display text-5xl tracking-wide mt-2">JOIN AS A VENDOR</h1>
        <p className="text-neutral-400 mt-3 text-sm">
          List your ground, court or services on Kreeda Nation. Companies discover and book you — your contact details stay private until you confirm.
        </p>

        <div className="flex items-center gap-3 mt-8 text-xs font-mono uppercase tracking-widest">
          <span className={step === "details" ? "text-[#EC4899]" : "text-neutral-500"}>① Details</span>
          <span className="text-neutral-700">/</span>
          <span className={step === "verify" ? "text-[#EC4899]" : "text-neutral-500"}>② Verify email</span>
        </div>

        {step === "details" && (
          <form onSubmit={(e) => { e.preventDefault(); requestOtp(); }} className="mt-8 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Business name *</Label>
                <Input data-testid="vendor-signup-business" required value={form.business_name} onChange={(e) => setForm({ ...form, business_name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Vendor types (multi-select) *</Label>
                <div data-testid="vendor-signup-types" className="mt-2 flex flex-wrap gap-1.5">
                  {VENDOR_TYPES.map((t) => {
                    const on = (form.vendor_types || []).includes(t.v);
                    return (
                      <button key={t.v} type="button" data-testid={`vendor-signup-type-${t.v}`} onClick={() => toggleType(t.v)}
                        className={`text-[10px] font-mono uppercase px-2 py-1 rounded-sm border transition-colors ${
                          on ? "bg-[#EC4899] text-black border-transparent" : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
                        }`}>{t.l}</button>
                    );
                  })}
                </div>
              </div>
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Contact name *</Label>
                <Input data-testid="vendor-signup-contact" required value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">City *</Label>
                <Input data-testid="vendor-signup-city" required value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Mobile *</Label>
                <Input data-testid="vendor-signup-mobile" required value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-xs font-mono uppercase text-neutral-500">Business email *</Label>
                <Input data-testid="vendor-signup-email" required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
              </div>
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Password *</Label>
              <Input data-testid="vendor-signup-password" required minLength={6} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <Button type="submit" data-testid="vendor-signup-request-otp" disabled={busy} className="w-full bg-[#EC4899] hover:bg-[#DB2777] text-black font-semibold h-12 rounded-sm">
              {busy ? "Sending code..." : "Send verification code"}
            </Button>
            <p className="text-xs text-neutral-500 text-center">
              Already onboarded? <Link to="/login" className="text-[#EC4899] hover:underline">Sign in</Link>
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
              testidPrefix="vendor-signup-otp"
            />
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
