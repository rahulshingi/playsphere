import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { LogOut, Shield, Briefcase, Crown, User, Store } from "lucide-react";

const LOGO_URL = "/playsphere-mark.png";

const publicLinks = [
  { to: "/", label: "Home" },
  { to: "/events", label: "Events" },
  { to: "/services", label: "Services" },
  { to: "/about", label: "About" },
];

export default function Nav() {
  const { user, isCompanyAdmin, isPlatformAdmin, isPlayer, isVendor, companyName, logout } = useAuth();
  const navigate = useNavigate();
  const isAuthed = user && user !== false;

  return (
    <header
      data-testid="site-nav"
      className="sticky top-0 z-50 w-full backdrop-blur-xl bg-black/70 border-b border-white/10"
    >
      <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between gap-4">
        <Link to="/" data-testid="nav-logo" className="flex items-center gap-3 shrink-0">
          <img src={LOGO_URL} alt="Kreeda Nation" className="w-11 h-11 object-contain" />
          <div className="leading-none hidden lg:block">
            <div className="font-brand text-2xl">
              <span className="text-white">KREEDA</span><span className="text-[#84CC16]"> NATION</span>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-widest mt-1">
              <span className="text-[#EC4899]">compete</span>
              <span className="text-neutral-500"> · </span>
              <span className="text-[#84CC16]">connect</span>
              <span className="text-neutral-500"> · </span>
              <span className="text-[#06B6D4]">grow</span>
            </div>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-0.5 flex-1 justify-center">
          {publicLinks.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              data-testid={`nav-link-${n.label.toLowerCase()}`}
              className={({ isActive }) =>
                `px-3 py-2 text-sm font-medium rounded-sm transition-colors ${
                  isActive ? "text-white bg-white/5" : "text-neutral-400 hover:text-white"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
          {isCompanyAdmin && (
            <>
              <NavLink to="/dashboard" data-testid="nav-link-dashboard" className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-sm flex items-center gap-1 ${isActive ? "text-[#84CC16]" : "text-[#84CC16]/80 hover:text-[#84CC16]"}`}>
                <Briefcase className="w-3.5 h-3.5" /> Dashboard
              </NavLink>
              <NavLink to="/hire" data-testid="nav-link-hire" className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-sm ${isActive ? "text-white bg-white/5" : "text-neutral-400 hover:text-white"}`}>
                Hire
              </NavLink>
              <NavLink to="/admin" data-testid="nav-link-admin" className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-sm flex items-center gap-1 ${isActive ? "text-[#84CC16]" : "text-[#84CC16]/80 hover:text-[#84CC16]"}`}>
                <Shield className="w-3.5 h-3.5" /> Manage
              </NavLink>
            </>
          )}
          {isPlayer && (
            <>
              <NavLink to="/players/me" data-testid="nav-link-my-profile" className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-sm flex items-center gap-1 ${isActive ? "text-[#84CC16]" : "text-[#84CC16]/80 hover:text-[#84CC16]"}`}>
                <User className="w-3.5 h-3.5" /> My profile
              </NavLink>
              <NavLink to="/players/profiles" data-testid="nav-link-find-players" className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-sm ${isActive ? "text-white bg-white/5" : "text-neutral-400 hover:text-white"}`}>
                Find players
              </NavLink>
            </>
          )}
          {isVendor && (
            <>
              <NavLink to="/vendor/dashboard" data-testid="nav-link-vendor" className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-sm flex items-center gap-1 ${isActive ? "text-[#EC4899]" : "text-[#EC4899]/80 hover:text-[#EC4899]"}`}>
                <Store className="w-3.5 h-3.5" /> Vendor
              </NavLink>
              <NavLink to="/bookings" data-testid="nav-link-vendor-bookings" className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-sm ${isActive ? "text-white bg-white/5" : "text-neutral-400 hover:text-white"}`}>
                Requests
              </NavLink>
            </>
          )}
          {isPlatformAdmin && (
            <NavLink to="/platform-admin" data-testid="nav-link-platform-admin" className={({ isActive }) => `px-3 py-2 text-sm font-medium rounded-sm flex items-center gap-1 ${isActive ? "text-[#FF3B30]" : "text-[#FF3B30]/80 hover:text-[#FF3B30]"}`}>
              <Crown className="w-3.5 h-3.5" /> HQ
            </NavLink>
          )}
        </nav>

        <div className="flex items-center gap-2 shrink-0">
          {isAuthed ? (
            <>
              <div className="hidden sm:flex flex-col items-end leading-tight">
                {companyName && <span className="text-xs font-mono text-[#84CC16]">{companyName}</span>}
                <span data-testid="nav-user-email" className="text-[10px] text-neutral-500 font-mono">{user.email}</span>
              </div>
              <Button
                data-testid="nav-logout-btn"
                variant="ghost"
                size="sm"
                onClick={async () => { await logout(); navigate("/"); }}
                className="text-neutral-400 hover:text-white"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </>
          ) : (
            <>
              <Button
                data-testid="nav-login-btn"
                variant="ghost"
                size="sm"
                onClick={() => navigate("/login")}
                className="text-neutral-300 hover:text-white"
              >
                Sign in
              </Button>
              <Button
                data-testid="nav-signup-company-btn"
                size="sm"
                onClick={() => navigate("/signup-company")}
                className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"
              >
                For Companies
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
