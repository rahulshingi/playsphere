import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { CalendarDays, Users, Activity, Package, Plus, ChevronRight, Handshake } from "lucide-react";
import { fmtPrice } from "@/lib/currency";
import DashboardPanel from "@/components/DashboardPanel";
import UpcomingBookingsWidget from "@/components/UpcomingBookingsWidget";
import CompanyAddressCard from "@/components/CompanyAddressCard";

export default function Dashboard() {
  const { ready, isCompanyAdmin, companyName, user } = useAuth();
  const nav = useNavigate();
  const [stats, setStats] = useState({});
  const [events, setEvents] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [sponsorship, setSponsorship] = useState({ sent: [], received: [] });

  useEffect(() => {
    if (ready && !isCompanyAdmin) { nav("/login"); return; }
    if (ready && user?.company_id) {
      Promise.all([
        api.get("/stats/company"),
        api.get(`/events?company_id=${user.company_id}`),
        api.get("/bookings"),
        api.get("/sponsorships/my-activity").catch(() => ({ data: { sent: [], received: [] } })),
      ]).then(([s, e, b, sp]) => {
        setStats(s.data); setEvents(e.data); setBookings(b.data);
        setSponsorship(sp.data || { sent: [], received: [] });
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
          <h1 className="font-display text-6xl tracking-wide mt-3">YOUR KREEDA NATION</h1>
          <div className="flex gap-2">
            <Button data-testid="dashboard-new-event" onClick={() => nav("/admin")} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
              <Plus className="w-4 h-4 mr-1" /> New tournament
            </Button>
            <Button data-testid="dashboard-browse-services" onClick={() => nav("/services")} variant="outline" className="border-white/10 bg-transparent text-white rounded-sm">Browse services</Button>
          </div>
        </div>

        <div className="mt-10">
          <DashboardPanel role="company" />
        </div>

        <div className="mt-10">
          <UpcomingBookingsWidget />
        </div>

        <div className="mt-6">
          <CompanyAddressCard />
        </div>

        <SponsorshipInbox data={sponsorship} />

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
                  <div className="font-mono">{fmtPrice(b.total_price, b.currency)}</div>
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
    accepted:  "text-[#84CC16] border-[#84CC16]/40",
    rejected:  "text-[#FF3B30] border-[#FF3B30]/40",
  }[status] || "text-neutral-500 border-white/10";
  return <span className={`text-[10px] font-mono uppercase border rounded-sm px-1.5 py-0.5 mt-1 inline-block ${m}`}>{status}</span>;
}

// Two-column sponsorship inbox — shows both interests THIS company has
// received on its own events, AND interests this company has expressed on
// other people's events (when the company_admin is also acting as a sponsor).
function SponsorshipInbox({ data }) {
  const sent = data?.sent || [];
  const received = data?.received || [];
  const total = sent.length + received.length;
  if (total === 0) return null;

  return (
    <div data-testid="sponsorship-inbox" className="mt-8 border border-[#FACC15]/30 rounded-sm bg-gradient-to-br from-[#FACC15]/5 to-transparent p-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15] flex items-center gap-1.5">
            <Handshake className="w-3.5 h-3.5" /> / Sponsorship activity
          </div>
          <div className="text-sm text-neutral-300 mt-1">
            {received.length > 0 && <span>{received.length} interest{received.length === 1 ? "" : "s"} on your events. </span>}
            {sent.length > 0 && <span>{sent.length} you&apos;ve sent as a sponsor.</span>}
          </div>
        </div>
        <Link to="/sponsorships" data-testid="sponsorship-inbox-browse" className="text-xs font-mono uppercase tracking-widest text-[#FACC15] hover:underline">Browse marketplace →</Link>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mt-4">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mb-2">Received on your events</div>
          {received.length === 0 ? (
            <div className="text-xs text-neutral-500 border border-dashed border-white/10 rounded-sm py-4 px-3 text-center">
              No sponsorship interest received yet. <Link to="/admin" className="text-[#FACC15] underline">Enable sponsorships</Link> on your next event.
            </div>
          ) : received.slice(0, 4).map((r) => (
            <Link to={`/events/${r.event_id}`} key={r.id} data-testid={`si-received-${r.id}`} className="flex items-start justify-between border-t border-white/5 py-2 px-1 hover:bg-white/[0.02]">
              <div className="min-w-0">
                <div className="text-sm truncate">{r.sponsor_company_name || "A sponsor"}</div>
                <div className="text-[10px] font-mono uppercase text-neutral-500">{r.event_name || r.event_id?.slice(0, 8)} · {r.tier_name || r.opportunity_id?.slice(0, 8)}</div>
              </div>
              <StatusPill status={r.status} />
            </Link>
          ))}
        </div>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mb-2">Sent by you as a sponsor</div>
          {sent.length === 0 ? (
            <div className="text-xs text-neutral-500 border border-dashed border-white/10 rounded-sm py-4 px-3 text-center">
              You haven&apos;t expressed interest in any sponsorship yet. <Link to="/sponsorships" className="text-[#FACC15] underline">Browse the marketplace</Link>.
            </div>
          ) : sent.slice(0, 4).map((s) => (
            <Link to={`/events/${s.event_id}`} key={s.id} data-testid={`si-sent-${s.id}`} className="flex items-start justify-between border-t border-white/5 py-2 px-1 hover:bg-white/[0.02]">
              <div className="min-w-0">
                <div className="text-sm truncate">{s.event_name || s.event_id?.slice(0, 8)}</div>
                <div className="text-[10px] font-mono uppercase text-neutral-500">{s.tier_name || s.opportunity_id?.slice(0, 8)}</div>
              </div>
              <StatusPill status={s.status} />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
