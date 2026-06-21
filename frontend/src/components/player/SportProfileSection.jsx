import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SPORT_SCHEMAS } from "@/lib/sportProfileSchema";
import { X } from "lucide-react";

function Field({ label, children }) {
  return (
    <div className="mt-3">
      <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</Label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}

function SportField({ sport, field, value, onChange }) {
  const testid = `sp-${sport}-${field.key}`;
  if (field.type === "select") {
    return (
      <Select value={value || field.default || field.options[0]} onValueChange={onChange}>
        <SelectTrigger data-testid={testid} className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
        <SelectContent className="bg-[#141414] text-white border-white/10">
          {field.options.map((o) => <SelectItem key={o} value={o}>{o.replace(/-/g, " ")}</SelectItem>)}
        </SelectContent>
      </Select>
    );
  }
  if (field.type === "number") {
    return <Input data-testid={testid} type="number" value={value ?? ""} placeholder={field.placeholder} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))} className="bg-black/40 border-white/10 text-white" />;
  }
  if (field.type === "textarea") {
    return <Textarea data-testid={testid} rows={2} value={value || ""} placeholder={field.placeholder} onChange={(e) => onChange(e.target.value)} className="bg-black/40 border-white/10 text-white" />;
  }
  return <Input data-testid={testid} value={value || ""} placeholder={field.placeholder} onChange={(e) => onChange(e.target.value)} className="bg-black/40 border-white/10 text-white" />;
}

/**
 * Renders the editable form for one sport: a header + each schema field.
 */
export default function SportProfileSection({ sport, sportProfile, onChange, onRemove }) {
  const schema = SPORT_SCHEMAS[sport];
  if (!schema) return null;
  const setField = (key, val) => onChange({ ...sportProfile, [key]: val });
  return (
    <div data-testid={`sport-section-${sport}`} className="border border-white/10 rounded-sm bg-black/30 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: schema.color }} />
          <div className="font-display tracking-wider text-xl">{schema.label.toUpperCase()}</div>
        </div>
        <button data-testid={`sport-remove-${sport}`} onClick={onRemove}
          className="text-[10px] font-mono uppercase text-neutral-500 hover:text-[#FF3B30] flex items-center gap-1">
          <X className="w-3 h-3" /> remove
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 mt-3">
        {schema.fields.map((f) => (
          <Field key={f.key} label={f.label}>
            <SportField sport={sport} field={f} value={sportProfile[f.key]} onChange={(v) => setField(f.key, v)} />
          </Field>
        ))}
      </div>
    </div>
  );
}
