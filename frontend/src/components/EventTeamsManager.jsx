import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { devError } from "@/lib/devLog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Trash2, Plus, Crown, UserPlus, Users, Building2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const COLOR_OPTIONS = ["#84CC16", "#EC4899", "#06B6D4", "#F59E0B", "#A855F7", "#3B82F6", "#EF4444"];

const INDIVIDUAL_SPORTS = new Set(["chess", "quiz", "hackathon"]);

export default function EventTeamsManager({ event, teams, reload }) {
  const { isPlatformAdmin, isCompanyAdmin, isPlayer, companyId } = useAuth();
  const [myPlayerId, setMyPlayerId] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [allPlayers, setAllPlayers] = useState([]);
  const [creds, setCreds] = useState(null); // { kind, email, password, name }

  useEffect(() => {
    if (isPlayer) api.get("/players/me").then((r) => setMyPlayerId(r.data.id)).catch(() => {});
    api.get(`/events/${event.id}/companies`).then((r) => setCompanies(r.data)).catch(() => {});
    api.get("/players/profiles").then((r) => setAllPlayers(r.data)).catch(() => {});
  }, [event.id, isPlayer]);

  const myCaptainTeamIds = useMemo(
    () => (myPlayerId ? teams.filter((t) => t.captain_player_id === myPlayerId).map((t) => t.id) : []),
    [teams, myPlayerId]
  );

  const canManageEvent = isPlatformAdmin || (isCompanyAdmin && (event.company_id === companyId || (event.companies || []).includes(companyId)));
  const canManageTeam = (t) => {
    if (isPlatformAdmin) return true;
    if (isCompanyAdmin && event.event_type === "inter_company") return t.company_id === companyId;
    if (isCompanyAdmin) return event.company_id === companyId;
    if (isPlayer && myCaptainTeamIds.includes(t.id)) return true;
    return false;
  };
  const canSeeTab = canManageEvent || myCaptainTeamIds.length > 0;

  // Memoized visible teams: avoids re-filtering on unrelated renders
  const visibleTeams = useMemo(() => {
    if (!canSeeTab) return [];
    return teams.filter((t) => {
      if (isPlatformAdmin) return true;
      if (isCompanyAdmin) {
        if (event.event_type === "inter_company") return t.company_id === companyId;
        return event.company_id === companyId;
      }
      if (isPlayer) return myCaptainTeamIds.includes(t.id);
      return false;
    });
  }, [teams, canSeeTab, isPlatformAdmin, isCompanyAdmin, isPlayer, event.event_type, event.company_id, companyId, myCaptainTeamIds]);

  if (!canSeeTab) return null;

  const isIndividual = INDIVIDUAL_SPORTS.has(event.sport);

  return (
    <div data-testid="teams-manager" className="space-y-8">
      {isPlatformAdmin && event.event_type === "inter_company" && (
        <EventCompaniesSection event={event} companies={companies} reload={async () => { await reload(); const r = await api.get(`/events/${event.id}/companies`); setCompanies(r.data); }} setCreds={setCreds} />
      )}

      {canManageEvent && (
        isIndividual ? (
          <NewIndividualPlayerForm
            event={event}
            companies={companies}
            isPlatformAdmin={isPlatformAdmin}
            companyId={companyId}
            allPlayers={allPlayers}
            reload={reload}
            setCreds={setCreds}
          />
        ) : (
          <NewTeamForm
            event={event}
            companies={companies}
            isPlatformAdmin={isPlatformAdmin}
            companyId={companyId}
            reload={reload}
          />
        )
      )}

      {visibleTeams.length === 0 ? (
        <div className="text-neutral-500 text-center py-16 border border-dashed border-white/10 rounded-sm">
          {isIndividual ? "No players registered yet. " : "No teams yet for your view. "}{canManageEvent && "Add the first one above."}
        </div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-4">
          {visibleTeams.map((t) => (
            <TeamCard
              key={t.id}
              team={t}
              event={event}
              companies={companies}
              allPlayers={allPlayers}
              canManage={canManageTeam(t)}
              reload={reload}
              setCreds={setCreds}
              individualMode={isIndividual}
            />
          ))}
        </div>
      )}

      <CredentialsModal open={!!creds} onClose={() => setCreds(null)} creds={creds} />
    </div>
  );
}

