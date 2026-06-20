import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Trash2 } from "lucide-react";
import { CURRENCIES } from "@/lib/currency";
import ImageUpload from "@/components/ImageUpload";

const CATEGORIES = ["streaming", "apparel", "merchandise", "awards", "venue", "equipment", "training", "other"];
const FIELD_TYPES = ["number", "text", "textarea", "select"];

function Field({ label, children }) {
  return (
    <div>
      <Label className="text-xs font-mono uppercase text-neutral-500">{label}</Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

export default function ServiceEditor({ service, setService, onSave, onClose }) {
  const upd = (patch) => setService({ ...service, ...patch });
  const addField = () => upd({ config_fields: [...(service.config_fields || []), { key: "", label: "", type: "number", required: false }] });
  const updField = (i, patch) => { const next = [...service.config_fields]; next[i] = { ...next[i], ...patch }; upd({ config_fields: next }); };
  const delField = (i) => upd({ config_fields: service.config_fields.filter((_, idx) => idx !== i) });
  const addVariant = () => upd({ variants: [...(service.variants || []), { id: `v-${Date.now()}`, name: "", image_url: "", extra_price: 0 }] });
  const updVariant = (i, patch) => { const next = [...service.variants]; next[i] = { ...next[i], ...patch }; upd({ variants: next }); };
  const delVariant = (i) => upd({ variants: service.variants.filter((_, idx) => idx !== i) });

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-start justify-center overflow-auto p-6">
      <div className="bg-[#0c0c0c] border border-white/10 rounded-sm w-full max-w-3xl my-10 p-6 space-y-4 text-white">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-mono text-[10px] uppercase text-[#84CC16] tracking-widest">/ {service.id ? "Edit" : "New"} service</div>
            <h2 className="font-display text-3xl tracking-wider">{service.id ? service.name.toUpperCase() : "NEW SERVICE"}</h2>
          </div>
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Close</Button>
        </div>

        <div className="grid md:grid-cols-2 gap-3">
          <Field label="Name *"><Input data-testid="svc-name" value={service.name} onChange={(e) => upd({ name: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
          <Field label="Category">
            <Select value={service.category} onValueChange={(v) => upd({ category: v })}>
              <SelectTrigger data-testid="svc-category" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Currency">
            <Select value={service.currency || "USD"} onValueChange={(v) => upd({ currency: v })}>
              <SelectTrigger data-testid="svc-currency" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {CURRENCIES.map((c) => <SelectItem key={c.code} value={c.code}>{c.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field label={`Base price (${service.currency || "USD"})`}><Input data-testid="svc-price" type="number" min={0} value={service.base_price} onChange={(e) => upd({ base_price: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
          <Field label="Price unit"><Input data-testid="svc-unit" value={service.price_unit} onChange={(e) => upd({ price_unit: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
        </div>
        <Field label="Description"><Textarea data-testid="svc-desc" value={service.description} onChange={(e) => upd({ description: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
        <Field label="Main image">
          <ImageUpload value={service.images?.[0] || ""} onChange={(v) => upd({ images: [v] })} testid="svc-image" placeholder="https://… or upload image" />
        </Field>

        <div className="flex items-center gap-3">
          <input id="svc-allow-text" type="checkbox" checked={!!service.allow_custom_text} onChange={(e) => upd({ allow_custom_text: e.target.checked })} className="accent-[#84CC16]" />
          <label htmlFor="svc-allow-text" className="text-sm">Allow custom text input (e.g., trophy inscription)</label>
        </div>
        {service.allow_custom_text && (
          <Field label="Custom text label">
            <Input value={service.custom_text_label || ""} onChange={(e) => upd({ custom_text_label: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          </Field>
        )}

        <div className="flex items-center gap-3">
          <input id="svc-active" type="checkbox" checked={!!service.active} onChange={(e) => upd({ active: e.target.checked })} className="accent-[#84CC16]" />
          <label htmlFor="svc-active" className="text-sm">Active (visible in marketplace)</label>
        </div>

        <div className="border border-white/10 rounded-sm p-4">
          <div className="flex items-center justify-between">
            <div className="font-mono text-[10px] uppercase text-neutral-500">/ Form fields shown to HR</div>
            <Button size="sm" variant="ghost" onClick={addField} className="text-[#84CC16]" data-testid="svc-add-field">+ Add field</Button>
          </div>
          <div className="space-y-2 mt-3">
            {(service.config_fields || []).map((f, i) => (
              <div key={`field-${f.key || "new"}-${i}`} className="grid grid-cols-12 gap-2 items-center">
                <Input placeholder="key" value={f.key} onChange={(e) => updField(i, { key: e.target.value })} className="col-span-3 bg-black/40 border-white/10 text-white" />
                <Input placeholder="Label" value={f.label} onChange={(e) => updField(i, { label: e.target.value })} className="col-span-4 bg-black/40 border-white/10 text-white" />
                <Select value={f.type} onValueChange={(v) => updField(i, { type: v })}>
                  <SelectTrigger className="col-span-2 bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    {FIELD_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Input placeholder={f.type === "select" ? "opt1,opt2" : "default"} value={f.type === "select" ? (f.options || []).join(",") : (f.default || "")} onChange={(e) => updField(i, f.type === "select" ? { options: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) } : { default: e.target.value })} className="col-span-2 bg-black/40 border-white/10 text-white" />
                <Button size="sm" variant="ghost" onClick={() => delField(i)} className="col-span-1 text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
              </div>
            ))}
          </div>
        </div>

        <div className="border border-white/10 rounded-sm p-4">
          <div className="flex items-center justify-between">
            <div className="font-mono text-[10px] uppercase text-neutral-500">/ Variants (e.g., trophy designs)</div>
            <Button size="sm" variant="ghost" onClick={addVariant} className="text-[#84CC16]" data-testid="svc-add-variant">+ Add variant</Button>
          </div>
          <div className="space-y-2 mt-3">
            {(service.variants || []).map((v, i) => (
              <div key={`variant-${v.name || "new"}-${i}`} className="grid grid-cols-12 gap-2 items-center">
                <Input placeholder="Name" value={v.name} onChange={(e) => updVariant(i, { name: e.target.value })} className="col-span-3 bg-black/40 border-white/10 text-white" />
                <Input placeholder="Image URL" value={v.image_url} onChange={(e) => updVariant(i, { image_url: e.target.value })} className="col-span-6 bg-black/40 border-white/10 text-white" />
                <Input placeholder="±price" type="number" value={v.extra_price} onChange={(e) => updVariant(i, { extra_price: Number(e.target.value) || 0 })} className="col-span-2 bg-black/40 border-white/10 text-white" />
                <Button size="sm" variant="ghost" onClick={() => delVariant(i)} className="col-span-1 text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Cancel</Button>
          <Button data-testid="svc-save" onClick={onSave} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save service</Button>
        </div>
      </div>
    </div>
  );
}
