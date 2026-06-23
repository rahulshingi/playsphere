import { useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { CheckCircle2, XCircle, ExternalLink } from "lucide-react";

/**
 * Platform-admin approvals inbox. Shows every event submitted by an organiser
 * that is currently in `pending_admin_approval`. Lets the admin approve
 * (event goes public) or reject with a reason (organiser can edit + resubmit).
 */
export default function PendingApprovalsTab({ pending, companies = [], reload }) {
  const companyMap = Object.fromEntries(companies.map((c) => [c.id, c]));
  return (
    <div className="space-y-3">
      {pending.length === 0 ? (
        <div data-testid="approvals-empty"
          className="text-neutral-500 text-center py-16 border border-dashed border-white/10 rounded-sm">
          Nothing in the approval queue right now.
        </div>
      ) : (
        pending.map((e) => (
          <ApprovalRow key={e.id} event={e}
            organiser={companyMap[e.company_id]?.name || "Unknown organiser"}
            reload={reload} />
        ))
      )}
    </div>
  );
}

function ApprovalRow({ event, organiser, reload }) {
  const [showReject, setShowReject] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const approve = async () => {
    setBusy(true);
    try {
      await api.post(`/events/${event.id}/approve`);
      toast.success("Approved — event is now live");
      reload?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  const reject = async () => {
    if (!reason.trim()) { toast.error("Reason is required"); return; }
    setBusy(true);
    try {
      await api.post(`/events/${event.id}/reject`, { reason: reason.trim() });
      toast.success("Rejected — organiser notified");
      reload?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  return (
    <div data-testid={`approval-row-${event.id}`}
      className="border border-[#FACC15]/30 rounded-sm bg-[#141414] p-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15]">
            / Submitted {event.submitted_at ? new Date(event.submitted_at).toLocaleString() : "—"}
          </div>
          <div className="font-display text-2xl tracking-wide mt-1">{event.name}</div>
          <div className="text-xs text-neutral-400 mt-1">
            <span className="text-[#84CC16] font-mono uppercase text-[10px]">Organiser</span>{" "}
            {organiser}
            <span className="mx-2 text-neutral-700">·</span>
            <span className="font-mono uppercase text-[10px]">{event.sport}</span>
            <span className="mx-2 text-neutral-700">·</span>
            <span className="font-mono uppercase text-[10px]">{event.format.replace("_", " ")}</span>
            {event.venue && <><span className="mx-2 text-neutral-700">·</span>{event.venue}</>}
          </div>
          {event.description && (
            <p className="text-sm text-neutral-300 mt-2 max-w-2xl line-clamp-2">{event.description}</p>
          )}
        </div>
        <Link to={`/events/${event.id}`} data-testid={`approval-open-${event.id}`}
          className="text-xs font-mono uppercase tracking-widest px-3 py-2 bg-white/5 hover:bg-white/10 rounded-sm flex items-center gap-1.5">
          Open <ExternalLink className="w-3 h-3" />
        </Link>
      </div>

      {!showReject ? (
        <div className="mt-4 flex gap-2">
          <Button data-testid={`approval-approve-${event.id}`} onClick={approve} disabled={busy}
            className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
            <CheckCircle2 className="w-4 h-4 mr-1.5" /> Approve & publish
          </Button>
          <Button data-testid={`approval-reject-open-${event.id}`} type="button" variant="outline"
            onClick={() => setShowReject(true)}
            className="bg-transparent border-[#FF3B30] text-[#FF3B30] hover:bg-[#FF3B30]/10">
            <XCircle className="w-4 h-4 mr-1.5" /> Reject…
          </Button>
        </div>
      ) : (
        <div className="mt-4 space-y-2">
          <Textarea data-testid={`approval-reject-reason-${event.id}`} rows={3}
            value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="Explain to the organiser why this event is being rejected. They can edit and resubmit."
            className="bg-black/40 border-white/10 text-white" />
          <div className="flex gap-2">
            <Button data-testid={`approval-reject-confirm-${event.id}`} onClick={reject} disabled={busy}
              className="bg-[#FF3B30] hover:bg-[#dc2626] text-white font-semibold rounded-sm">
              Confirm rejection
            </Button>
            <Button data-testid={`approval-reject-cancel-${event.id}`} type="button" variant="ghost"
              onClick={() => { setShowReject(false); setReason(""); }}
              className="text-neutral-300 hover:text-white">
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
