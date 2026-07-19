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

      <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3 mt-6">
        <div className="font-display tracking-wider text-2xl">ORGANISER EVENT INSTRUCTIONS</div>
        <p className="text-xs text-neutral-500 font-mono">
          Shown to organisers when they create a new event. They must acknowledge before the event
          is queued for your approval. Plain text or basic HTML (e.g. &lt;b&gt;, &lt;ul&gt;&lt;li&gt;).
        </p>
        <Textarea
          data-testid="setting-organiser_event_instructions"
          rows={10}
          value={settings.organiser_event_instructions || ""}
          onChange={(e) => setSettings({ ...settings, organiser_event_instructions: e.target.value })}
          placeholder="Outline your tournament policies, fair-play rules, sponsorship terms…"
          className="mt-2 bg-black/40 border-white/10 text-white font-mono text-xs leading-relaxed"
        />
        <Button data-testid="organiser-instructions-save" onClick={save}
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
          Save instructions
        </Button>
      </div>

      <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3 mt-6">
        <div className="font-display tracking-wider text-2xl">ORGANISER EVENT FEE</div>
        <p className="text-xs text-neutral-500 font-mono">
          One-time platform charge every organiser pays when submitting an event for approval.
          Set to <b>0</b> to make submissions free — the payment picker won&apos;t be shown.
        </p>
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <div className="text-[10px] font-mono uppercase text-neutral-500">Amount</div>
            <Input
              data-testid="setting-organiser_event_fee"
              type="number" min="0" step="0.01"
              value={settings.organiser_event_fee ?? 0}
              onChange={(e) => setSettings({ ...settings, organiser_event_fee: Number(e.target.value) })}
              className="mt-1 bg-black/40 border-white/10 text-white font-mono"
            />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase text-neutral-500">Currency</div>
            <Input
              data-testid="setting-organiser_event_fee_currency"
              value={settings.organiser_event_fee_currency || "INR"}
              onChange={(e) => setSettings({ ...settings, organiser_event_fee_currency: e.target.value.toUpperCase() })}
              className="mt-1 bg-black/40 border-white/10 text-white font-mono uppercase"
            />
          </div>
        </div>
        <Button data-testid="organiser-fee-save" onClick={save}
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
          Save event fee
        </Button>
      </div>

      <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3 mt-6">
        <div className="font-display tracking-wider text-2xl">MOBILE APPS</div>
        <p className="text-xs text-neutral-500 font-mono">
          Public store URLs shown as footer badges. Leave blank and the badge shows a
          disabled &ldquo;Stay tuned &mdash; launching soon&rdquo; state. Fill either one
          the moment its build goes live &mdash; no redeploy required.
        </p>
        <div>
          <Label className="text-xs font-mono uppercase text-neutral-500">iOS &mdash; App Store URL</Label>
          <Input
            data-testid="setting-ios_app_url"
            value={settings.ios_app_url || ""}
            onChange={(e) => setSettings({ ...settings, ios_app_url: e.target.value })}
            placeholder="https://apps.apple.com/app/id..."
            className="mt-2 bg-black/40 border-white/10 text-white"
          />
        </div>
        <div>
          <Label className="text-xs font-mono uppercase text-neutral-500">Android &mdash; Google Play URL</Label>
          <Input
            data-testid="setting-android_app_url"
            value={settings.android_app_url || ""}
            onChange={(e) => setSettings({ ...settings, android_app_url: e.target.value })}
            placeholder="https://play.google.com/store/apps/details?id=..."
            className="mt-2 bg-black/40 border-white/10 text-white"
          />
        </div>
        <Button data-testid="app-links-save" onClick={save}
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
          Save app links
        </Button>
      </div>

      <ContactInbox />
    </>
  );
}
