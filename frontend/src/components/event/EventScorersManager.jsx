import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Mail, Trash2, Copy, ShieldCheck } from "lucide-react";

/**
 * Scorer invitation panel.
 * - Lets the event organiser/HR invite scorers by email and optionally restrict
 *   them to specific fixtures.
 * - On invite, backend creates a `scorer` user (if not already registered),
 *   emails the credentials, and also returns the temp password once so we can
 *   show it inline (fallback when SendGrid delivery fails).
 */
export default function EventScorersManager({ eventId, fixtures, teamMap }) {
  const [scorers, setScorers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [scope, setScope] = useState("all"); // all | specific
  const [pickedFixtures, setPickedFixtures] = useState([]);
  const [lastResult, setLastResult] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get(`/events/${eventId}/scorers`);
      setScorers(data || []);
    } catch {
      setScorers([]);
    }
  };
  useEffect(() => { load(); }, [eventId]);

  const togglePick = (id) =>
    setPickedFixtures((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const invite = async (e) => {
    e.preventDefault();
    if (!email.trim()) { toast.error("Enter the scorer's email"); return; }
    if (scope === "specific" && pickedFixtures.length === 0) {
      toast.error("Pick at least one fixture or switch to 'All fixtures'");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post(`/events/${eventId}/scorers`, {
        email: email.trim().toLowerCase(),
        name: name.trim(),
        fixture_ids: scope === "specific" ? pickedFixtures : [],
      });
      setLastResult(data);
      if (data.email_sent) {
        toast.success("Invitation emailed");
      } else if (data.user_created) {
        toast.warning("Account created but email delivery failed. Copy credentials below.");
      } else {
        toast.success("Scorer assigned (existing account, no email sent).");
      }
      setEmail(""); setName(""); setPickedFixtures([]); setScope("all");
      await load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to invite scorer");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (assignmentId) => {
    if (!window.confirm("Remove this scorer's access?")) return;
    try {
      await api.delete(`/events/${eventId}/scorers/${assignmentId}`);
      toast.success("Scorer removed");
      await load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  const copy = async (text) => {
    try { await navigator.clipboard.writeText(text); toast.success("Copied"); }
    catch { toast.error("Copy failed"); }
  };

  return (
    <div className="space-y-8">
      <div className="border border-white/10 rounded-sm bg-[#141414] p-5">
        <div className="font-display tracking-wider text-xl flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-[#06B6D4]" /> INVITE A SCORER
        </div>
        <p className="text-xs text-neutral-400 mt-2 max-w-2xl">
          Scorers can update live scores only for the events/matches you assign them to. If the
          person isn&apos;t already on Kreeda Nation, a lightweight account is auto-created and login
          credentials are emailed to them.
        </p>

        <form onSubmit={invite} className="mt-5 grid md:grid-cols-2 gap-3">
          <div>
            <Label className="text-[10px] font-mono uppercase text-neutral-500">Email *</Label>
            <Input data-testid="scorer-invite-email" type="email" value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="scorer@example.com"
              className="mt-1.5 bg-black/40 border-white/10 text-white" />
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase text-neutral-500">Name (optional)</Label>
            <Input data-testid="scorer-invite-name" value={name}
              onChange={(e) => setName(e.target.value)} placeholder="Ravi Sharma"
              className="mt-1.5 bg-black/40 border-white/10 text-white" />
          </div>
          <div className="md:col-span-2">
            <Label className="text-[10px] font-mono uppercase text-neutral-500">Scope</Label>
            <div className="flex gap-1.5 mt-1.5">
              {[
                { k: "all", label: "All fixtures of this event" },
                { k: "specific", label: "Specific fixtures only" },
              ].map((opt) => (
                <button key={opt.k} type="button" data-testid={`scorer-scope-${opt.k}`}
                  onClick={() => setScope(opt.k)}
                  className={`text-[11px] font-mono uppercase px-2.5 py-1 rounded-sm border transition-colors ${
                    scope === opt.k
                      ? "bg-[#06B6D4] text-black border-transparent"
                      : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
                  }`}>
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          {scope === "specific" && (
            <div className="md:col-span-2 max-h-56 overflow-y-auto border border-white/10 rounded-sm p-3 bg-black/30">
              {fixtures.length === 0 && <div className="text-xs text-neutral-500">No fixtures yet — generate them first.</div>}
              <div className="grid sm:grid-cols-2 gap-1.5">
                {fixtures.map((f) => {
                  const a = teamMap[f.team_a_id]; const b = teamMap[f.team_b_id];
                  const on = pickedFixtures.includes(f.id);
                  return (
                    <button key={f.id} type="button" data-testid={`scorer-pick-${f.id}`}
                      onClick={() => togglePick(f.id)}
                      className={`text-left text-xs px-3 py-2 rounded-sm border transition-colors ${
                        on ? "bg-[#06B6D4]/20 border-[#06B6D4] text-white" : "bg-black/40 border-white/10 text-neutral-300 hover:border-white/30"
                      }`}>
                      <div className="font-mono text-[10px] text-neutral-500">Match #{f.match_number} · R{f.round}</div>
                      <div>{a?.name || "TBD"} <span className="text-neutral-500">vs</span> {b?.name || "TBD"}</div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <div className="md:col-span-2">
            <Button data-testid="scorer-invite-submit" type="submit" disabled={busy}
              className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
              <Mail className="w-4 h-4 mr-1.5" /> {busy ? "Sending invite…" : "Send invitation"}
            </Button>
          </div>
        </form>

        {lastResult && lastResult.temp_password && (
          <div data-testid="scorer-invite-result" className="mt-5 border border-[#FACC15]/40 bg-[#FACC15]/5 rounded-sm p-4 text-sm">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15] mb-1">/ Account created</div>
            <div className="text-neutral-300">An invitation email was {lastResult.email_sent ? "sent" : "attempted"}. Share these credentials manually if needed:</div>
            <div className="mt-3 grid sm:grid-cols-2 gap-2">
              <div className="bg-black/40 rounded-sm px-3 py-2 font-mono text-xs flex items-center justify-between">
                <span className="text-neutral-300 truncate">{email || "(see list below)"}</span>
              </div>
              <div className="bg-black/40 rounded-sm px-3 py-2 font-mono text-xs flex items-center justify-between">
                <span className="text-[#FACC15] truncate">{lastResult.temp_password}</span>
                <button type="button" onClick={() => copy(lastResult.temp_password)} className="ml-2 text-neutral-400 hover:text-white" data-testid="scorer-copy-pwd">
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Active scorers ({scorers.length})</div>
        {scorers.length === 0 ? (
          <div className="text-neutral-500 text-center py-10 border border-dashed border-white/10 rounded-sm text-sm">
            No scorers invited yet.
          </div>
        ) : (
          <div className="space-y-2">
            {scorers.map((s) => (
              <div key={s.id} data-testid={`scorer-row-${s.id}`}
                className="border border-white/10 rounded-sm bg-[#141414] p-4 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="font-semibold truncate">{s.name || s.email}</div>
                  <div className="text-xs text-neutral-400 font-mono truncate">{s.email}</div>
                  <div className="text-[10px] font-mono uppercase text-[#06B6D4] mt-1">
                    {(s.fixture_ids || []).length === 0 ? "All fixtures" : `${(s.fixture_ids || []).length} specific fixture(s)`}
                  </div>
                </div>
                <Button size="sm" variant="ghost" data-testid={`scorer-remove-${s.id}`}
                  onClick={() => remove(s.id)} className="text-[#FF3B30] hover:text-white">
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
