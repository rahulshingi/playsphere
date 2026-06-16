import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Activity, TrendingUp, Calendar, Users, MapPin, ShoppingCart } from "lucide-react";

const STAT_GROUPS = {
  admin: [
    { key: "events_total", label: "Events", icon: Calendar, accent: "#84CC16" },
    { key: "events_ongoing", label: "Ongoing", icon: Activity, accent: "#06B6D4" },
    { key: "companies", label: "Companies", icon: TrendingUp, accent: "#EC4899" },
    { key: "vendors_total", label: "Vendors", icon: ShoppingCart, accent: "#F59E0B" },
    { key: "vendors_pending", label: "Pending vendors", icon: Activity, accent: "#FF3B30" },
    { key: "listings_pending", label: "Pending listings", icon: Activity, accent: "#FF3B30" },
    { key: "vendor_bookings_total", label: "Ground bookings", icon: MapPin, accent: "#A855F7" },
    { key: "vendor_bookings_pending", label: "Pending bookings", icon: MapPin, accent: "#F59E0B" },
    { key: "vendor_bookings_confirmed", label: "Confirmed", icon: MapPin, accent: "#84CC16" },
    { key: "players", label: "Players", icon: Users, accent: "#06B6D4" },
    { key: "teams", label: "Teams", icon: Users, accent: "#EC4899" },
    { key: "service_bookings", label: "Service bookings", icon: ShoppingCart, accent: "#84CC16" },
  ],
  company: [
    { key: "my_events", label: "My events", icon: Calendar, accent: "#84CC16" },
    { key: "my_events_ongoing", label: "Ongoing", icon: Activity, accent: "#06B6D4" },
    { key: "my_events_upcoming", label: "Upcoming", icon: Calendar, accent: "#A855F7" },
    { key: "my_events_completed", label: "Completed", icon: Calendar, accent: "#525252" },
    { key: "my_teams", label: "My teams", icon: Users, accent: "#EC4899" },
    { key: "players_in_company", label: "Players", icon: Users, accent: "#06B6D4" },
    { key: "my_matches", label: "Matches", icon: Activity, accent: "#84CC16" },
    { key: "matches_completed", label: "Played", icon: Activity, accent: "#525252" },
    { key: "service_bookings", label: "Service bookings", icon: ShoppingCart, accent: "#F59E0B" },
    { key: "ground_bookings", label: "Ground bookings", icon: MapPin, accent: "#A855F7" },
    { key: "ground_bookings_pending", label: "Awaiting confirmation", icon: MapPin, accent: "#F59E0B" },
    { key: "ground_bookings_confirmed", label: "Confirmed", icon: MapPin, accent: "#84CC16" },
  ],
  vendor: [
    { key: "listings_total", label: "Listings", icon: ShoppingCart, accent: "#84CC16" },
    { key: "listings_approved", label: "Approved", icon: ShoppingCart, accent: "#06B6D4" },
    { key: "listings_pending", label: "Pending approval", icon: ShoppingCart, accent: "#F59E0B" },
    { key: "bookings_total", label: "Total bookings", icon: MapPin, accent: "#EC4899" },
    { key: "bookings_upcoming", label: "Upcoming", icon: Calendar, accent: "#84CC16" },
    { key: "bookings_completed", label: "Completed", icon: Activity, accent: "#525252" },
    { key: "bookings_pending", label: "New requests", icon: MapPin, accent: "#F59E0B" },
    { key: "bookings_vendor_accepted", label: "Accepted · waiting admin", icon: MapPin, accent: "#06B6D4" },
    { key: "bookings_confirmed", label: "Confirmed", icon: MapPin, accent: "#84CC16" },
    { key: "bookings_rejected", label: "Rejected", icon: Activity, accent: "#FF3B30" },
    { key: "bookings_cancelled", label: "Cancelled", icon: Activity, accent: "#525252" },
  ],
};

export default function DashboardPanel({ role }) {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    api.get(`/dashboard/${role}`).then((r) => setStats(r.data)).catch(() => setStats({}));
  }, [role]);

  if (!stats) return <div data-testid={`dashboard-${role}-loading`} className="text-neutral-500 text-sm py-8">Loading dashboard…</div>;
  const groups = STAT_GROUPS[role] || [];

  return (
    <div data-testid={`dashboard-${role}`} className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      {groups.map((g) => {
        const Icon = g.icon;
        const value = stats[g.key] ?? 0;
        return (
          <div key={g.key} data-testid={`stat-${g.key}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{g.label}</div>
              <Icon className="w-3.5 h-3.5" style={{ color: g.accent }} />
            </div>
            <div className="font-display text-4xl mt-2" style={{ color: g.accent }}>{value}</div>
          </div>
        );
      })}
    </div>
  );
}
