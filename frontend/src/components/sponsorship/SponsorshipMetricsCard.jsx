import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Link } from "react-router-dom";
import { Megaphone, TrendingUp, Clock, CheckCircle, XCircle } from "lucide-react";

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="border border-white/10 bg-black/30 rounded-sm p-4">
      <div className="flex items-center gap-2">
        <Icon className="w-3.5 h-3.5" style={{ color }} />
        <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</div>
      </div>
      <div className="font-display text-3xl mt-2" style={{ color }}>{value}</div>
    </div>
  );
}

export default function SponsorshipMetricsCard() {
  const [m, setM] = useState(null);
  useEffect(() => { api.get("/admin/sponsorship-metrics").then((r) => setM(r.data)).catch(() => {}); }, []);
  if (!m) return null;
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-6 mt-6" data-testid="sponsorship-metrics-card">
      <div className="flex items-center gap-2">
        <Megaphone className="w-4 h-4 text-[#FACC15]" />
        <div className="font-display tracking-wider text-2xl">SPONSORSHIP MARKETPLACE</div>
        <Link to="/sponsorships" className="ml-auto text-[10px] font-mono uppercase tracking-widest text-[#FACC15] hover:underline">→ Browse marketplace</Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-4">
        <StatCard label="Total opportunities" value={m.total_opportunities} icon={TrendingUp} color="#FACC15" />
        <StatCard label="Total value" value={`₹${(m.total_sponsorship_value || 0).toLocaleString()}`} icon={TrendingUp} color="#84CC16" />
        <StatCard label="Pending" value={m.pending_applications} icon={Clock} color="#06B6D4" />
        <StatCard label="Awarded" value={m.accepted_applications} icon={CheckCircle} color="#10B981" />
        <StatCard label="Rejected" value={m.rejected_applications} icon={XCircle} color="#FF3B30" />
      </div>

      <div className="grid md:grid-cols-2 gap-4 mt-6">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mb-2">/ Top sponsors</div>
          {(m.top_sponsors || []).length === 0
            ? <div className="text-xs text-neutral-500">No awarded sponsorships yet.</div>
            : (m.top_sponsors || []).map((s) => (
              <div key={s.sponsor_id} className="flex items-center justify-between text-sm border-b border-white/5 py-1.5">
                <span>{s.name || "Anonymous"}</span>
                <span className="font-mono text-xs text-[#84CC16]">₹{Number(s.value || 0).toLocaleString()} · {s.count}</span>
              </div>
            ))}
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mb-2">/ Top events by value</div>
          {(m.top_events || []).length === 0
            ? <div className="text-xs text-neutral-500">No sponsorship-ready events yet.</div>
            : (m.top_events || []).map((e) => (
              <Link key={e.id} to={`/events/${e.id}`} className="flex items-center justify-between text-sm border-b border-white/5 py-1.5 hover:text-[#FACC15]">
                <span>{e.name}</span>
                <span className="font-mono text-xs text-[#FACC15]">₹{Number(e.value || 0).toLocaleString()}</span>
              </Link>
            ))}
        </div>
      </div>
    </div>
  );
}
