import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import DOMPurify from "dompurify";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ShieldAlert, CheckCircle2, XCircle, FileText } from "lucide-react";

/**
 * Event approval banner — handles the three pre-approval states:
 * 1. `pending_organiser_ack` — organiser sees the admin's instructions
 *    inline and a single "I agree & submit for approval" button.
 * 2. `pending_admin_approval` — organiser sees "Awaiting approval";
 *    platform admin sees Approve / Reject buttons (with reason).
 * 3. `rejected` — organiser sees the reason. They can keep editing the event
 *    and once ready, re-trigger acknowledgement (resubmit) via the same flow.
 */
export default function EventApprovalBanner({
  event, isPendingAck, isPendingAdmin, isRejected,
  isOwnerOrganiser, isPlatformAdmin, onChange,
}) {
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (!isPendingAck && !isRejected) return;
    api.get("/settings").then((r) => setInstructions(r.data?.organiser_event_instructions || ""))
      .catch(() => setInstructions(""));
  }, [isPendingAck, isRejected]);

  // Sanitize the admin-authored instructions HTML before injecting it. The platform admin
  // composes these in a textarea (basic HTML allowed for bold / lists), so we DOMPurify
  // them per-render to neutralise any <script>, on-event handlers, or malicious tags
  // that might slip in.
  const safeInstructions = useMemo(() => {
    if (!instructions) return "";
    return DOMPurify.sanitize(instructions, {
      ALLOWED_TAGS: ["b", "strong", "i", "em", "u", "p", "br", "ul", "ol", "li", "a", "span", "div", "h3", "h4"],
      ALLOWED_ATTR: ["href", "target", "rel", "class"],
    });
  }, [instructions]);

  const acknowledge = async () => {
    setBusy(true);
    try {
      await api.post(`/events/${event.id}/acknowledge-instructions`);
      toast.success("Event submitted to platform admin for approval");
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to submit");
    } finally { setBusy(false); }
  };

  const approve = async () => {
    setBusy(true);
    try {
      await api.post(`/events/${event.id}/approve`);
      toast.success("Event approved — it's now live");
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  const reject = async () => {
    if (!reason.trim()) { toast.error("Reason is required"); return; }
    setBusy(true);
    try {
      await api.post(`/events/${event.id}/reject`, { reason: reason.trim() });
      toast.success("Event rejected — organiser notified");
      setShowReject(false); setReason("");
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  // ----- 1. Organiser acknowledgement view -----
  if (isPendingAck && isOwnerOrganiser) {
    return (
      <div data-testid="event-approval-ack" className="mt-6 border border-[#FACC15]/40 bg-[#FACC15]/5 rounded-sm p-5 max-w-3xl">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FACC15] flex items-center gap-2">
          <FileText className="w-3.5 h-3.5" /> / Action needed
        </div>
        <h3 className="font-display text-2xl tracking-wide mt-2">REVIEW PLATFORM INSTRUCTIONS</h3>
        <p className="text-sm text-neutral-400 mt-1.5">
          Your event has been saved as a draft. Before it goes to the platform admin for approval,
          please read and acknowledge the policies below.
        </p>
        <div data-testid="approval-instructions"
          className="mt-4 bg-black/40 border border-white/10 rounded-sm p-4 text-sm text-neutral-200 whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto"
          dangerouslySetInnerHTML={{ __html: safeInstructions || "<em class='text-neutral-500'>No instructions have been set by the platform admin yet — proceed to submit.</em>" }}
        />
        <Button data-testid="approval-acknowledge-btn" onClick={acknowledge} disabled={busy}
          className="mt-4 bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm">
          {busy ? "Submitting…" : "I agree & submit for approval"}
        </Button>
      </div>
    );
  }

  // ----- 2. Organiser waiting view -----
  if (isPendingAdmin && isOwnerOrganiser && !isPlatformAdmin) {
    return (
      <div data-testid="event-approval-waiting"
        className="mt-6 border border-[#06B6D4]/40 bg-[#06B6D4]/5 rounded-sm p-5 max-w-3xl">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4] flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5" /> / Pending review
        </div>
        <h3 className="font-display text-xl tracking-wide mt-1.5">AWAITING PLATFORM ADMIN APPROVAL</h3>
        <p className="text-sm text-neutral-300 mt-1">
          Your event has been queued for review. You&apos;ll be notified once it is approved.
          The event won&apos;t appear on the public events page until then.
        </p>
      </div>
    );
  }

  // ----- 3. Rejected view (visible to organiser) -----
  if (isRejected && isOwnerOrganiser && !isPlatformAdmin) {
    return (
      <div data-testid="event-approval-rejected"
        className="mt-6 border border-[#FF3B30]/40 bg-[#FF3B30]/5 rounded-sm p-5 max-w-3xl">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FF3B30] flex items-center gap-2">
          <XCircle className="w-3.5 h-3.5" /> / Rejected
        </div>
        <h3 className="font-display text-xl tracking-wide mt-1.5">EVENT REJECTED</h3>
        <p className="text-sm text-neutral-400 mt-1">Reason from the platform admin:</p>
        <div data-testid="approval-rejection-reason"
          className="mt-3 bg-black/40 border border-white/10 rounded-sm p-3 text-sm text-neutral-200">
          {event.rejection_reason || <em className="text-neutral-500">No reason provided.</em>}
        </div>
        <p className="text-xs text-neutral-500 mt-3">
          Edit the event details (venue, dates, sponsorship terms, etc.) and resubmit when ready.
        </p>
        <Button data-testid="approval-resubmit-btn" onClick={acknowledge} disabled={busy}
          className="mt-4 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
          {busy ? "Submitting…" : "Resubmit for approval"}
        </Button>
      </div>
    );
  }

  // ----- 4. Platform admin view (Approve / Reject) -----
  if (isPlatformAdmin && (isPendingAdmin || isPendingAck || isRejected)) {
    return (
      <div data-testid="event-approval-admin"
        className="mt-6 border border-[#FACC15]/40 bg-[#FACC15]/5 rounded-sm p-5 max-w-3xl">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FACC15] flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5" /> / Approval queue
        </div>
        <h3 className="font-display text-xl tracking-wide mt-1.5">
          {isPendingAck && "AWAITING ORGANISER ACKNOWLEDGEMENT"}
          {isPendingAdmin && "AWAITING YOUR APPROVAL"}
          {isRejected && "PREVIOUSLY REJECTED"}
        </h3>
        {isPendingAck && <p className="text-sm text-neutral-300 mt-1">The organiser has not yet acknowledged your instructions. You can still pre-approve the event.</p>}
        {isPendingAdmin && <p className="text-sm text-neutral-300 mt-1">The organiser has accepted your instructions. Review the event details (teams, dates, sponsorships) and approve to make it public.</p>}
        {isRejected && (
          <div className="mt-3 text-sm">
            <span className="text-neutral-500">Previous rejection reason: </span>
            <span className="text-neutral-200">{event.rejection_reason}</span>
          </div>
        )}

        {!showReject ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <Button data-testid="approval-approve-btn" onClick={approve} disabled={busy}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
              <CheckCircle2 className="w-4 h-4 mr-1.5" /> Approve & publish
            </Button>
            <Button data-testid="approval-reject-open-btn" type="button" variant="outline"
              onClick={() => setShowReject(true)}
              className="bg-transparent border-[#FF3B30] text-[#FF3B30] hover:bg-[#FF3B30]/10">
              <XCircle className="w-4 h-4 mr-1.5" /> Reject…
            </Button>
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            <Textarea data-testid="approval-reject-reason" rows={3}
              value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="Explain to the organiser why this event is being rejected. They can edit and resubmit."
              className="bg-black/40 border-white/10 text-white" />
            <div className="flex gap-2">
              <Button data-testid="approval-reject-confirm-btn" onClick={reject} disabled={busy}
                className="bg-[#FF3B30] hover:bg-[#dc2626] text-white font-semibold rounded-sm">
                Confirm rejection
              </Button>
              <Button data-testid="approval-reject-cancel-btn" type="button" variant="ghost"
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

  return null;
}
