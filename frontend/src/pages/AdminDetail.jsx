import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { useAuth } from "@/context/AuthContext";
import { ArrowLeft, Mail, MapPin, Phone, Calendar, ShoppingBag, Users, Trophy, Star, Eye } from "lucide-react";
import { SPORT_SCHEMAS } from "@/lib/sportProfileSchema";
import { STATS_SCHEMAS } from "@/lib/sportStatsSchema";

const TYPES = {
  vendor: { path: "vendors", label: "Vendor" },
  company: { path: "companies", label: "Company" },
  player: { path: "players", label: "Player" },
};

export default function AdminDetail({ type }) {
  const { id } = useParams();
  const nav = useNavigate();
  const { ready, isPlatformAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!ready) return;
    if (!isPlatformAdmin) { nav("/login"); return; }
    api.get(`/admin/${TYPES[type].path}/${id}/detail`)
      .then((r) => setData(r.data))
      .catch((e) => setError(e.response?.data?.detail || "Failed to load"));
  }, [type, id, ready, isPlatformAdmin, nav]);

  if (!data) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white">
        <Nav />
        <div className="mx-auto max-w-6xl px-6 py-12">
          {error ? <div className="text-[#FF3B30]">{error}</div> : <div className="text-neutral-500">Loading…</div>}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Nav />
      <div className="mx-auto max-w-6xl px-6 py-10">
        <button onClick={() => nav(-1)} data-testid="admin-detail-back"
          className="inline-flex items-center gap-1 text-xs font-mono text-neutral-400 hover:text-white">
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>

        {type === "vendor" && <VendorDetail data={data} tab={tab} setTab={setTab} />}
        {type === "company" && <CompanyDetail data={data} tab={tab} setTab={setTab} />}
        {type === "player" && <PlayerDetailView data={data} tab={tab} setTab={setTab} />}
      </div>
      <Footer />
    </div>
  );
}

function TabBar({ tabs, tab, setTab }) {
  return (
    <div className="mt-6 flex flex-wrap gap-2 border-b border-white/10 pb-3">
      {tabs.map((t) => (
        <button
          key={t.k}
          data-testid={`admin-tab-${t.k}`}
          onClick={() => setTab(t.k)}
          className={`px-3 py-1.5 text-xs font-mono uppercase rounded-sm border ${
            tab === t.k ? "bg-[#84CC16] border-[#84CC16] text-black" : "border-white/10 text-neutral-400 hover:text-white"
          }`}
        >
          {t.label} {typeof t.count === "number" ? `· ${t.count}` : ""}
        </button>
      ))}
    </div>
  );
}

