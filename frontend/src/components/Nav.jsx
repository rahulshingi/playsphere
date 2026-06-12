import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { LogOut, Shield, Trophy } from "lucide-react";

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
        <Link to="/" data-testid="nav-logo" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-sm bg-[#007AFF] grid place-items-center">
            <Trophy className="w-4 h-4 text-white" />
          </div>
          <div className="leading-none">
            <div className="font-display text-2xl tracking-wider text-white">PLAYSPHERE</div>
            <div className="text-[10px] font-mono uppercase text-neutral-400 tracking-widest">
              compete · connect · grow
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
                  isActive ? "text-[#007AFF]" : "text-[#007AFF]/80 hover:text-[#007AFF]"
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
                className="bg-[#007AFF] hover:bg-[#0066d6] text-white rounded-sm"
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
