import { useEffect, useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Eye, Save, Search, Pencil, X } from "lucide-react";
import ImageUpload from "@/components/ImageUpload";
import SportsMultiSelect from "@/components/player/SportsMultiSelect";
import SportProfileSection from "@/components/player/SportProfileSection";
import SportStatsEditor from "@/components/player/SportStatsEditor";
import SportStatsDashboard from "@/components/player/SportStatsDashboard";
import { SPORT_SCHEMAS } from "@/lib/sportProfileSchema";
import { STATS_SCHEMAS } from "@/lib/sportStatsSchema";

const LEGACY_CRICKET_KEYS = ["role", "batting_hand", "bowling_style", "jersey_number", "cricheroes_url"];

/**
 * If the profile predates multi-sport (no interested_sports list), migrate the legacy
 * cricket fields into sport_profiles.cricket so they show up in the new UI.
 */
function withLegacyMigration(profile) {
  if (!profile) return profile;
  const interested = profile.interested_sports?.length ? profile.interested_sports : [];
  const sportProfiles = { ...(profile.sport_profiles || {}) };
  const hasAnyLegacy = LEGACY_CRICKET_KEYS.some((k) => profile[k] && profile[k] !== "any" && profile[k] !== "none");
  if (interested.length === 0 && hasAnyLegacy) {
    sportProfiles.cricket = {
      role: profile.role, batting_hand: profile.batting_hand,
      bowling_style: profile.bowling_style, jersey_number: profile.jersey_number,
      cricheroes_url: profile.cricheroes_url, ...sportProfiles.cricket,
    };
    return { ...profile, interested_sports: ["cricket"], sport_profiles: sportProfiles };
  }
  return { ...profile, interested_sports: interested, sport_profiles: sportProfiles };
}

/** Stable serialization for change-detection — `JSON.stringify` is fine here because
 *  field order is preserved by spread, and we strip noisy fields like view_count. */
function snapshot(p) {
  if (!p) return "";
  const { view_count, created_at, ...rest } = p;
  return JSON.stringify(rest);
}

