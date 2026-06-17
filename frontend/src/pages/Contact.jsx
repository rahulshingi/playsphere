import { useEffect, useState } from "react";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Mail, Phone, MapPin, Clock } from "lucide-react";

export default function Contact() {
  const [settings, setSettings] = useState(null);
  const [form, setForm] = useState({ name: "", email: "", phone: "", message: "" });
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => setSettings(r.data)).catch(() => setSettings({}));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!(form.name && form.email && form.message)) return toast.error("Name, email and message are required");
    setBusy(true);
    try {
      await api.post("/contact", form);
      toast.success("Message sent — we'll be in touch soon");
      setSent(true);
      setForm({ name: "", email: "", phone: "", message: "" });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to send");
    } finally { setBusy(false); }
  };

  const s = settings || {};
  return (
    <div className="bg-[#0a0a0a] text-white min-h-screen">
      <Nav />
      <div className="max-w-6xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] tracking-[0.3em] text-[#84CC16] uppercase">/ Contact</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">GET IN TOUCH</h1>
        <p className="text-neutral-400 mt-3 max-w-2xl">Have a tournament to plan, a partnership idea, or a press question? We&apos;d love to hear from you.</p>

        <div className="mt-12 grid lg:grid-cols-2 gap-10">
          {/* INFO */}
          <div data-testid="contact-info" className="space-y-5">
            <ContactRow icon={Mail} label="Email" value={s.contact_email || "contact@kreedanation.com"} accent="#84CC16" testid="info-email" />
            <ContactRow icon={Phone} label="Phone" value={s.contact_phone || "—"} accent="#06B6D4" testid="info-phone" />
            <ContactRow icon={MapPin} label="Address" value={s.contact_address || "—"} accent="#EC4899" testid="info-address" />
            <ContactRow icon={Clock} label="Hours" value={s.contact_hours || "Mon–Sat · 09:00 – 19:00 IST"} accent="#F59E0B" testid="info-hours" />
            {s.contact_map_url && (
              <div className="border border-white/10 rounded-sm overflow-hidden mt-4">
                <iframe data-testid="info-map" src={s.contact_map_url} title="Map" className="w-full h-64 border-0" loading="lazy" />
              </div>
            )}
          </div>

          {/* FORM */}
          <form onSubmit={submit} className="border border-white/10 rounded-sm bg-[#141414] p-6 space-y-4">
            <h2 className="font-display text-2xl tracking-wider">SEND US A MESSAGE</h2>
            {sent && <div data-testid="contact-sent" className="text-[#84CC16] text-sm border border-[#84CC16]/30 bg-[#84CC16]/5 rounded-sm px-3 py-2">Thanks! We&apos;ll be in touch.</div>}
            <div>
              <Label className="text-xs uppercase font-mono text-neutral-500">Your name</Label>
              <Input data-testid="contact-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1 bg-black/40 border-white/10 text-white" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs uppercase font-mono text-neutral-500">Email</Label>
                <Input data-testid="contact-email" required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-1 bg-black/40 border-white/10 text-white" />
              </div>
              <div>
                <Label className="text-xs uppercase font-mono text-neutral-500">Phone (optional)</Label>
                <Input data-testid="contact-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="mt-1 bg-black/40 border-white/10 text-white" />
              </div>
            </div>
            <div>
              <Label className="text-xs uppercase font-mono text-neutral-500">Message</Label>
              <Textarea data-testid="contact-message" required rows={6} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className="mt-1 bg-black/40 border-white/10 text-white" placeholder="Tell us about your tournament, partnership idea, or question…" />
            </div>
            <Button data-testid="contact-submit" disabled={busy} className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm">{busy ? "Sending…" : "Send message"}</Button>
            <p className="text-[10px] text-neutral-500">By submitting you agree to be contacted at the email/phone provided. We will not share your details with third parties.</p>
          </form>
        </div>
      </div>
      <Footer />
    </div>
  );
}

function ContactRow({ icon: Icon, label, value, accent, testid }) {
  return (
    <div data-testid={testid} className="flex items-start gap-3 border border-white/10 rounded-sm bg-[#141414] p-4">
      <div className="w-10 h-10 rounded-sm flex items-center justify-center" style={{ background: `${accent}20`, color: accent }}><Icon className="w-4 h-4" /></div>
      <div className="min-w-0 flex-1">
        <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
        <div className="text-sm text-white mt-0.5 break-words whitespace-pre-wrap">{value}</div>
      </div>
    </div>
  );
}
