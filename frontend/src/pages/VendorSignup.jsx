import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

const VENDOR_TYPES = [
  { v: "ground", l: "Cricket / Football Ground" },
  { v: "court", l: "Badminton / Tennis Court" },
  { v: "coach", l: "Coach" },
  { v: "referee", l: "Referee" },
  { v: "umpire", l: "Umpire" },
  { v: "trainer", l: "Trainer" },
  { v: "photographer", l: "Photographer" },
  { v: "videographer", l: "Videographer" },
];

export default function VendorSignup() {
  const nav = useNavigate();
  const [form, setForm] = useState({ business_name: "", vendor_type: "ground", contact_name: "", mobile: "", email: "", password: "", city: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/vendors/signup", form);
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
          List your ground, court or services on PlaySphere. Companies discover and book you — your contact details stay private until you confirm.
        </p>
        <form onSubmit={submit} className="mt-10 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Business name *</Label>
              <Input data-testid="vendor-signup-business" required value={form.business_name} onChange={(e) => setForm({ ...form, business_name: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Vendor type</Label>
              <Select value={form.vendor_type} onValueChange={(v) => setForm({ ...form, vendor_type: v })}>
                <SelectTrigger data-testid="vendor-signup-type" className="mt-2 bg-[#141414] border-white/10 text-white"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  {VENDOR_TYPES.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}
                </SelectContent>
              </Select>
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
              <Label className="text-xs font-mono uppercase text-neutral-500">Email *</Label>
              <Input data-testid="vendor-signup-email" required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
            </div>
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Password *</Label>
            <Input data-testid="vendor-signup-password" required minLength={6} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-2 bg-[#141414] border-white/10 text-white" />
          </div>
          <Button data-testid="vendor-signup-submit" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm">
            {busy ? "Creating..." : "Create vendor account"}
          </Button>
          <p className="text-xs text-neutral-500 text-center">
            Already onboarded? <Link to="/login" className="text-[#84CC16] hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
      <Footer />
    </div>
  );
}
