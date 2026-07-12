import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Link } from "react-router-dom";
import { fmtPrice } from "@/lib/currency";
import { BarChart3, TrendingUp, Store, Wallet } from "lucide-react";

/**
 * Platform admin bookings analytics (Task 44 · Feb 2026).
 *
 * Displays booking counts + commission for PLATFORM (online) bookings, alongside
 * a holistic count of vendor OFFLINE bookings (which do not incur commission
 * but count toward vendor utilisation).
 *
 * Ranges: Day / Week / Month — via `GET /admin/bookings-analytics?range=...`.
 */
const RANGE_TABS = [
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
];

export default function BookingsAnalyticsTab() {
  const [range, setRange] = useState("week");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get(`/admin/bookings-analytics?range=${range}`)
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [range]);

  return (
    <div data-testid="bookings-analytics" className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-neutral-500">
            <BarChart3 className="w-3 h-3 text-[#84CC16]" /> / Bookings analytics
          </div>
          <div className="font-display text-3xl tracking-wide mt-1">
            Commission &amp; utilisation
          </div>
        </div>
        <div className="flex gap-1">
          {RANGE_TABS.map((t) => (
            <button
              key={t.key}
              data-testid={`ba-range-${t.key}`}
              onClick={() => setRange(t.key)}
              className={`px-3 py-1.5 text-xs font-mono uppercase tracking-widest rounded-sm border ${range === t.key ? "bg-[#84CC16] border-[#84CC16] text-black" : "border-white/10 text-neutral-400 hover:bg-white/5"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="text-xs text-neutral-500 font-mono">Loading…</div>}

      {data && (
        <>
          {/* Totals cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard icon={<Store className="w-3 h-3" />} label="Platform bookings" value={data.totals.online_bookings} testid="ba-online-count" accent="#84CC16" />
            <StatCard icon={<Wallet className="w-3 h-3" />} label="Platform revenue" value={fmtPrice(data.totals.online_revenue, "INR")} testid="ba-online-revenue" accent="#06B6D4" />
            <StatCard icon={<TrendingUp className="w-3 h-3" />} label="Commission earned" value={fmtPrice(data.totals.commission_earned, "INR")} testid="ba-commission" accent="#EC4899" highlight />
            <StatCard icon={<Store className="w-3 h-3" />} label="Offline bookings" value={data.totals.offline_bookings} testid="ba-offline-count" accent="#FACC15" />
            <StatCard icon={<Wallet className="w-3 h-3" />} label="Offline revenue" value={fmtPrice(data.totals.offline_revenue, "INR")} testid="ba-offline-revenue" accent="#FACC15" />
          </div>

          {/* Per-vendor rollup */}
          <div className="border border-white/10 rounded-sm bg-[#0f0f0f]">
            <div className="p-4 border-b border-white/10 font-mono text-[10px] uppercase tracking-widest text-neutral-500">
              / Per-vendor rollup — commission excludes offline bookings
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
                  <tr>
                    <th className="text-left px-4 py-3">Vendor</th>
                    <th className="text-left px-3 py-3">Rate</th>
                    <th className="text-right px-3 py-3">Platform bookings</th>
                    <th className="text-right px-3 py-3">Platform revenue</th>
                    <th className="text-right px-3 py-3">Commission earned</th>
                    <th className="text-right px-3 py-3">Offline bookings</th>
                    <th className="text-right px-3 py-3">Offline revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_vendor.length === 0 && (
                    <tr><td colSpan={7} className="text-center py-10 text-neutral-500 text-xs">No bookings in this range.</td></tr>
                  )}
                  {data.by_vendor.map((v) => (
                    <tr key={v.vendor_id} data-testid={`ba-vendor-${v.vendor_id}`} className="border-t border-white/5 hover:bg-white/[0.02]">
                      <td className="px-4 py-3 text-neutral-200">{v.business_name}</td>
                      <td className="px-3 py-3 font-mono text-[10px] text-neutral-400">
                        {v.commission_percent}% <span className="text-neutral-600">or</span> ₹{v.commission_min_flat} <span className="text-neutral-600">min</span>
                      </td>
                      <td className="px-3 py-3 text-right font-mono">{v.online_bookings}</td>
                      <td className="px-3 py-3 text-right font-mono">{fmtPrice(v.online_revenue, "INR")}</td>
                      <td className="px-3 py-3 text-right font-mono text-[#EC4899] font-semibold">{fmtPrice(v.commission, "INR")}</td>
                      <td className="px-3 py-3 text-right font-mono">{v.offline_bookings}</td>
                      <td className="px-3 py-3 text-right font-mono">{fmtPrice(v.offline_revenue, "INR")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Daily time series */}
          {data.timeseries.length > 0 && (
            <div className="border border-white/10 rounded-sm bg-[#0f0f0f] p-5">
              <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-4">/ Daily breakdown</div>
              <table className="w-full text-xs">
                <thead className="font-mono text-[10px] uppercase text-neutral-500">
                  <tr>
                    <th className="text-left py-2">Date</th>
                    <th className="text-right py-2">Platform</th>
                    <th className="text-right py-2">Offline</th>
                    <th className="text-right py-2">Commission</th>
                  </tr>
                </thead>
                <tbody>
                  {data.timeseries.map((t) => (
                    <tr key={t.date} className="border-t border-white/5">
                      <td className="py-2 font-mono">{t.date}</td>
                      <td className="py-2 text-right font-mono text-[#84CC16]">{t.online}</td>
                      <td className="py-2 text-right font-mono text-[#FACC15]">{t.offline}</td>
                      <td className="py-2 text-right font-mono text-[#EC4899]">{fmtPrice(t.commission, "INR")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <div>
        <Link to="/bookings" className="text-[#84CC16] hover:underline text-xs font-mono">→ Manage all bookings</Link>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, testid, accent, highlight }) {
  return (
    <div data-testid={testid} className={`border rounded-sm p-4 bg-[#141414] ${highlight ? "border-[#EC4899]/40" : "border-white/10"}`}>
      <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest" style={{ color: accent }}>
        {icon} {label}
      </div>
      <div className={`mt-2 ${highlight ? "font-display text-3xl" : "font-display text-2xl"} tracking-wide text-white`}>
        {value}
      </div>
    </div>
  );
}
