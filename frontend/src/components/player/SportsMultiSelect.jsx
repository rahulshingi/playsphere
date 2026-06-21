import { SPORT_SCHEMAS, SPORT_KEYS } from "@/lib/sportProfileSchema";
import { Check, Plus } from "lucide-react";

/**
 * Chip-style multi-select for "interested sports". Clicking a chip toggles it.
 */
export default function SportsMultiSelect({ value, onChange }) {
  const selected = new Set(value || []);
  const toggle = (sport) => {
    if (selected.has(sport)) {
      onChange((value || []).filter((s) => s !== sport));
    } else {
      onChange([...(value || []), sport]);
    }
  };
  return (
    <div className="flex flex-wrap gap-2" data-testid="interested-sports-picker">
      {SPORT_KEYS.map((s) => {
        const isOn = selected.has(s);
        const schema = SPORT_SCHEMAS[s];
        return (
          <button
            key={s}
            type="button"
            data-testid={`interested-sport-${s}`}
            onClick={() => toggle(s)}
            className={`px-3 py-1.5 rounded-sm border text-xs font-mono uppercase tracking-widest flex items-center gap-1.5 transition-colors ${
              isOn ? "text-black border-transparent" : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
            }`}
            style={isOn ? { backgroundColor: schema.color } : undefined}
          >
            {isOn ? <Check className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
            {schema.label}
          </button>
        );
      })}
    </div>
  );
}