function EventCompaniesSection({ event, companies, reload, setCreds }) {
  const [mode, setMode] = useState("existing"); // existing | new
  const [pickedId, setPickedId] = useState("");
  const [allCompanies, setAllCompanies] = useState([]);
  const [form, setForm] = useState({ name: "", hr_name: "", hr_email: "" });

  useEffect(() => {
    api.get("/companies/public").then((r) => setAllCompanies(r.data)).catch(() => {});
  }, []);

  const addExisting = async () => {
    if (!pickedId) return toast.error("Pick a company");
    try {
      await api.post(`/events/${event.id}/companies`, { company_id: pickedId });
      toast.success("Company added");
      setPickedId("");
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const addNew = async () => {
    if (!(form.name && form.hr_email)) return toast.error("Name and HR email required");
    try {
      const { data } = await api.post(`/events/${event.id}/companies`, { new_company: form });
      toast.success("Company + HR account created");
      if (data.temp_password) setCreds({ kind: "HR", email: data.hr_email, password: data.temp_password, name: form.name });
      setForm({ name: "", hr_name: "", hr_email: "" });
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  const remove = async (cid) => {
    if (!window.confirm("Remove this company from the event?")) return;
    await api.delete(`/events/${event.id}/companies/${cid}`);
    reload();
  };

  // Memoized: pool of companies the event hasn't already onboarded
  const pickableCompanies = useMemo(
    () => allCompanies.filter((c) => !companies.find((x) => x.id === c.id)),
    [allCompanies, companies]
  );

  return (
    <div data-testid="event-companies" className="border border-white/10 rounded-sm bg-[#141414] p-5">
      <div className="flex items-center gap-2 mb-4">
        <Building2 className="w-4 h-4 text-[#06B6D4]" />
        <div className="font-display tracking-wider text-xl">PARTICIPATING COMPANIES</div>
      </div>
      <div className="flex flex-wrap gap-2 mb-4">
        {companies.length === 0 && <div className="text-xs text-neutral-500">No companies yet.</div>}
        {companies.map((c) => (
          <div key={c.id} data-testid={`event-company-${c.id}`} className="flex items-center gap-2 px-3 py-1.5 rounded-sm bg-black/40 border border-white/10 text-sm">
            <span>{c.name}</span>
            <button onClick={() => remove(c.id)} className="text-[#FF3B30] hover:text-white" aria-label="remove"><Trash2 className="w-3 h-3" /></button>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mb-3">
        <Button size="sm" variant={mode === "existing" ? "default" : "outline"} onClick={() => setMode("existing")} className="rounded-sm">Pick existing</Button>
        <Button size="sm" variant={mode === "new" ? "default" : "outline"} onClick={() => setMode("new")} className="rounded-sm">Create new company</Button>
      </div>
      {mode === "existing" ? (
        <div className="flex gap-2">
          <Select value={pickedId} onValueChange={setPickedId}>
            <SelectTrigger data-testid="ec-pick-company" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Pick a registered company" /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              {pickableCompanies.map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button data-testid="ec-add-existing" onClick={addExisting} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm">Add</Button>
        </div>
      ) : (
        <div className="grid md:grid-cols-3 gap-2">
          <Input data-testid="ec-new-name" placeholder="Company name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="ec-new-hr-name" placeholder="HR contact name" value={form.hr_name} onChange={(e) => setForm({ ...form, hr_name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="ec-new-hr-email" placeholder="HR email" value={form.hr_email} onChange={(e) => setForm({ ...form, hr_email: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Button data-testid="ec-create-new" onClick={addNew} className="md:col-span-3 bg-[#06B6D4] hover:bg-[#0891B2] text-black rounded-sm">Create company + HR login</Button>
        </div>
      )}
    </div>
  );
}

function NewIndividualPlayerForm({ event, companies, isPlatformAdmin, companyId, allPlayers, reload, setCreds }) {
  const [mode, setMode] = useState("existing");
  const [pickedPlayerId, setPickedPlayerId] = useState("");
  const [quick, setQuick] = useState({ name: "", mobile: "", email: "" });
  const [pickedCompanyId, setPickedCompanyId] = useState("");

  const targetCompanyId = isPlatformAdmin && event.event_type === "inter_company"
    ? pickedCompanyId
    : (companyId || event.company_id || "");

  const submit = async (e) => {
    e.preventDefault();
    if (event.event_type === "inter_company" && isPlatformAdmin && !targetCompanyId) return toast.error("Pick which company this player belongs to");
    let playerId = pickedPlayerId;
    let playerName = "";
    let createdCreds = null;
    if (mode === "quick") {
      if (!(quick.name && quick.mobile)) return toast.error("Name and mobile required");
      playerName = quick.name;
    } else {
      if (!playerId) return toast.error("Pick a player");
      const p = allPlayers.find((x) => x.id === playerId);
      playerName = p?.name || "Player";
    }
    try {
      // 1. Create a "team" of one (named after the player)
      const teamPayload = { name: playerName, color: "#84CC16" };
      if (targetCompanyId) teamPayload.company_id = targetCompanyId;
      const tr = await api.post(`/events/${event.id}/teams`, teamPayload);
      const teamId = tr.data.id;
      // 2. Add the player
      const memberBody = mode === "quick" ? { quick } : { player_id: playerId };
      const mr = await api.post(`/events/${event.id}/teams/${teamId}/members`, memberBody);
      if (mr.data.temp_password) {
        createdCreds = {
          kind: "Player",
          email: quick.email || `player_${quick.mobile}@players.playsphere.app`,
          password: mr.data.temp_password,
          name: quick.name,
        };
      }
      // 3. Auto-assign as captain so the player can manage their own entry
      await api.post(`/events/${event.id}/teams/${teamId}/captain`, { player_id: mr.data.player_id });
      toast.success("Player registered");
      if (createdCreds) setCreds(createdCreds);
      setPickedPlayerId("");
      setQuick({ name: "", mobile: "", email: "" });
      reload();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  return (
    <form onSubmit={submit} className="border border-white/10 rounded-sm bg-[#141414] p-5">
      <div className="font-display tracking-wider text-xl flex items-center gap-2 mb-3"><Plus className="w-4 h-4 text-[#84CC16]" /> REGISTER PLAYER</div>
      <div className="flex gap-2 mb-3">
        <Button type="button" size="sm" variant={mode === "existing" ? "default" : "outline"} onClick={() => setMode("existing")} className="rounded-sm" data-testid="indiv-mode-existing">Pick registered</Button>
        <Button type="button" size="sm" variant={mode === "quick" ? "default" : "outline"} onClick={() => setMode("quick")} className="rounded-sm" data-testid="indiv-mode-quick">Quick add (creates profile)</Button>
      </div>
      {mode === "existing" ? (
        <Select value={pickedPlayerId} onValueChange={setPickedPlayerId}>
          <SelectTrigger data-testid="indiv-pick" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Pick from registered players" /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10 max-h-[280px]">
            {allPlayers.map((p) => (<SelectItem key={p.id} value={p.id}>{p.name} {p.company_name ? `· ${p.company_name}` : ""}</SelectItem>))}
          </SelectContent>
        </Select>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Input data-testid="indiv-quick-name" placeholder="Full name" value={quick.name} onChange={(e) => setQuick({ ...quick, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="indiv-quick-mobile" placeholder="Mobile (+91...)" value={quick.mobile} onChange={(e) => setQuick({ ...quick, mobile: e.target.value })} className="bg-black/40 border-white/10 text-white" />
          <Input data-testid="indiv-quick-email" placeholder="Email (for login + reset)" value={quick.email} onChange={(e) => setQuick({ ...quick, email: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        </div>
      )}
      {event.event_type === "inter_company" && isPlatformAdmin && (
        <Select value={pickedCompanyId} onValueChange={setPickedCompanyId}>
          <SelectTrigger data-testid="indiv-company" className="bg-black/40 border-white/10 text-white mt-2"><SelectValue placeholder="Player's company" /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            {companies.map((c) => (<SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>))}
          </SelectContent>
        </Select>
      )}
      <Button data-testid="indiv-submit" type="submit" className="mt-3 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Register player</Button>
      <p className="text-[10px] text-neutral-500 mt-2 leading-relaxed">For {event.sport}, each participant registers as an individual — no team setup needed.</p>
    </form>
  );
}

function NewTeamForm({ event, companies, isPlatformAdmin, companyId, reload }) {
  const [form, setForm] = useState({ name: "", department: "", color: COLOR_OPTIONS[0], company_id: "" });
  const submit = async (e) => {
    e.preventDefault();
    if (!form.name) return toast.error("Team name required");
    const payload = { ...form };
    if (event.event_type === "inter_company") {
      if (!payload.company_id && companyId) payload.company_id = companyId;
      if (isPlatformAdmin && !payload.company_id) return toast.error("Pick which company this team belongs to");
    }
    try {
      await api.post(`/events/${event.id}/teams`, payload);
      toast.success("Team created");
      setForm({ name: "", department: "", color: COLOR_OPTIONS[0], company_id: "" });
      reload();
    } catch (e2) { toast.error(e2.response?.data?.detail || "Failed"); }
  };
  return (
    <form onSubmit={submit} className="border border-white/10 rounded-sm bg-[#141414] p-5 grid md:grid-cols-4 gap-2">
      <div className="md:col-span-4 font-display tracking-wider text-xl flex items-center gap-2"><Plus className="w-4 h-4 text-[#84CC16]" /> NEW TEAM</div>
      <Input data-testid="nt-name" placeholder="Team name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
      <Input data-testid="nt-dept" placeholder="Department (optional)" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="bg-black/40 border-white/10 text-white" />
      <Select value={form.color} onValueChange={(v) => setForm({ ...form, color: v })}>
        <SelectTrigger data-testid="nt-color" className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
        <SelectContent className="bg-[#141414] text-white border-white/10">
          {COLOR_OPTIONS.map((c) => (<SelectItem key={c} value={c}><span className="inline-flex items-center gap-2"><span className="w-3 h-3 rounded-sm" style={{ background: c }} />{c}</span></SelectItem>))}
        </SelectContent>
      </Select>
      {event.event_type === "inter_company" && isPlatformAdmin ? (
        <Select value={form.company_id} onValueChange={(v) => setForm({ ...form, company_id: v })}>
          <SelectTrigger data-testid="nt-company" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Company" /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            {companies.map((c) => (<SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>))}
          </SelectContent>
        </Select>
      ) : (
        <Button data-testid="nt-submit" type="submit" className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Add team</Button>
      )}
      {event.event_type === "inter_company" && isPlatformAdmin && (
        <Button data-testid="nt-submit" type="submit" className="md:col-span-4 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Add team</Button>
      )}
    </form>
  );
}

function useTeamMembers(eventId, teamId) {
  const [members, setMembers] = useState([]);
  const refresh = useMemo(() => async () => {
    try {
      const r = await api.get(`/events/${eventId}/teams/${teamId}/members`);
      setMembers(r.data);
    } catch (err) {
      devError("[useTeamMembers] refresh failed:", err);
    }
  }, [eventId, teamId]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get(`/events/${eventId}/teams/${teamId}/members`);
        if (!cancelled) setMembers(r.data);
      } catch (err) {
        devError("[useTeamMembers] initial load failed:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [eventId, teamId]);
  return [members, refresh];
}

function TeamCardHeader({ team, company }) {
  return (
    <div className="flex items-start justify-between mb-3">
      <div className="flex items-center gap-3">
        <span className="w-2 h-10 rounded-sm" style={{ background: team.color }} />
        <div>
          <div className="font-semibold text-base">{team.name}</div>
          <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-widest">
            {team.department || "team"}{company && ` · ${company.name}`}
          </div>
        </div>
      </div>
      {team.captain && (
        <div className="flex items-center gap-1 text-xs font-mono text-[#F59E0B]">
          <Crown className="w-3.5 h-3.5" /> {team.captain}
        </div>
      )}
    </div>
  );
}

function CaptainAssigner({ team, allPlayers, onAssign }) {
  const [captainPick, setCaptainPick] = useState("");
  const submit = () => {
    if (!captainPick) return toast.error("Pick a player");
    onAssign(captainPick).then(() => setCaptainPick(""));
  };
  return (
    <div className="flex gap-2 mb-3">
      <Select value={captainPick} onValueChange={setCaptainPick}>
        <SelectTrigger data-testid={`tc-captain-pick-${team.id}`} className="bg-black/40 border-white/10 text-white">
          <SelectValue placeholder="Assign captain (registered player)" />
        </SelectTrigger>
        <SelectContent className="bg-[#141414] text-white border-white/10 max-h-[260px]">
          {allPlayers.map((p) => (<SelectItem key={p.id} value={p.id}>{p.name} {p.company_name ? `· ${p.company_name}` : ""}</SelectItem>))}
        </SelectContent>
      </Select>
      <Button data-testid={`tc-captain-set-${team.id}`} onClick={submit} className="bg-[#F59E0B] hover:bg-[#D97706] text-black rounded-sm">Set</Button>
    </div>
  );
}

function MemberRow({ team, member, canManage, onRemove }) {
  return (
    <div data-testid={`tc-member-${member.id}`} className="flex items-center justify-between gap-2 px-3 py-2 rounded-sm bg-black/30 border border-white/5">
      <div className="flex items-center gap-2 min-w-0">
        {member.photo_url ? <img src={member.photo_url} alt="" className="w-7 h-7 rounded-full object-cover" /> : <div className="w-7 h-7 rounded-full bg-white/5" />}
        <div className="min-w-0">
          <div className="text-sm truncate">{member.name}{team.captain_player_id === member.id && <span className="ml-2 text-[10px] font-mono text-[#F59E0B]">CAPTAIN</span>}</div>
          <div className="text-[10px] font-mono text-neutral-500 truncate">{member.mobile_masked || member.mobile} · {member.role || "any"}</div>
        </div>
      </div>
      {canManage && (
        <button data-testid={`tc-member-del-${member.id}`} onClick={() => onRemove(member.id)} className="text-[#FF3B30] hover:text-white p-1" aria-label="remove"><Trash2 className="w-3.5 h-3.5" /></button>
      )}
    </div>
  );
}

function AddMemberDialog({ team, allPlayers, members, open, onOpenChange, onPick, onQuick }) {
  const [mode, setMode] = useState("existing");
  const [pickedPlayerId, setPickedPlayerId] = useState("");
  const [quick, setQuick] = useState({ name: "", mobile: "", email: "" });
  const memberIds = useMemo(() => new Set(members.map((m) => m.id)), [members]);
  const candidates = useMemo(() => allPlayers.filter((p) => !memberIds.has(p.id)), [allPlayers, memberIds]);

  const submit = async () => {
    if (mode === "existing") {
      if (!pickedPlayerId) return toast.error("Pick a player");
      await onPick(pickedPlayerId);
      setPickedPlayerId("");
    } else {
      if (!(quick.name && quick.mobile)) return toast.error("Name and mobile required");
      await onQuick(quick);
      setQuick({ name: "", mobile: "", email: "" });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#141414] text-white border-white/10">
        <DialogHeader><DialogTitle>Add player to {team.name}</DialogTitle></DialogHeader>
        <div className="flex gap-2 mb-3">
          <Button size="sm" variant={mode === "existing" ? "default" : "outline"} onClick={() => setMode("existing")} className="rounded-sm" data-testid={`tc-mode-existing-${team.id}`}>Pick registered</Button>
          <Button size="sm" variant={mode === "quick" ? "default" : "outline"} onClick={() => setMode("quick")} className="rounded-sm" data-testid={`tc-mode-quick-${team.id}`}>Quick add (creates profile)</Button>
        </div>
        {mode === "existing" ? (
          <Select value={pickedPlayerId} onValueChange={setPickedPlayerId}>
            <SelectTrigger data-testid={`tc-existing-pick-${team.id}`} className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Pick from registered players" /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10 max-h-[280px]">
              {candidates.map((p) => (<SelectItem key={p.id} value={p.id}>{p.name} {p.company_name ? `· ${p.company_name}` : ""}</SelectItem>))}
            </SelectContent>
          </Select>
        ) : (
          <div className="grid grid-cols-1 gap-2">
            <Input data-testid={`tc-quick-name-${team.id}`} placeholder="Full name" value={quick.name} onChange={(e) => setQuick({ ...quick, name: e.target.value })} className="bg-black/40 border-white/10 text-white" />
            <Input data-testid={`tc-quick-mobile-${team.id}`} placeholder="Mobile (e.g. +91…)" value={quick.mobile} onChange={(e) => setQuick({ ...quick, mobile: e.target.value })} className="bg-black/40 border-white/10 text-white" />
            <Input data-testid={`tc-quick-email-${team.id}`} placeholder="Email (for login + reset)" value={quick.email} onChange={(e) => setQuick({ ...quick, email: e.target.value })} className="bg-black/40 border-white/10 text-white" />
            <p className="text-[10px] text-neutral-500">A profile will be created with a temporary password. The credentials will be shown to you so you can share with the player.</p>
          </div>
        )}
        <DialogFooter>
          <Button onClick={submit} data-testid={`tc-confirm-add-${team.id}`} className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm">Add</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function TeamCard({ team, event, companies, allPlayers, canManage, reload, setCreds }) {
  const [members, refreshMembers] = useTeamMembers(event.id, team.id);
  const [open, setOpen] = useState(false);
  const company = useMemo(() => companies.find((c) => c.id === team.company_id), [companies, team.company_id]);

  const handleAssignCaptain = async (playerId) => {
    try {
      await api.post(`/events/${event.id}/teams/${team.id}/captain`, { player_id: playerId });
      toast.success("Captain assigned");
      await refreshMembers();
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handlePick = async (playerId) => {
    try {
      await api.post(`/events/${event.id}/teams/${team.id}/members`, { player_id: playerId });
      toast.success("Player added");
      setOpen(false);
      await refreshMembers();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handleQuick = async (quick) => {
    try {
      const { data } = await api.post(`/events/${event.id}/teams/${team.id}/members`, { quick });
      toast.success("Player added");
      if (data.temp_password) {
        setCreds({
          kind: "Player",
          email: quick.email || `player_${quick.mobile}@players.playsphere.app`,
          password: data.temp_password,
          name: quick.name,
        });
      }
      setOpen(false);
      await refreshMembers();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const handleRemove = async (pid) => {
    if (!window.confirm("Remove player from team?")) return;
    try {
      await api.delete(`/events/${event.id}/teams/${team.id}/members/${pid}`);
      await refreshMembers();
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div data-testid={`team-card-${team.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-5">
      <TeamCardHeader team={team} company={company} />
      {canManage && !team.captain_player_id && (
        <CaptainAssigner team={team} allPlayers={allPlayers} onAssign={handleAssignCaptain} />
      )}
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-mono uppercase tracking-widest text-neutral-500 flex items-center gap-1.5">
          <Users className="w-3 h-3" />Roster ({members.length})
        </div>
        {canManage && (
          <Button data-testid={`tc-add-member-${team.id}`} size="sm" variant="outline" onClick={() => setOpen(true)} className="rounded-sm border-white/10 text-white">
            <UserPlus className="w-3.5 h-3.5 mr-1" /> Add player
          </Button>
        )}
      </div>
      <div className="space-y-1.5">
        {members.length === 0 && <div className="text-xs text-neutral-600 py-2">No players yet.</div>}
        {members.map((m) => (
          <MemberRow key={m.id} team={team} member={m} canManage={canManage} onRemove={handleRemove} />
        ))}
      </div>
      <AddMemberDialog
        team={team}
        allPlayers={allPlayers}
        members={members}
        open={open}
        onOpenChange={setOpen}
        onPick={handlePick}
        onQuick={handleQuick}
      />
    </div>
  );
}

function CredentialsModal({ open, onClose, creds }) {
  if (!creds) return null;
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-[#141414] text-white border-white/10">
        <DialogHeader><DialogTitle>{creds.kind} login credentials</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-neutral-400">Share these credentials with {creds.name}. They should change the password on first login.</p>
          <div className="border border-[#84CC16]/40 rounded-sm bg-black/40 p-4 font-mono text-sm space-y-1.5">
            <div><span className="text-neutral-500">Email:</span> <span data-testid="cred-email" className="text-white">{creds.email}</span></div>
            <div><span className="text-neutral-500">Password:</span> <span data-testid="cred-password" className="text-[#84CC16]">{creds.password}</span></div>
          </div>
          <Button data-testid="cred-copy"
                  onClick={() => { navigator.clipboard.writeText(`${creds.email} / ${creds.password}`); toast.success("Copied"); }}
                  className="w-full bg-white/5 hover:bg-white/10 text-white rounded-sm">Copy email + password</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
