import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Star, ShieldCheck, Flag, Send } from "lucide-react";

/* ============================================================
   Public-facing review block for a listing
   ============================================================ */
export function ListingReviews({ listingId }) {
  const [data, setData] = useState({ reviews: [], summary: { average: 0, count: 0 } });
  useEffect(() => {
    let cancelled = false;
    api.get(`/vendor-listings/${listingId}/reviews`)
      .then((r) => { if (!cancelled) setData(r.data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [listingId]);

  if (!data.reviews.length && !data.summary.count) return null;
  return (
    <div data-testid="listing-reviews" className="mt-6">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-xl">Reviews</h3>
        <div className="flex items-center gap-1">
          <StarRow value={Math.round(data.summary.average)} />
          <span className="text-sm font-mono text-neutral-300">{data.summary.average.toFixed(1)} · {data.summary.count}</span>
        </div>
      </div>
      <div className="mt-3 space-y-3">
        {data.reviews.map((rv) => (
          <ReviewCard key={rv.id} rv={rv} />
        ))}
      </div>
    </div>
  );
}

function ReviewCard({ rv }) {
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StarRow value={rv.rating} />
          <span className="text-xs font-mono text-neutral-400">{rv.author_name}</span>
          <span className="text-[10px] font-mono text-neutral-600">{(rv.created_at || "").slice(0, 10)}</span>
        </div>
      </div>
      {rv.text && <p className="text-sm text-neutral-200 mt-2 whitespace-pre-line">{rv.text}</p>}
      {rv.vendor_response && (
        <div className="mt-3 border-l-2 border-[#06B6D4] pl-3">
          <div className="text-[10px] font-mono uppercase text-[#06B6D4]">/ Vendor response</div>
          <p className="text-xs text-neutral-300 mt-1 whitespace-pre-line">{rv.vendor_response}</p>
        </div>
      )}
    </div>
  );
}

/* ============================================================
   Star widget — input form for a completed booking
   ============================================================ */
export function ReviewForm({ listingId, bookingId, onSubmitted }) {
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (rating < 1) return toast.error("Please pick a star rating");
    try {
      setBusy(true);
      const r = await api.post(`/vendor-listings/${listingId}/reviews`, {
        rating, text, booking_id: bookingId,
      });
      toast.success("Review submitted — pending vendor approval");
      onSubmitted && onSubmitted(r.data);
      setRating(0); setText("");
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <div data-testid={`review-form-${bookingId}`} className="border border-white/10 rounded-sm bg-[#141414] p-4 mt-3">
      <div className="font-mono text-[10px] uppercase text-neutral-500">/ Leave a review</div>
      <div className="flex items-center gap-1 mt-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} data-testid={`review-star-${n}`} onClick={() => setRating(n)} className="p-1">
            <Star className={`w-6 h-6 ${n <= rating ? "fill-[#FACC15] text-[#FACC15]" : "text-neutral-600"}`} />
          </button>
        ))}
      </div>
      <textarea data-testid="review-text" value={text} onChange={(e) => setText(e.target.value)} rows={3}
        placeholder="Share your experience (optional)"
        className="mt-2 w-full bg-black/40 border border-white/10 rounded-sm p-2 text-sm text-white" />
      <Button data-testid="review-submit" disabled={busy} onClick={submit}
        className="mt-2 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
        <Send className="w-3.5 h-3.5 mr-1" /> Submit review
      </Button>
    </div>
  );
}

function StarRow({ value }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} className={`w-3.5 h-3.5 ${n <= value ? "fill-[#FACC15] text-[#FACC15]" : "text-neutral-700"}`} />
      ))}
    </div>
  );
}

/* ============================================================
   Vendor inbox — approve / flag / respond
   ============================================================ */
