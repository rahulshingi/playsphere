import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { LogOut, Shield } from "lucide-react";

const LOGO_URL = "https://customer-assets.emergentagent.com/job_live-scoring-hub-5/artifacts/4vqrrfy3_Playsphere%20logo%20main.png";

const navItems = [
  { to: "/", label: "Home" },
  { to: "/events", label: "Events" },
  { to: "/teams", label: "Teams" },
  { to: "/standings", label: "Standings" },
  { to: "/sponsors", label: "Sponsors" },
];

export default function Nav() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header
      data-testid="site-nav"
      className="sticky top-0 z-50 w-full backdrop-blur-xl bg-black/70 border-b border-white/10"
    >
      <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
        <Link to="/" data-testid="nav-logo" className="flex items-center gap-3">
          <img src={LOGO_URL} alt="PlaySphere" className="w-11 h-11 object-contain" />
          <div className="leading-none hidden sm:block">
            <div className="font-display text-2xl tracking-wider">
              <span className="text-white">PLAY</span><span className="text-[#84CC16]">SPHERE</span>
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

        <nav className="hidden md:flex items-center gap-1">
          {navItems.map((n) => (
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
          {isAdmin && (
            <NavLink
              to="/admin"
              data-testid="nav-link-admin"
              className={({ isActive }) =>
                `px-3 py-2 text-sm font-medium rounded-sm flex items-center gap-1 transition-colors ${
                  isActive ? "text-[#84CC16]" : "text-[#84CC16]/80 hover:text-[#84CC16]"
                }`
              }
            >
              <Shield className="w-3.5 h-3.5" /> Admin
            </NavLink>
          )}
        </nav>

        <div className="flex items-center gap-2">
          {user && user !== false ? (
            <>
              <span data-testid="nav-user-email" className="hidden sm:block text-xs text-neutral-400 font-mono">
                {user.email}
              </span>
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
                data-testid="nav-register-team-btn"
                size="sm"
                onClick={() => navigate("/register-team")}
                className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"
              >
                Register Team
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