function KV({ label, value, icon: Icon }) {
  if (!value) return null;
  return (
    <div className="flex items-center gap-2 text-sm text-neutral-300">
      {Icon && <Icon className="w-3.5 h-3.5 text-neutral-500" />}
      <span className="font-mono text-[10px] uppercase text-neutral-500">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function VendorDetail({ data, tab, setTab }) {
  const { vendor, owner, listings, bookings, reviews, schedules } = data;
  return (
    <>
      <div className="mt-4 border border-white/10 rounded-sm bg-[#141414] p-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase text-[#EC4899]">/ Vendor</div>
            <h1 className="font-display text-3xl mt-1">{vendor.business_name}</h1>
            <div className="font-mono text-xs text-neutral-500 mt-1">{vendor.vendor_type} · {vendor.city}</div>
          </div>
          <span className={`px-3 py-1 text-[11px] font-mono uppercase rounded-sm border ${vendor.approved ? "border-[#84CC16] text-[#84CC16]" : "border-[#F59E0B] text-[#F59E0B]"}`}>
            {vendor.approved ? "Approved" : "Pending approval"}
          </span>
        </div>
        <div className="grid sm:grid-cols-2 gap-2 mt-4">
          <KV label="Contact" value={vendor.contact_name} icon={Users} />
          <KV label="Email" value={vendor.email} icon={Mail} />
          <KV label="Mobile" value={vendor.mobile} icon={Phone} />
          <KV label="Owner user" value={owner?.email} icon={Mail} />
        </div>
      </div>

      <TabBar tab={tab} setTab={setTab} tabs={[
        { k: "overview", label: "Overview" },
        { k: "listings", label: "Listings", count: listings.length },
        { k: "policies", label: "Policies" },
        { k: "schedules", label: "Schedules", count: schedules.length },
        { k: "bookings", label: "Bookings", count: bookings.length },
        { k: "reviews", label: "Reviews", count: reviews.length },
      ]} />

      <div className="mt-6">
        {tab === "overview" && <OverviewStats stats={[
          { label: "Listings", value: listings.length, icon: ShoppingBag },
          { label: "Bookings", value: bookings.length, icon: Calendar },
          { label: "Approved", value: listings.filter((L) => L.approved).length, icon: Trophy },
          { label: "Reviews", value: reviews.length, icon: Star },
        ]} />}
        {tab === "listings" && <ListingsTable listings={listings} />}
        {tab === "policies" && <PoliciesTable listings={listings} />}
        {tab === "schedules" && <SchedulesTable schedules={schedules} listings={listings} />}
        {tab === "bookings" && <BookingsTable bookings={bookings} />}
        {tab === "reviews" && <ReviewsTable reviews={reviews} />}
      </div>
    </>
  );
}

function CompanyDetail({ data, tab, setTab }) {
  const { company, members, players, bookings, events } = data;
  const isOrganiser = company.org_type === "organiser";
  return (
    <>
      <div className="mt-4 border border-white/10 rounded-sm bg-[#141414] p-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className={`font-mono text-[10px] uppercase ${isOrganiser ? "text-[#06B6D4]" : "text-[#84CC16]"}`}>/ {isOrganiser ? "Organiser" : "Company"}</div>
            <h1 className="font-display text-3xl mt-1">{company.name}</h1>
            <div className="font-mono text-xs text-neutral-500 mt-1">{company.slug || ""} · {company.industry || (isOrganiser ? "Tournament organiser" : "—")}</div>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 gap-2 mt-4">
          <KV label="Contact email" value={company.contact_email} icon={Mail} />
          <KV label="City" value={company.city} icon={MapPin} />
        </div>
      </div>

      <TabBar tab={tab} setTab={setTab} tabs={[
        { k: "overview", label: "Overview" },
        { k: "members", label: isOrganiser ? "Owner & staff" : "Team members", count: members.length },
        { k: "players", label: "Player profiles", count: players.length },
        { k: "events", label: "Events", count: events.length },
        { k: "bookings", label: "Bookings", count: bookings.length },
      ]} />

      <div className="mt-6">
        {tab === "overview" && <OverviewStats stats={[
          { label: "Team", value: members.length, icon: Users },
          { label: "Players", value: players.length, icon: Users },
          { label: "Events", value: events.length, icon: Trophy },
          { label: "Bookings", value: bookings.length, icon: Calendar },
        ]} />}
        {tab === "members" && <UsersTable users={members} />}
        {tab === "players" && <PlayersTable players={players} />}
        {tab === "events" && <EventsTable events={events} />}
        {tab === "bookings" && <BookingsTable bookings={bookings} />}
      </div>
    </>
  );
}

function PlayerDetailView({ data, tab, setTab }) {
  const { player, user, company, teams, events, reviews } = data;
  const interested = player.interested_sports || [];
  return (
    <>
      <div className="mt-4 border border-white/10 rounded-sm bg-[#141414] p-6">
        <div className="grid md:grid-cols-[180px_1fr] gap-6 items-start">
          {/* Profile photo */}
          <div className="aspect-square rounded-sm overflow-hidden bg-black/40 border border-white/10">
            <img
              src={player.photo_url || "https://images.pexels.com/photos/2216610/pexels-photo-2216610.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"}
              alt={player.name} className="w-full h-full object-cover"
              data-testid="admin-player-photo"
            />
          </div>
          <div className="min-w-0">
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <div className="font-mono text-[10px] uppercase text-[#06B6D4]">/ Player</div>
                <h1 className="font-display text-3xl mt-1" data-testid="admin-player-name">{player.name}</h1>
                <div className="font-mono text-xs text-neutral-500 mt-1">
                  {player.city || ""}{player.city ? " · " : ""}{interested.map((s) => SPORT_SCHEMAS[s]?.label || s).join(", ") || "—"}
                </div>
              </div>
              <div className="text-right">
                <div className="font-display text-2xl text-[#84CC16] flex items-center gap-1.5 justify-end">
                  <Eye className="w-4 h-4" /> {player.view_count || 0}
                </div>
                <div className="text-[10px] font-mono uppercase text-neutral-500 tracking-widest">Profile views</div>
              </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-2 mt-4">
              <KV label="Email" value={user?.email} icon={Mail} />
              <KV label="Mobile" value={player.mobile} icon={Phone} />
              <KV label="Company" value={company?.name || "Independent"} icon={Users} />
              <KV label="Date of birth" value={player.dob} icon={Calendar} />
              <KV label="Height" value={player.height_cm ? `${player.height_cm} cm` : null} icon={Trophy} />
              <KV label="Weight" value={player.weight_kg ? `${player.weight_kg} kg` : null} icon={Trophy} />
            </div>
            {player.bio && (
              <div className="mt-4 pt-4 border-t border-white/10">
                <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-1.5">/ Bio</div>
                <p className="text-sm text-neutral-300 whitespace-pre-wrap" data-testid="admin-player-bio">{player.bio}</p>
              </div>
            )}
          </div>
        </div>

        {/* Per-sport profile cards */}
        {interested.length > 0 && (
          <div className="mt-6 space-y-3">
            {interested.map((s) => {
              const sp = player.sport_profiles?.[s] || {};
              const profileSchema = SPORT_SCHEMAS[s]?.fields || [];
              const statsSchema = STATS_SCHEMAS?.[s]?.manual || [];
              const stats = player.lifetime_stats?.[s] || {};
              const profileEntries = profileSchema.filter((f) => sp[f.key] !== undefined && sp[f.key] !== "" && sp[f.key] !== null);
              const statsEntries = statsSchema.filter((f) => stats[f.key] !== undefined && stats[f.key] !== "" && stats[f.key] !== null);
              if (!profileEntries.length && !statsEntries.length) return null;
              return (
                <div key={s} data-testid={`admin-player-sport-${s}`} className="border border-white/10 rounded-sm bg-black/30 p-4">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16] mb-3">/ {(SPORT_SCHEMAS[s]?.label || s).replace(/-/g, " ")} profile</div>
                  {profileEntries.length > 0 && (
                    <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2 text-sm">
                      {profileEntries.map((f) => (
                        <div key={f.key}>
                          <div className="text-[10px] font-mono uppercase text-neutral-500">{(f.label || f.key).replace(/_/g, " ")}</div>
                          <div className="text-neutral-200 break-words">{Array.isArray(sp[f.key]) ? sp[f.key].join(", ") : String(sp[f.key])}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {statsEntries.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-white/10">
                      <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-2">/ Lifetime career stats</div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {statsEntries.map((f) => (
                          <div key={f.key}>
                            <div className="text-[10px] font-mono uppercase text-neutral-500">{(f.label || f.key).replace(/_/g, " ")}</div>
                            <div className="font-display text-2xl text-[#84CC16]">{stats[f.key]}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <TabBar tab={tab} setTab={setTab} tabs={[
        { k: "overview", label: "Overview" },
        { k: "teams", label: "Teams", count: teams.length },
        { k: "events", label: "Events", count: events.length },
        { k: "reviews", label: "Reviews authored", count: reviews.length },
      ]} />

      <div className="mt-6">
        {tab === "overview" && <OverviewStats stats={[
          { label: "Teams", value: teams.length, icon: Users },
          { label: "Events", value: events.length, icon: Trophy },
          { label: "Reviews", value: reviews.length, icon: Star },
          { label: "Profile views", value: player.view_count || 0, icon: Eye },
        ]} />}
        {tab === "teams" && <TeamsTable teams={teams} />}
        {tab === "events" && <EventsTable events={events} />}
        {tab === "reviews" && <ReviewsTable reviews={reviews} />}
      </div>
    </>
  );
}

function OverviewStats({ stats }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {stats.map((s) => {
        const Icon = s.icon;
        return (
          <div key={s.label} className="border border-white/10 rounded-sm bg-[#141414] p-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase text-neutral-500">{s.label}</span>
              {Icon && <Icon className="w-4 h-4 text-neutral-600" />}
            </div>
            <div className="font-display text-3xl mt-2">{s.value}</div>
          </div>
        );
      })}
    </div>
  );
}

function Table({ headers, rows, empty }) {
  if (!rows.length) return <div className="text-sm text-neutral-500 border border-dashed border-white/10 rounded-sm p-6 text-center">{empty}</div>;
  return (
    <div className="overflow-x-auto border border-white/10 rounded-sm bg-[#141414]">
      <table className="w-full text-xs">
        <thead className="bg-black/40 text-neutral-500 font-mono uppercase">
          <tr>{headers.map((h) => <th key={h} className="text-left px-3 py-2">{h}</th>)}</tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  );
}

function ListingsTable({ listings }) {
  return <Table headers={["Title", "City", "Price", "Approved", "Active"]} empty="No listings"
    rows={listings.map((L) => (
      <tr key={L.id} data-testid={`detail-listing-${L.id}`} className="border-t border-white/5">
        <td className="px-3 py-2">{L.title}</td>
        <td className="px-3 py-2">{L.city}</td>
        <td className="px-3 py-2 font-mono">{L.currency} {L.price}/{L.price_unit}</td>
        <td className="px-3 py-2"><span className={L.approved ? "text-[#84CC16]" : "text-[#F59E0B]"}>{L.approved ? "Yes" : "No"}</span></td>
        <td className="px-3 py-2">{L.active ? "Yes" : "No"}</td>
      </tr>
    ))} />;
}

function PoliciesTable({ listings }) {
  return <Table headers={["Listing", "Cancellation", "Reschedule"]} empty="No policies set"
    rows={listings.map((L) => {
      const cp = L.cancellation_policy;
      const rp = L.reschedule_policy;
      return (
        <tr key={L.id} data-testid={`detail-policy-${L.id}`} className="border-t border-white/5">
          <td className="px-3 py-2">{L.title}</td>
          <td className="px-3 py-2 font-mono">
            {cp ? `Full≥${cp.full_refund_hours_before}h · ${cp.partial_refund_percent}% ≥${cp.partial_refund_hours_before}h · No<${cp.no_refund_window_hours}h` : "—"}
          </td>
          <td className="px-3 py-2 font-mono">
            {rp ? `Free≥${rp.free_reschedule_hours_before}h · max ${rp.max_reschedules} · fee ${L.currency} ${rp.fee_amount}` : "—"}
          </td>
        </tr>
      );
    })} />;
}

function SchedulesTable({ schedules, listings }) {
  const title = (id) => listings.find((L) => L.id === id)?.title || id.slice(0, 8);
  return <Table headers={["Listing", "Hours", "Peak", "Happy hours"]} empty="No schedules configured"
    rows={schedules.map((s) => (
      <tr key={s.listing_id} className="border-t border-white/5">
        <td className="px-3 py-2">{title(s.listing_id)}</td>
        <td className="px-3 py-2 font-mono">{s.opening_time}–{s.closing_time}</td>
        <td className="px-3 py-2 font-mono">{(s.peak_hours || []).join(", ") || "—"} ({s.peak_price_factor || 1}x)</td>
        <td className="px-3 py-2 font-mono">{(s.happy_hours || []).map((h) => `${h.label} ${h.start}-${h.end} (${h.factor}x)`).join("; ") || "—"}</td>
      </tr>
    ))} />;
}

function BookingsTable({ bookings }) {
  return <Table headers={["Date", "Slot", "Listing", "Company", "Status", "Total"]} empty="No bookings"
    rows={bookings.map((b) => (
      <tr key={b.id} data-testid={`detail-booking-${b.id}`} className="border-t border-white/5">
        <td className="px-3 py-2 font-mono">{b.requested_date}</td>
        <td className="px-3 py-2 font-mono">{b.start_time}–{b.end_time}</td>
        <td className="px-3 py-2">{b.listing_title}</td>
        <td className="px-3 py-2">{b.company_name}</td>
        <td className="px-3 py-2"><span className="font-mono text-[10px] uppercase">{b.status}</span></td>
        <td className="px-3 py-2 font-mono">{b.currency} {b.total}</td>
      </tr>
    ))} />;
}

function ReviewsTable({ reviews }) {
  return <Table headers={["Rating", "Author", "Status", "Text"]} empty="No reviews"
    rows={reviews.map((r) => (
      <tr key={r.id} className="border-t border-white/5">
        <td className="px-3 py-2 font-mono">{r.rating}/5</td>
        <td className="px-3 py-2">{r.author_name}</td>
        <td className="px-3 py-2"><span className="font-mono text-[10px] uppercase">{r.status}</span></td>
        <td className="px-3 py-2 text-neutral-400 max-w-md truncate">{r.text}</td>
      </tr>
    ))} />;
}

function UsersTable({ users }) {
  return <Table headers={["Email", "Role", "Name"]} empty="No team members"
    rows={users.map((u) => (
      <tr key={u.id} className="border-t border-white/5">
        <td className="px-3 py-2">{u.email}</td>
        <td className="px-3 py-2"><span className="font-mono text-[10px] uppercase">{u.role}</span></td>
        <td className="px-3 py-2 text-neutral-400">{u.name || "—"}</td>
      </tr>
    ))} />;
}

function PlayersTable({ players }) {
  return <Table headers={["Name", "City", "Sports", "Mobile"]} empty="No players"
    rows={players.map((p) => (
      <tr key={p.id} className="border-t border-white/5">
        <td className="px-3 py-2"><Link to={`/platform-admin/players/${p.id}`} data-testid={`detail-player-${p.id}`} className="text-[#84CC16] hover:underline">{p.name}</Link></td>
        <td className="px-3 py-2">{p.city || "—"}</td>
        <td className="px-3 py-2 text-neutral-400">{(p.sports || []).join(", ")}</td>
        <td className="px-3 py-2 font-mono">{p.mobile || "—"}</td>
      </tr>
    ))} />;
}

function EventsTable({ events }) {
  return <Table headers={["Name", "Sport", "Format", "Created"]} empty="No events"
    rows={events.map((e) => (
      <tr key={e.id} className="border-t border-white/5">
        <td className="px-3 py-2"><Link to={`/events/${e.id}`} className="text-[#84CC16] hover:underline">{e.name}</Link></td>
        <td className="px-3 py-2">{e.sport}</td>
        <td className="px-3 py-2 text-neutral-400">{e.format}</td>
        <td className="px-3 py-2 font-mono text-neutral-500">{(e.created_at || "").slice(0, 10)}</td>
      </tr>
    ))} />;
}

function TeamsTable({ teams }) {
  return <Table headers={["Team", "Event", "Members"]} empty="Not on any team"
    rows={teams.map((t) => (
      <tr key={t.id} className="border-t border-white/5">
        <td className="px-3 py-2">{t.name}</td>
        <td className="px-3 py-2"><Link to={`/events/${t.event_id}`} className="text-[#84CC16] hover:underline">{t.event_id.slice(0, 8)}</Link></td>
        <td className="px-3 py-2 font-mono">{(t.members || []).length}</td>
      </tr>
    ))} />;
}
