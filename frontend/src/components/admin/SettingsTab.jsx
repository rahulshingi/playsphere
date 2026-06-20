import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import ContactInbox from "@/components/admin/ContactInbox";

const SOCIAL_KEYS = ["facebook_url", "instagram_url", "linkedin_url", "twitter_url", "youtube_url"];
const CONTACT_FIELDS = [
  { k: "contact_email", label: "Email", placeholder: "contact@kreedanation.com" },
  { k: "contact_phone", label: "Phone", placeholder: "+91 ..." },
  { k: "contact_address", label: "Address", placeholder: "Office address", multiline: true },
  { k: "contact_hours", label: "Hours", placeholder: "Mon–Sat · 09:00 – 19:00 IST" },
  { k: "contact_map_url", label: "Google Maps embed URL", placeholder: "https://www.google.com/maps/embed?…" },
];

export default function SettingsTab({ settings, setSettings, reload }) {
  const save = async () => { await api.patch("/settings", settings); toast.success("Saved"); reload(); };
  return (
    <>
      <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3">
        <div className="font-display tracking-wider text-2xl">SITE SETTINGS</div>
        <p className="text-xs text-neutral-500 font-mono">Social media links shown in footer.</p>
        {SOCIAL_KEYS.map((k) => (
          <div key={k}>
            <Label className="text-xs font-mono uppercase text-neutral-500">{k.replace("_url", "")}</Label>
            <Input data-testid={`setting-${k}`} value={settings[k] || ""} onChange={(e) => setSettings({ ...settings, [k]: e.target.value })} placeholder={`https://${k.split("_")[0]}.com/playsphere`} className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>
        ))}
        <Button data-testid="settings-save" onClick={save} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save settings</Button>
      </div>

      <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3 mt-6">
        <div className="font-display tracking-wider text-2xl">CONTACT DETAILS</div>
        <p className="text-xs text-neutral-500 font-mono">Shown on /contact and used as the default email for contact-form deliveries.</p>
        {CONTACT_FIELDS.map((f) => (
          <div key={f.k}>
            <Label className="text-xs font-mono uppercase text-neutral-500">{f.label}</Label>
            {f.multiline ? (
              <Textarea data-testid={`setting-${f.k}`} rows={2} value={settings[f.k] || ""} onChange={(e) => setSettings({ ...settings, [f.k]: e.target.value })} placeholder={f.placeholder} className="mt-2 bg-black/40 border-white/10 text-white" />
            ) : (
              <Input data-testid={`setting-${f.k}`} value={settings[f.k] || ""} onChange={(e) => setSettings({ ...settings, [f.k]: e.target.value })} placeholder={f.placeholder} className="mt-2 bg-black/40 border-white/10 text-white" />
            )}
          </div>
        ))}
        <Button data-testid="contact-save" onClick={save} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save contact details</Button>
      </div>

      <ContactInbox />
    </>
  );
}
