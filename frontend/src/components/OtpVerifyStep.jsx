import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail, Loader2 } from "lucide-react";

const OTP_TTL_SECONDS = 600;
const RESEND_COOLDOWN_SECONDS = 60;

const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/**
 * Reusable OTP verification step for signup flows.
 * Props:
 *  - email: the email address the OTP was sent to (display only)
 *  - busy: parent's loading flag
 *  - onSubmit(otp): called when the user submits the 6-digit code
 *  - onResend(): called when user hits "Resend code"
 *  - onBack(): called when user clicks "Edit details"
 *  - testidPrefix: prefix for data-testid attributes (e.g. "vendor-signup-otp")
 */
export default function OtpVerifyStep({ email, busy, onSubmit, onResend, onBack, testidPrefix }) {
  const [otp, setOtp] = useState("");
  const [ttl, setTtl] = useState(OTP_TTL_SECONDS);
  const [resendIn, setResendIn] = useState(RESEND_COOLDOWN_SECONDS);

  useEffect(() => {
    const t = setInterval(() => {
      setTtl((s) => Math.max(0, s - 1));
      setResendIn((s) => Math.max(0, s - 1));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  const handleResend = async () => {
    if (resendIn > 0) return;
    const ok = await onResend();
    if (ok) {
      setTtl(OTP_TTL_SECONDS);
      setResendIn(RESEND_COOLDOWN_SECONDS);
      setOtp("");
    }
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (otp.length === 6) onSubmit(otp); }} className="space-y-5">
      <div className="border border-[#84CC16]/30 rounded-sm bg-[#84CC16]/5 p-5 flex items-start gap-3" data-testid={`${testidPrefix}-banner`}>
        <Mail className="w-5 h-5 text-[#84CC16] shrink-0 mt-0.5" />
        <div className="text-sm">
          <p>We&apos;ve emailed a 6-digit code to</p>
          <p className="font-mono text-[#84CC16] mt-1">{email}</p>
          <p className="text-xs text-neutral-400 mt-2">
            Code expires in <span className="text-white font-mono">{fmt(ttl)}</span>. Check your inbox (and spam folder).
          </p>
        </div>
      </div>

      <div>
        <Label className="text-xs font-mono uppercase text-neutral-500">Verification code</Label>
        <Input
          data-testid={`${testidPrefix}-input`}
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
        <Button type="button" variant="ghost" onClick={onBack} className="flex-1 text-neutral-400" data-testid={`${testidPrefix}-back`}>
          ← Edit details
        </Button>
        <Button type="button" variant="ghost" onClick={handleResend} disabled={resendIn > 0 || busy} className="flex-1 text-[#84CC16]" data-testid={`${testidPrefix}-resend`}>
          {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
        </Button>
      </div>

      <Button
        type="submit"
        disabled={busy || ttl === 0 || otp.length !== 6}
        className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm"
        data-testid={`${testidPrefix}-submit`}
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify & create account"}
      </Button>
      {ttl === 0 && <p className="text-xs text-red-400 text-center">Code expired. Please resend.</p>}
    </form>
  );
}
