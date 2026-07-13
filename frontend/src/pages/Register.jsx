import { Link, useNavigate } from "react-router-dom";
import Nav from "@/components/Nav";
import { Building2, Trophy, User, Handshake, Store } from "lucide-react";

/**
 * Register — role picker (Feb 28, 2026).
 *
 * The previous generic 3-field form silently created a "viewer" account that
 * couldn't do anything. Now we ask WHO the user is first and route to the
 * appropriate signup flow (each collects the role-specific fields — company
 * name for HR/Organiser, sport preferences for Player, brand info for Sponsor).
 */
const ROLES = [
  {
    key: "company",
    to: "/signup-company",
    icon: Building2,
    label: "Company HR",
    tag: "For corporate teams",
    desc: "Register your company to host tournaments, roster teams, and manage employee wellness events.",
    color: "#84CC16",
  },
  {
    key: "organiser",
    to: "/signup-organiser",
    icon: Trophy,
    label: "Event Organiser",
    tag: "Independent event owner",
    desc: "Run corporate sports events, invite companies, and monetise your tournaments.",
    color: "#06B6D4",
  },
  {
    key: "player",
    to: "/players/signup",
    icon: User,
    label: "Player",
    tag: "Individual athlete",
    desc: "Build a universal sports profile, discover events, and get scouted.",
    color: "#EC4899",
  },
  {
    key: "sponsor",
    to: "/sponsor/signup",
    icon: Handshake,
    label: "Sponsor",
    tag: "Brand / sponsor",
    desc: "Discover events and companies to sponsor — sports, wellness, community.",
    color: "#F59E0B",
  },
  {
    key: "vendor",
    to: "/vendor/signup",
    icon: Store,
    label: "Vendor / Service Provider",
    tag: "Grounds, courts, coaches",
    desc: "List your venue, coaching, referee, gym or studio services and get discovered.",
    color: "#8B5CF6",
  },
];

export default function Register() {
  const nav = useNavigate();
  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-5xl mx-auto px-6 py-16">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Create account</div>
        <h1 className="font-display text-4xl md:text-5xl tracking-wide mt-2">JOIN KREEDA NATION</h1>
        <p className="text-neutral-400 mt-3 text-sm max-w-2xl">
          Pick the role that best describes you — we&rsquo;ll take you to the right signup form so you land with the correct dashboard and access.
        </p>

        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="register-role-grid">
          {ROLES.map((r) => {
            const Icon = r.icon;
            return (
              <button
                key={r.key}
                data-testid={`register-role-${r.key}`}
                onClick={() => nav(r.to)}
                className="group text-left bg-[#141414] border border-white/10 rounded-xl p-6 hover:border-white/30 transition-colors flex flex-col gap-3"
                style={{ boxShadow: `0 0 0 0 ${r.color}` }}
              >
                <div className="flex items-center justify-between">
                  <div
                    className="w-11 h-11 rounded-lg flex items-center justify-center"
                    style={{ background: `${r.color}20`, color: r.color }}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 group-hover:text-white transition-colors">
                    {r.tag}
                  </span>
                </div>
                <div className="text-lg font-semibold text-white">{r.label}</div>
                <div className="text-sm text-neutral-400 leading-relaxed">{r.desc}</div>
                <div
                  className="text-xs font-mono uppercase mt-2 opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ color: r.color }}
                >
                  Continue →
                </div>
              </button>
            );
          })}
        </div>

        <p className="text-xs text-neutral-500 mt-10 text-center">
          Already a member? <Link to="/login" className="text-[#84CC16] hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