export default function PlayerProfile() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [profile, setProfile] = useState(null);
  const [original, setOriginal] = useState("");
  const [companies, setCompanies] = useState([]);
  const [busy, setBusy] = useState(false);
  // Profile defaults to view-only. Player explicitly clicks Edit to make changes.
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (ready && (!user || user.role !== "player")) { nav("/players/login"); return; }
    if (ready) {
      api.get("/players/me").then((r) => {
        const migrated = withLegacyMigration(r.data);
        setProfile(migrated);
        setOriginal(snapshot(migrated));
      });
      api.get("/companies/public").then((r) => setCompanies(r.data));
    }
  }, [ready, user]);

  const upd = (patch) => setProfile({ ...profile, ...patch });
  const updSport = (sport, sportProfile) => setProfile({
    ...profile, sport_profiles: { ...(profile.sport_profiles || {}), [sport]: sportProfile },
  });
  const updStats = (sport, stats) => setProfile({
    ...profile, lifetime_stats: { ...(profile.lifetime_stats || {}), [sport]: stats },
  });

  const toggleInterestedSports = (next) => {
    const sp = { ...(profile.sport_profiles || {}) };
    next.forEach((s) => { if (!sp[s]) sp[s] = {}; });
    setProfile({ ...profile, interested_sports: next, sport_profiles: sp });
  };

  const isDirty = useMemo(() => snapshot(profile) !== original, [profile, original]);

  const save = async () => {
    setBusy(true);
    try {
      const body = { ...profile };
      ["id", "user_id", "mobile", "view_count", "created_at"].forEach((k) => delete body[k]);
      const cricket = body.sport_profiles?.cricket;
      if (cricket) {
        LEGACY_CRICKET_KEYS.forEach((k) => { if (cricket[k] !== undefined) body[k] = cricket[k]; });
      }
      const { data } = await api.patch("/players/me", body);
      const migrated = withLegacyMigration(data);
      setProfile(migrated);
      setOriginal(snapshot(migrated));
      setEditing(false);
      toast.success("Profile saved");
    } catch { toast.error("Failed to save"); }
    finally { setBusy(false); }
  };

  const cancel = () => {
    // Revert any unsaved tweaks by parsing the stored snapshot.
    try { setProfile(JSON.parse(original)); } catch { /* keep current */ }
    setEditing(false);
  };

  const interested = useMemo(() => profile?.interested_sports || [], [profile]);
  const companyName = useMemo(() => {
    if (!profile?.company_id) return "Independent";
    return companies.find((c) => c.id === profile.company_id)?.name || "Independent";
  }, [profile, companies]);

  if (!profile) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-5xl mx-auto px-6 pt-12 pb-24">
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Your Profile</div>
            <h1 className="font-display text-5xl tracking-wide mt-2">{profile.name?.toUpperCase()}</h1>
            <p className="text-neutral-400 text-sm mt-2 font-mono">{profile.mobile}</p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <div className="text-right">
              <div className="font-display text-3xl text-[#84CC16]" data-testid="pp-view-count">{profile.view_count || 0}</div>
              <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-widest flex items-center gap-1"><Eye className="w-3 h-3" /> Profile views</div>
            </div>
            <Link to="/players/profiles" data-testid="search-players-link">
              <Button variant="outline" className="border-white/10 bg-transparent text-white rounded-sm">
                <Search className="w-4 h-4 mr-1" /> Find players
              </Button>
            </Link>
            {!editing && (
              <Button data-testid="pp-edit-btn" onClick={() => setEditing(true)}
                className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
                <Pencil className="w-4 h-4 mr-1" /> Edit profile
              </Button>
            )}
          </div>
        </div>

        {editing ? (
          <EditForm
            profile={profile}
            companies={companies}
            interested={interested}
            upd={upd}
            updSport={updSport}
            updStats={updStats}
            toggleInterestedSports={toggleInterestedSports}
          />
        ) : (
          <ViewMode profile={profile} companyName={companyName} interested={interested} />
        )}

        {editing && (
          <div className="mt-6 flex gap-3" data-testid="pp-edit-actions">
            <Button data-testid="pp-save" disabled={busy || !isDirty} onClick={save}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm disabled:bg-neutral-700 disabled:text-neutral-400 disabled:cursor-not-allowed"
              title={!isDirty ? "Nothing to save — make a change first" : undefined}>
              <Save className="w-4 h-4 mr-1" /> {busy ? "Saving…" : isDirty ? "Save changes" : "No changes"}
            </Button>
            <Button data-testid="pp-cancel" onClick={cancel} variant="outline"
              className="bg-transparent border-white/10 text-white hover:bg-white/5">
              <X className="w-4 h-4 mr-1" /> Cancel
            </Button>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}

/* ───── View-only dashboard ───── */
function ViewMode({ profile, companyName, interested }) {
  return (
    <div className="grid md:grid-cols-3 gap-6 mt-10">
      <div className="border border-white/10 rounded-sm bg-[#141414] p-5 space-y-4">
        <div className="aspect-square rounded-sm overflow-hidden bg-black/40 border border-white/10">
          <img
            src={profile.photo_url || "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"}
            alt="" className="w-full h-full object-cover"
          />
        </div>
        <ReadField label="Company" value={companyName} testid="view-company" />
        <ReadField label="City" value={profile.city || "—"} testid="view-city" />
        <ReadField label="Date of birth" value={profile.dob || "—"} testid="view-dob" />
        <ReadField label="Height" value={profile.height_cm ? `${profile.height_cm} cm` : "—"} testid="view-height" />
        <ReadField label="Weight" value={profile.weight_kg ? `${profile.weight_kg} kg` : "—"} testid="view-weight" />
      </div>

      <div className="md:col-span-2 border border-white/10 rounded-sm bg-[#141414] p-5 space-y-5">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Bio</div>
          <p className="text-sm text-neutral-200 whitespace-pre-wrap" data-testid="view-bio">
            {profile.bio || <span className="text-neutral-500 italic">No bio yet — hit Edit to add one.</span>}
          </p>
        </div>

        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Interested sports</div>
          {interested.length === 0 ? (
            <p className="text-xs text-amber-400/80">No sports added yet — hit Edit to pick the ones you play.</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {interested.map((s) => (
                <span key={s} data-testid={`view-sport-${s}`}
                  className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-sm bg-[#84CC16]/15 text-[#84CC16] border border-[#84CC16]/30">
                  {s.replace(/-/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>

        {interested.map((s) => {
          const sp = profile.sport_profiles?.[s] || {};
          const schema = SPORT_SCHEMAS[s]?.fields || [];
          const hasAny = schema.some((f) => sp[f.key] !== undefined && sp[f.key] !== "" && sp[f.key] !== null);
          if (!hasAny) return null;
          return (
            <div key={s} data-testid={`view-sport-card-${s}`}
              className="border border-white/10 rounded-sm bg-black/30 p-4">
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16] mb-3">/ {(SPORT_SCHEMAS[s]?.label || s).replace(/-/g, " ")} profile</div>
              <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
                {schema.map((f) => {
                  const v = sp[f.key];
                  if (v === undefined || v === "" || v === null) return null;
                  const label = (f.label || f.key).replace(/_/g, " ");
                  const display = Array.isArray(v) ? v.join(", ") : String(v);
                  return (
                    <div key={f.key}>
                      <div className="text-[10px] font-mono uppercase text-neutral-500">{label}</div>
                      <div className="text-neutral-200 break-words">{display}</div>
                    </div>
                  );
                })}
              </div>
              <SportLifetimeStats sport={s} stats={profile.lifetime_stats?.[s] || {}} />
            </div>
          );
        })}

        {interested.length > 0 && profile.id && (
          <SportStatsDashboard profileId={profile.id} interestedSports={interested} />
        )}
      </div>
    </div>
  );
}

function SportLifetimeStats({ sport, stats }) {
  const schema = STATS_SCHEMAS?.[sport]?.manual || [];
  const entries = schema.filter((f) => stats[f.key] !== undefined && stats[f.key] !== "" && stats[f.key] !== null);
  if (entries.length === 0) return null;
  return (
    <div className="mt-4 pt-3 border-t border-white/10">
      <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-2">/ Lifetime career stats</div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {entries.map((f) => (
          <div key={f.key}>
            <div className="text-[10px] font-mono uppercase text-neutral-500">{(f.label || f.key).replace(/_/g, " ")}</div>
            <div className="font-display text-2xl text-[#84CC16]">{stats[f.key]}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReadField({ label, value, testid }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="text-neutral-200" data-testid={testid}>{value}</div>
    </div>
  );
}

/* ───── Edit form (extracted from previous inline JSX) ───── */
function EditForm({ profile, companies, interested, upd, updSport, updStats, toggleInterestedSports }) {
  return (
    <div className="grid md:grid-cols-3 gap-6 mt-10">
      <div className="border border-white/10 rounded-sm bg-[#141414] p-5">
        <div className="aspect-square rounded-sm overflow-hidden bg-black/40 border border-white/10">
          <img src={profile.photo_url || "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"} alt="" className="w-full h-full object-cover" />
        </div>
        <Field label="Photo"><ImageUpload value={profile.photo_url} onChange={(v) => upd({ photo_url: v })} testid="pp-photo" placeholder="https://… or upload selfie" /></Field>
        <Field label="Company (universal — change any time)">
          <Select value={profile.company_id || "__none__"} onValueChange={(v) => upd({ company_id: v === "__none__" ? null : v })}>
            <SelectTrigger data-testid="pp-company" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Independent" /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10 max-h-80">
              <SelectItem value="__none__">Independent</SelectItem>
              {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <div className="md:col-span-2 border border-white/10 rounded-sm bg-[#141414] p-5 space-y-5">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-4">/ Identity</div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Full name *"><Input data-testid="pp-name" value={profile.name} onChange={(e) => upd({ name: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
            <Field label="City"><Input data-testid="pp-city" value={profile.city || ""} onChange={(e) => upd({ city: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
            <Field label="Date of birth"><Input data-testid="pp-dob" type="date" value={profile.dob || ""} onChange={(e) => upd({ dob: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
            <Field label="Height (cm)"><Input data-testid="pp-height" type="number" value={profile.height_cm ?? ""} onChange={(e) => upd({ height_cm: e.target.value ? Number(e.target.value) : null })} className="bg-black/40 border-white/10 text-white" /></Field>
            <Field label="Weight (kg)"><Input data-testid="pp-weight" type="number" value={profile.weight_kg ?? ""} onChange={(e) => upd({ weight_kg: e.target.value ? Number(e.target.value) : null })} className="bg-black/40 border-white/10 text-white" /></Field>
          </div>
          <Field label="Bio"><Textarea data-testid="pp-bio" rows={3} value={profile.bio || ""} onChange={(e) => upd({ bio: e.target.value })} className="bg-black/40 border-white/10 text-white" /></Field>
        </div>

        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Interested sports — pick all that apply</div>
          <SportsMultiSelect value={interested} onChange={toggleInterestedSports} />
          {interested.length === 0 && (
            <p className="text-xs text-amber-400/80 mt-3">Select at least one sport to add your role &amp; playing style — captains use this to pick teams.</p>
          )}
        </div>

        <div className="space-y-3">
          {interested.map((s) => (
            <div key={s}>
              <SportProfileSection
                sport={s}
                sportProfile={profile.sport_profiles?.[s] || {}}
                onChange={(sp) => updSport(s, sp)}
                onRemove={() => toggleInterestedSports(interested.filter((x) => x !== s))}
              />
              <div className="border border-white/10 border-t-0 rounded-b-sm bg-black/20 px-4 -mt-px">
                <SportStatsEditor
                  sport={s}
                  manualStats={profile.lifetime_stats?.[s] || {}}
                  onChange={(stats) => updStats(s, stats)}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="mt-3">
      <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</Label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}
