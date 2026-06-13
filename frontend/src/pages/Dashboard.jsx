import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { CalendarDays, Users, Activity, Package, Plus, ChevronRight } from "lucide-react";

export default function Dashboard() {
  const { ready, isCompanyAdmin, companyName, user } = useAuth();
  const nav = useNavigate();
  const [stats, setStats] = useState({});
  const [events, setEvents] = useState([]);
  const [bookings, setBookings] = useState([]);

  useEffect(() => {
    if (ready && !isCompanyAdmin) { nav("/login"); return; }
    if (ready && user?.company_id) {
      Promise.all([
        api.get("/stats/company"),
        api.get(`/events?company_id=${user.company_id}`),
        api.get("/bookings"),
      ]).then(([s, e, b]) => {
        setStats(s.data); setEvents(e.data); setBookings(b.data);
      });
    }
  }, [ready, isCompanyAdmin, user?.company_id]);

  if (!ready) return <div className="bg-[#0a0a0a] min-h-screen text-white"><Nav /><div className="p-20 text-center">Loading…</div></div>;

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-7xl mx-auto px-6 pt-12 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ {companyName}</div>
        <div className="flex items-end justify-between flex-wrap gap-4">
          <h1 className="font-display text-6xl tracking-wide mt-3">YOUR PLAYSPHERE</h1>
          <div className="flex gap-2">
            <Button data-testid="dashboard-new-event" onClick={() => nav("/admin")} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
              <Plus className="w-4 h-4 mr-1" /> New tournament
            </Button>
            <Button data-testid="dashboard-browse-services" onClick={() => nav("/services")} variant="outline" className="border-white/10 bg-transparent text-white rounded-sm">Browse services</Button>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/10 mt-10 border border-white/10 rounded-sm overflow-hidden">
          {[
            { l: "EVENTS",   v: stats.events ?? 0,   icon: CalendarDays },
            { l: "TEAMS",    v: stats.teams ?? 0,    icon: Users },
            { l: "LIVE",     v: stats.live ?? 0,     icon: Activity, red: true },
            { l: "BOOKINGS", v: stats.bookings ?? 0, icon: Package, accent: true },
          ].map((s, i) => (
            <div key={i} className="bg-[#0a0a0a] p-5">
              <s.icon className={`w-4 h-4 ${s.red ? "text-[#FF3B30]" : s.accent ? "text-[#84CC16]" : "text-neutral-500"}`} />
              <div className={`font-mono text-4xl mt-3 ${s.red ? "text-[#FF3B30]" : s.accent ? "text-[#84CC16]" : "text-white"}`}>{String(s.v).padStart(2, "0")}</div>
              <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-neutral-500 mt-1">{s.l}</div>
            </div>
          ))}
        </div>

        <div className="grid md:grid-cols-2 gap-6 mt-12">
          <Panel title="YOUR TOURNAMENTS" cta={{ label: "New", to: "/admin" }}>
            {events.length === 0 ? <Empty msg="No tournaments yet. Spin one up in admin." /> : events.slice(0, 5).map((e) => (
              <Link to={`/events/${e.id}`} key={e.id} className="flex items-center justify-between border-t border-white/5 py-3 hover:bg-white/[0.02] px-2">
                <div>
                  <div className="font-medium">{e.name}</div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500">{e.sport} · {e.status}</div>
                </div>
                <ChevronRight className="w-4 h-4 text-neutral-500" />
              </Link>
            ))}
          </Panel>

          <Panel title="RECENT BOOKINGS" cta={{ label: "All", to: "/bookings" }}>
            {bookings.length === 0 ? <Empty msg="No service bookings yet — head to Services." /> : bookings.slice(0, 5).map((b) => (
              <div key={b.id} className="flex items-center justify-between border-t border-white/5 py-3 px-2">
                <div>
                  <div className="font-medium">{b.service_name}</div>
                  <div className="text-[10px] font-mono uppercase text-neutral-500">qty {b.quantity} · {b.variant_name || "—"}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono">${b.total_price.toFixed(0)}</div>
                  <StatusPill status={b.status} />
                </div>
              </div>
            ))}
          </Panel>
        </div>
      </div>
      <Footer />
    </div>
  );
}

function Panel({ title, cta, children }) {
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-5">
      <div className="flex items-center justify-between mb-2">
        <div className="font-display tracking-wider text-xl">{title}</div>
        {cta && <Link to={cta.to} className="text-xs font-mono text-[#84CC16] hover:underline">{cta.label} →</Link>}
      </div>
      {children}
    </div>
  );
}
function Empty({ msg }) {
  return <div className="text-center text-neutral-500 py-10 text-sm">{msg}</div>;
}
function StatusPill({ status }) {
  const m = {
    pending:   "text-amber-400 border-amber-500/40",
    approved:  "text-[#84CC16] border-[#84CC16]/40",
    fulfilled: "text-emerald-400 border-emerald-500/40",
    cancelled: "text-neutral-500 border-white/10",
  }[status] || "text-neutral-500 border-white/10";
  return <span className={`text-[10px] font-mono uppercase border rounded-sm px-1.5 py-0.5 mt-1 inline-block ${m}`}>{status}</span>;
}
