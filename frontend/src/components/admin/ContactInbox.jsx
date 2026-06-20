import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function ContactInbox() {
  const [items, setItems] = useState([]);
  const load = () => api.get("/contact-messages").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const markRead = async (id) => { await api.patch(`/contact-messages/${id}`, { read: true }); load(); };
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-6 max-w-2xl space-y-3 mt-6">
      <div className="font-display tracking-wider text-2xl">CONTACT INBOX ({items.filter((x) => !x.read).length} unread)</div>
      {items.length === 0 && <div className="text-xs text-neutral-500">No messages yet.</div>}
      <div className="space-y-2 max-h-[480px] overflow-auto">
        {items.map((m) => (
          <div key={m.id} data-testid={`contact-msg-${m.id}`} className={`border border-white/10 rounded-sm p-3 ${m.read ? "bg-black/20" : "bg-black/40"}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold">{m.name} <span className="text-[10px] font-mono text-neutral-500">{m.email}</span></div>
                <div className="text-[10px] font-mono text-neutral-600">{new Date(m.created_at).toLocaleString()} · phone: {m.phone || "—"}</div>
              </div>
              {!m.read && <Button size="sm" variant="ghost" onClick={() => markRead(m.id)} className="text-[#84CC16] text-xs">Mark read</Button>}
            </div>
            <div className="text-sm text-neutral-300 mt-2 whitespace-pre-wrap">{m.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
