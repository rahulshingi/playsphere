import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MapPin, Pencil, Save, X } from "lucide-react";

/**
 * Company / Organiser address card for the Dashboard.
 * - View-only until the user clicks Edit.
 * - Save is disabled until something actually changes (dirty tracking).
 * - The stored address powers nearby-venue suggestions in the event-creation picker,
 *   so we lead with that context.
 */
const ADDRESS_FIELDS = [
  { key: "address_line", label: "Building / street", full: true },
  { key: "area", label: "Area (e.g. Kharadi)" },
  { key: "city", label: "City (e.g. Pune)" },
  { key: "state", label: "State" },
  { key: "pincode", label: "Pincode" },
];

function snapshot(obj) {
  return JSON.stringify(ADDRESS_FIELDS.reduce((acc, f) => ({ ...acc, [f.key]: (obj?.[f.key] || "").trim() }), {}));
}

export default function CompanyAddressCard() {
  const [company, setCompany] = useState(null);
  const [draft, setDraft] = useState(null);
  const [original, setOriginal] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.get("/companies/me").then((r) => {
      setCompany(r.data);
      setDraft({ ...r.data });
      setOriginal(snapshot(r.data));
    }).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  if (!company) return null;

  const upd = (k, v) => setDraft({ ...draft, [k]: v });
  const isDirty = snapshot(draft) !== original;
  const isEmpty = ADDRESS_FIELDS.every((f) => !(company[f.key] || "").trim());

  const save = async () => {
    setBusy(true);
    try {
      const payload = ADDRESS_FIELDS.reduce((acc, f) => ({ ...acc, [f.key]: (draft[f.key] || "").trim() }), {});
      const { data } = await api.patch("/companies/me", payload);
      setCompany(data); setDraft({ ...data }); setOriginal(snapshot(data));
      setEditing(false);
      toast.success("Address saved — nearby venues will use this");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally { setBusy(false); }
  };

  const cancel = () => { setDraft({ ...company }); setEditing(false); };

  return (
    <div data-testid="company-address-card" className="border border-white/10 rounded-sm bg-[#141414] p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#06B6D4] flex items-center gap-1.5">
            <MapPin className="w-3 h-3" /> / Your address
          </div>
          <h3 className="font-display text-xl tracking-wide mt-1">WHERE ARE YOU BASED?</h3>
          <p className="text-xs text-neutral-400 mt-1 max-w-xl">
            Used to surface nearby verified venues when you create tournaments.
            {isEmpty && <span className="text-[#FACC15]"> Add it once and forget it.</span>}
          </p>
        </div>
        {!editing && (
          <Button data-testid="company-address-edit" size="sm" onClick={() => setEditing(true)}
            className="bg-white/5 hover:bg-white/10 text-white rounded-sm border border-white/10">
            <Pencil className="w-3.5 h-3.5 mr-1.5" /> {isEmpty ? "Add address" : "Edit"}
          </Button>
        )}
      </div>

      {!editing ? (
        <div className="mt-4">
          {isEmpty ? (
            <p data-testid="company-address-empty" className="text-sm text-neutral-500 italic">No address on file yet — add one to unlock nearby venue suggestions.</p>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3" data-testid="company-address-view">
              {ADDRESS_FIELDS.map((f) => company[f.key] && (
                <div key={f.key} className={f.full ? "sm:col-span-2" : ""}>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{f.label.replace(/\s*\(.*?\)/, "")}</div>
                  <div className="text-neutral-200 text-sm">{company[f.key]}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="mt-4 space-y-2">
          {ADDRESS_FIELDS.filter((f) => f.full).map((f) => (
            <div key={f.key}>
              <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{f.label}</Label>
              <Input data-testid={`company-address-${f.key}`}
                value={draft[f.key] || ""}
                onChange={(e) => upd(f.key, e.target.value)}
                className="mt-1 bg-black/40 border-white/10 text-white" />
            </div>
          ))}
          <div className="grid grid-cols-2 gap-3">
            {ADDRESS_FIELDS.filter((f) => !f.full).map((f) => (
              <Input key={f.key} data-testid={`company-address-${f.key}`}
                value={draft[f.key] || ""}
                onChange={(e) => upd(f.key, e.target.value)}
                placeholder={f.label}
                className="bg-black/40 border-white/10 text-white" />
            ))}
          </div>
          <div className="flex gap-2 pt-2">
            <Button data-testid="company-address-save" onClick={save} disabled={busy || !isDirty}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm disabled:bg-neutral-700 disabled:text-neutral-400">
              <Save className="w-4 h-4 mr-1.5" /> {busy ? "Saving…" : isDirty ? "Save" : "No changes"}
            </Button>
            <Button data-testid="company-address-cancel" onClick={cancel} variant="outline"
              className="bg-transparent border-white/10 text-white">
              <X className="w-4 h-4 mr-1.5" /> Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
