import { SPORT_SCHEMAS, SPORT_KEYS } from "@/lib/sportProfileSchema";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

const ROLE_KEYS = ["role", "position", "specialty", "domain"];
const HAND_KEYS = ["batting_hand", "preferred_foot", "shooting_hand", "hand", "preferred_color"];

/** Derive role + hand options from the chosen sport's schema. */
function deriveOptions(sport) {
  const schema = SPORT_SCHEMAS[sport];
  if (!schema) return { roleField: null, handField: null };
  const roleField = schema.fields.find((f) => ROLE_KEYS.includes(f.key)) || null;
  const handField = schema.fields.find((f) => HAND_KEYS.includes(f.key)) || null;
  return { roleField, handField };
}

export default function PlayerFilters({ filters, setFilters, onSearch }) {
  const { sport, role, hand, q, city } = filters;
  const { roleField, handField } = deriveOptions(sport);

  const update = (patch) => setFilters({ ...filters, ...patch });
  const onSportChange = (v) => update({ sport: v === "__any__" ? "" : v, role: "", hand: "" });
  const clear = () => setFilters({ q: "", sport: "", role: "", hand: "", city: "" });
  const hasActive = sport || role || hand || q || city;

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSearch(); }} className="mt-8 border border-white/10 rounded-sm bg-[#141414] p-4">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
        <Input data-testid="player-search-q" value={q} onChange={(e) => update({ q: e.target.value })}
          placeholder="Name / mobile" className="bg-black/40 border-white/10 text-white text-sm" />
        <Input data-testid="player-search-city" value={city} onChange={(e) => update({ city: e.target.value })}
          placeholder="City" className="bg-black/40 border-white/10 text-white text-sm" />
        <Select value={sport || "__any__"} onValueChange={onSportChange}>
          <SelectTrigger data-testid="player-search-sport" className="bg-black/40 border-white/10 text-white text-sm"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            <SelectItem value="__any__">Any sport</SelectItem>
            {SPORT_KEYS.map((s) => <SelectItem key={s} value={s}>{SPORT_SCHEMAS[s].label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={role || "__any__"} onValueChange={(v) => update({ role: v === "__any__" ? "" : v })} disabled={!roleField}>
          <SelectTrigger data-testid="player-search-role" className="bg-black/40 border-white/10 text-white text-sm">
            <SelectValue placeholder={roleField ? `Any ${roleField.label.toLowerCase()}` : "Role (pick sport)"} />
          </SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            <SelectItem value="__any__">{roleField ? `Any ${roleField.label.toLowerCase()}` : "Any role"}</SelectItem>
            {roleField?.options?.map((o) => <SelectItem key={o} value={o}>{o.replace(/-/g, " ")}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={hand || "__any__"} onValueChange={(v) => update({ hand: v === "__any__" ? "" : v })} disabled={!handField}>
          <SelectTrigger data-testid="player-search-hand" className="bg-black/40 border-white/10 text-white text-sm">
            <SelectValue placeholder={handField ? `Any ${handField.label.toLowerCase()}` : "Style (pick sport)"} />
          </SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            <SelectItem value="__any__">{handField ? `Any ${handField.label.toLowerCase()}` : "Any"}</SelectItem>
            {handField?.options?.map((o) => <SelectItem key={o} value={o}>{o.replace(/-/g, " ")}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-2 mt-3">
        <Button type="submit" data-testid="player-search-btn"
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Search</Button>
        {hasActive && (
          <Button type="button" variant="ghost" onClick={clear} data-testid="player-search-clear"
            className="text-neutral-400 hover:text-white">
            <X className="w-4 h-4 mr-1" /> Clear filters
          </Button>
        )}
        <span className="ml-auto text-[10px] font-mono uppercase tracking-widest text-neutral-500">
          {sport ? `/ filtering by ${SPORT_SCHEMAS[sport]?.label}` : "/ any sport"}
        </span>
      </div>
    </form>
  );
}