export function VendorReviewsInbox() {
  const [items, setItems] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [responses, setResponses] = useState({});

  const load = () => api.get("/vendors/me/reviews").then((r) => setItems(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const act = async (rid, body) => {
    try {
      setBusyId(rid);
      await api.post(`/reviews/${rid}/respond`, body);
      toast.success("Saved");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusyId(null); }
  };

  if (items.length === 0) return null;
  return (
    <div data-testid="vendor-reviews-inbox" className="mt-12">
      <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#FACC15]">/ Reviews awaiting your action</div>
      <h2 className="font-display text-3xl mt-2">CUSTOMER FEEDBACK</h2>
      <div className="mt-5 space-y-3">
        {items.map((rv) => (
          <div key={rv.id} data-testid={`vendor-review-${rv.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <StarRow value={rv.rating} />
                <span className="text-xs font-mono text-neutral-400">{rv.author_name}</span>
                <StatusPill status={rv.status} />
              </div>
              <span className="text-[10px] font-mono text-neutral-600">{(rv.created_at || "").slice(0, 10)}</span>
            </div>
            {rv.text && <p className="text-sm text-neutral-200 mt-2 whitespace-pre-line">{rv.text}</p>}

            {rv.status === "pending_vendor" && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button data-testid={`vendor-review-approve-${rv.id}`} size="sm" disabled={busyId === rv.id}
                  onClick={() => act(rv.id, { action: "approve" })}
                  className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm">
                  <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Approve & send to admin
                </Button>
                <Button data-testid={`vendor-review-flag-${rv.id}`} size="sm" variant="outline" disabled={busyId === rv.id}
                  onClick={() => act(rv.id, { action: "flag", note: window.prompt("Flag reason (optional)") || "" })}
                  className="rounded-sm border-[#FF3B30]/40 text-[#FF3B30]">
                  <Flag className="w-3.5 h-3.5 mr-1" /> Flag
                </Button>
              </div>
            )}

            {(rv.status === "pending_admin" || rv.status === "pending_vendor") && (
              <div className="mt-3 border-t border-white/5 pt-3">
                <Label className="text-[10px] font-mono text-neutral-500">Public response (optional)</Label>
                <Input data-testid={`vendor-review-response-${rv.id}`} placeholder="Thank you for the kind words..." value={responses[rv.id] || rv.vendor_response || ""}
                  onChange={(e) => setResponses({ ...responses, [rv.id]: e.target.value })}
                  className="bg-black/40 border-white/10 text-white mt-1" />
                <Button data-testid={`vendor-review-response-save-${rv.id}`} size="sm" disabled={busyId === rv.id}
                  onClick={() => act(rv.id, { action: "respond", response: responses[rv.id] || "" })}
                  className="mt-2 rounded-sm bg-white/10 hover:bg-white/20 text-white">
                  Save response
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   Admin moderation queue
   ============================================================ */
export function AdminReviewsQueue() {
  const [items, setItems] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const load = () => api.get("/admin/reviews/queue").then((r) => setItems(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const act = async (rid, body) => {
    try {
      setBusyId(rid);
      await api.post(`/admin/reviews/${rid}/moderate`, body);
      toast.success("Moderated");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setBusyId(null); }
  };

  if (items.length === 0) return (
    <div data-testid="admin-reviews-empty" className="text-sm text-neutral-500 mt-3">No reviews awaiting moderation.</div>
  );
  return (
    <div data-testid="admin-reviews-queue" className="space-y-3">
      {items.map((rv) => (
        <div key={rv.id} data-testid={`admin-review-${rv.id}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <StarRow value={rv.rating} />
              <span className="text-xs font-mono text-neutral-400">{rv.author_name} → listing {rv.listing_id.slice(0, 8)}</span>
              <StatusPill status={rv.status} />
            </div>
            <span className="text-[10px] font-mono text-neutral-600">{(rv.created_at || "").slice(0, 10)}</span>
          </div>
          {rv.text && <p className="text-sm text-neutral-200 mt-2 whitespace-pre-line">{rv.text}</p>}
          {rv.vendor_response && (
            <div className="mt-2 border-l-2 border-[#06B6D4] pl-3 text-xs text-neutral-300">
              <span className="font-mono text-[10px] uppercase text-[#06B6D4]">vendor: </span>{rv.vendor_response}
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <Button data-testid={`admin-review-publish-${rv.id}`} size="sm" disabled={busyId === rv.id}
              onClick={() => act(rv.id, { action: "publish" })}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black rounded-sm">
              Publish
            </Button>
            <Button data-testid={`admin-review-reject-${rv.id}`} size="sm" variant="outline" disabled={busyId === rv.id}
              onClick={() => act(rv.id, { action: "reject", note: window.prompt("Reject note (optional)") || "" })}
              className="rounded-sm border-[#FF3B30]/40 text-[#FF3B30]">
              Reject
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    pending_vendor: { c: "#FACC15", t: "Awaiting vendor" },
    pending_admin: { c: "#06B6D4", t: "Awaiting admin" },
    visible: { c: "#84CC16", t: "Published" },
    flagged: { c: "#FF3B30", t: "Flagged" },
    rejected: { c: "#FF3B30", t: "Rejected" },
  };
  const cfg = map[status] || { c: "#999", t: status };
  return (
    <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm" style={{ color: cfg.c, border: `1px solid ${cfg.c}66`, background: `${cfg.c}22` }}>
      {cfg.t}
    </span>
  );
}
