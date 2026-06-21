import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { STATS_SCHEMAS } from "@/lib/sportStatsSchema";

/**
 * Editor section for one sport's manual stats. Shown inside the PlayerProfile editor
 * below the per-sport role/style section. Auto-tracked fields (cricket) are NOT editable
 * here — they're computed server-side from completed fixtures.
 */
function StatField({ sport, field, value, onChange }) {
  const testid = `stat-edit-${sport}-${field.key}`;
  if (field.type === "number") {
    return (
      <Input data-testid={testid} type="number" value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="bg-black/40 border-white/10 text-white" />
    );
  }
  return (
    <Input data-testid={testid} value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      className="bg-black/40 border-white/10 text-white" />
  );
}

export default function SportStatsEditor({ sport, manualStats, onChange }) {
  const schema = STATS_SCHEMAS[sport];
  if (!schema || schema.manual.length === 0) return null;
  const set = (key, val) => onChange({ ...(manualStats || {}), [key]: val });

  return (
    <div data-testid={`stats-edit-section-${sport}`} className="border-t border-white/10 mt-4 pt-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ {schema.label} career stats</div>
      {schema.auto.length > 0 && (
        <p className="text-[10px] text-[#84CC16] font-mono mt-1">
          Match stats are auto-tracked from completed Kreeda Nation fixtures. Use the fields below for stats from external tournaments.
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 mt-3">
        {schema.manual.map((f) => (
          <div key={f.key}>
            <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{f.label}</Label>
            <div className="mt-1.5">
              <StatField sport={sport} field={f} value={manualStats?.[f.key]} onChange={(v) => set(f.key, v)} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
