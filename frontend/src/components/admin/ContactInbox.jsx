import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Archive, Trash2, Mail, Inbox, RotateCcw } from "lucide-react";

/**
 * Admin contact-form inbox.
 * - Default view: active messages (not archived).
 * - Toggle to Archive view to see archived messages.
 * - Workflow per message:
 *     unread -> Mark read -> can Archive or Delete (delete blocked while unread, server-enforced).
 *     archived messages can be Restored or Deleted.
 */
export default function ContactInbox() {
  const [items, setItems] = useState([]);
  const [view, setView] = useState("inbox"); // inbox | archived

  const load = (mode = view) =>
    api.get(`/contact-messages${mode === "archived" ? "?archived=true" : ""}`)
      .then((r) => setItems(r.data))
      .catch(() => setItems([]));

  useEffect(() => { load(view); }, [view]);

  const markRead = async (id) => {
    try {
      await api.patch(`/contact-messages/${id}`, { read: true });
      load();
    } catch { toast.error("Failed"); }
  };

  const archive = async (id) => {
    try {
      await api.patch(`/contact-messages/${id}`, { archived: true });
      toast.success("Archived");
      load();
    } catch { toast.error("Failed"); }
  };

  const restore = async (id) => {
    try {
      await api.patch(`/contact-messages/${id}`, { archived: false });
      toast.success("Restored to inbox");
      load();
    } catch { toast.error("Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Permanently delete this message?")) return;
    try {
      await api.delete(`/contact-messages/${id}`);
      toast.success("Deleted");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Mark as read first.");
    }
  };

  const unreadCount = items.filter((x) => !x.read && !x.archived).length;

  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3 mt-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="font-display tracking-wider text-2xl">
          CONTACT INBOX {view === "inbox" && unreadCount > 0 && <span className="text-[#FACC15] text-sm font-mono">({unreadCount} unread)</span>}
        </div>
        <div className="flex gap-1.5">
          {["inbox", "archived"].map((v) => (
            <button key={v} type="button" data-testid={`contact-view-${v}`}
              onClick={() => setView(v)}
              className={`text-[10px] font-mono uppercase px-2.5 py-1 rounded-sm border transition-colors ${
                view === v
                  ? "bg-[#84CC16] text-black border-transparent"
                  : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
              }`}>
              {v === "inbox" ? <><Inbox className="w-3 h-3 inline mr-1" /> Inbox</> : <><Archive className="w-3 h-3 inline mr-1" /> Archive</>}
            </button>
          ))}
        </div>
      </div>

      {items.length === 0 && (
        <div data-testid="contact-empty" className="text-xs text-neutral-500 text-center py-8 border border-dashed border-white/10 rounded-sm">
          {view === "archived" ? "No archived messages." : "No messages yet."}
        </div>
      )}

      <div className="space-y-2 max-h-[480px] overflow-auto">
        {items.map((m) => (
          <div key={m.id} data-testid={`contact-msg-${m.id}`}
            className={`border border-white/10 rounded-sm p-3 ${m.read ? "bg-black/20" : "bg-black/40"}`}>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="min-w-0">
                <div className="font-semibold flex items-center gap-2">
                  {m.name}
                  <span className="text-[10px] font-mono text-neutral-500">{m.email}</span>
                  {!m.read && (
                    <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#FACC15] text-black">New</span>
                  )}
                </div>
                <div className="text-[10px] font-mono text-neutral-600">
                  {new Date(m.created_at).toLocaleString()} · phone: {m.phone || "—"}
                  {m.archived_at && <span className="ml-2 text-neutral-700">· archived {new Date(m.archived_at).toLocaleDateString()}</span>}
                </div>
              </div>
              <div className="flex gap-1">
                {!m.read && (
                  <Button size="sm" variant="ghost" data-testid={`contact-mark-read-${m.id}`}
                    onClick={() => markRead(m.id)} className="text-[#84CC16] text-xs">
                    <Mail className="w-3 h-3 mr-1" /> Mark read
                  </Button>
                )}
                {view === "inbox" && m.read && (
                  <Button size="sm" variant="ghost" data-testid={`contact-archive-${m.id}`}
                    onClick={() => archive(m.id)} className="text-neutral-300 hover:text-[#FACC15] text-xs">
                    <Archive className="w-3 h-3 mr-1" /> Archive
                  </Button>
                )}
                {view === "archived" && (
                  <Button size="sm" variant="ghost" data-testid={`contact-restore-${m.id}`}
                    onClick={() => restore(m.id)} className="text-neutral-300 hover:text-[#06B6D4] text-xs">
                    <RotateCcw className="w-3 h-3 mr-1" /> Restore
                  </Button>
                )}
                <Button size="sm" variant="ghost" data-testid={`contact-delete-${m.id}`}
                  onClick={() => remove(m.id)} className="text-[#FF3B30] text-xs"
                  title={!m.read ? "Mark as read first" : "Delete permanently"}>
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
            <div className="text-sm text-neutral-300 mt-2 whitespace-pre-wrap">{m.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
