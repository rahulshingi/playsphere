import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { LogOut, Shield, Briefcase, Crown, User, Store, Menu, X, BookOpen, ChevronDown, ScanLine, ToggleRight, ToggleLeft } from "lucide-react";
import { getRoleGuide } from "@/lib/guides";

const LOGO_URL = "/kreeda-mark.png";

const publicLinks = [
  { to: "/", label: "Home" },
  { to: "/events", label: "Events" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

// Extra link injected only for HR / Organiser roles — the new Corporate
// Services (RFQ) module replaces the old public /services page.
const CORPORATE_SERVICES_LINK = { to: "/corporate-services", label: "Corporate Services" };

/**
 * Each role exposes a `primary` list (rendered horizontally in the header) and
 * an optional `more` list (folded into the user-menu dropdown). Keep primary at
 * 2-3 items max to avoid horizontal scroll on HR / admin accounts.
 *
 * When `inPlayerMode` is true (dual-role user has flipped to player view via
 * the nav dropdown), we intentionally SKIP the primary-role branches and emit
 * ONLY the player links — that's what keeps the nav clean.
 */
function roleLinks({ isCompanyAdmin, isPlayer, isVendor, isSponsor, isPlatformAdmin, isScorer, inPlayerMode }) {
  const primary = [];
  const more = [];
  // Player-mode collapse: hide every other role's links so the header shows
  // only the player experience while the user is checked-in as a player.
  const suppressOther = inPlayerMode && isPlayer;
  if (isCompanyAdmin && !suppressOther) {
    primary.push({ to: "/dashboard", label: "Dashboard", icon: Briefcase, accent: "#84CC16" });
    primary.push({ to: "/admin", label: "Manage", icon: Shield, accent: "#84CC16" });
    more.push({ to: CORPORATE_SERVICES_LINK.to, label: CORPORATE_SERVICES_LINK.label, icon: Store, accent: "#06B6D4" });
    more.push({ to: "/rfqs", label: "My RFQs", accent: "#06B6D4" });
    more.push({ to: "/hire", label: "Hire vendors", icon: Store });
    more.push({ to: "/my-memberships", label: "Memberships", accent: "#EC4899" });
    more.push({ to: "/players/profiles", label: "Players", icon: User });
    more.push({ to: "/sponsors/me", label: "Sponsor hub", accent: "#FACC15" });
  }
  if (isPlayer) {
    primary.push({ to: "/players/me", label: "My profile", icon: User, accent: "#84CC16" });
    primary.push({ to: "/players/check-in", label: "Check-in", icon: ScanLine, accent: "#06B6D4" });
    primary.push({ to: "/admin", label: "Host match", icon: Shield, accent: "#84CC16" });
    more.push({ to: "/hire", label: "Hire vendors", icon: Store });
    more.push({ to: "/bookings", label: "My bookings" });
    more.push({ to: "/players/profiles", label: "Find players" });
    more.push({ to: "/my-memberships", label: "Memberships", accent: "#EC4899" });
  }
  if (isVendor && !suppressOther) {
    primary.push({ to: "/vendor/dashboard", label: "Dashboard", icon: Store, accent: "#EC4899" });
    primary.push({ to: "/bookings", label: "Requests" });
  }
  if (isSponsor && !suppressOther) {
    primary.push({ to: "/sponsors/me", label: "Sponsor profile", icon: Briefcase, accent: "#FACC15" });
    primary.push({ to: "/sponsorships", label: "Sponsorships" });
  }
  if (isScorer && !suppressOther) {
    primary.push({ to: "/scorer/dashboard", label: "Scorer", icon: Shield, accent: "#06B6D4" });
  }
  if (isPlatformAdmin && !suppressOther) {
    primary.push({ to: "/platform-admin", label: "HQ", icon: Crown, accent: "#FF3B30" });
  }
  // Dual-role users (e.g. HR with `also_player=true`) can match multiple
  // branches above — dedupe by target URL so the same link never renders
  // twice in the header or dropdown.
  const dedupe = (list) => {
    const seen = new Set();
    return list.filter((l) => (seen.has(l.to) ? false : (seen.add(l.to), true)));
  };
  return { primary: dedupe(primary), more: dedupe(more) };
}

function DesktopLink({ link }) {
  const Icon = link.icon;
  const accent = link.accent;
  return (
    <NavLink
      to={link.to}
      end={link.to === "/"}
      data-testid={`nav-link-${link.label.toLowerCase().replace(/\s/g, "-")}`}
      className={({ isActive }) =>
        `px-3 py-2 text-sm font-medium rounded-sm transition-colors flex items-center gap-1 ${
          accent
            ? isActive
              ? "text-white"
              : "hover:text-white"
            : isActive
              ? "text-white bg-white/5"
              : "text-neutral-400 hover:text-white"
        }`
      }
      style={accent ? { color: accent } : undefined}
    >
      {Icon && <Icon className="w-3.5 h-3.5" />}
      {link.label}
    </NavLink>
  );
}

export default function Nav() {
  const { user, isCompanyAdmin, isPlatformAdmin, isPlayer, isVendor, isSponsor, isScorer, companyName, logout, inPlayerMode, setActiveMode, activeMode } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isAuthed = user && user !== false;
  const roles = { isCompanyAdmin, isPlayer, isVendor, isSponsor, isPlatformAdmin, isScorer, inPlayerMode };
  const { primary: primaryRoleLinks, more: moreRoleLinks } = roleLinks(roles);
  const allRoleLinks = [...primaryRoleLinks, ...moreRoleLinks];  // used by mobile drawer
  const guide = isAuthed ? getRoleGuide(user.role) : null;

  const closeMobile = () => setMobileOpen(false);

  // Corporate-style header: when authenticated, only show the role's PRIMARY
  // workspace links in the top bar; secondary items collapse into the right-side
  // user-menu dropdown. Unauthed visitors keep the full marketing nav.
  const visiblePublicLinks = isAuthed
    ? publicLinks.filter((l) => l.to === "/" || l.to === "/events")
    : publicLinks;

  return (
    <header
      data-testid="site-nav"
      className="sticky top-0 z-50 w-full backdrop-blur-xl bg-black/70 border-b border-white/10"
    >
      {/* Persistent "Player mode" strip — reminds dual-role users their nav
          is currently collapsed to player-only, with a one-tap way back. */}
      {inPlayerMode && user.role !== "player" && (
        <div data-testid="player-mode-strip" className="bg-[#84CC16]/15 border-b border-[#84CC16]/30 text-[#84CC16] text-[11px] font-mono uppercase tracking-widest flex items-center justify-center gap-3 py-1.5 px-4">
          <User className="w-3 h-3" />
          <span>You&apos;re in player mode</span>
          <button
            data-testid="player-mode-strip-exit"
            onClick={() => {
              setActiveMode("primary");
              if (isVendor) navigate("/vendor/dashboard");
              else if (isSponsor) navigate("/sponsors/me");
              else if (isPlatformAdmin) navigate("/platform-admin");
              else if (isCompanyAdmin) navigate("/dashboard");
              else navigate("/");
            }}
            className="underline hover:text-white transition"
          >
            Back to my workspace
          </button>
        </div>
      )}
      <div className="mx-auto max-w-7xl px-4 sm:px-6 h-20 flex items-center justify-between gap-3">
        <Link to="/" data-testid="nav-logo" className="flex items-center gap-3 shrink-0">
          <img src={LOGO_URL} alt="Kreeda Nation" className="w-16 h-16 object-cover rounded-full border border-white/10 bg-black" />
          <div className="leading-none hidden lg:flex flex-col items-stretch">
            <div data-testid="brand-kreeda" className="font-logo font-extrabold text-[34px] text-white uppercase leading-[0.9] tracking-[0.18em] text-center">
              KREEDA
            </div>
            <div data-testid="brand-nation" className="mt-1 flex items-center justify-between gap-2">
              <span className="h-[2px] flex-1 bg-[#22C55E] rounded-full" aria-hidden="true" />
              <span className="font-logo font-light text-[13px] tracking-[0.35em] text-[#22C55E] uppercase leading-none">NATION</span>
              <span className="h-[2px] flex-1 bg-[#22C55E] rounded-full" aria-hidden="true" />
            </div>
            <div className="text-[10px] font-mono uppercase tracking-widest mt-1.5 text-center">
              <span className="text-[#EC4899]">compete</span>
              <span className="text-neutral-500"> · </span>
              <span className="text-[#84CC16]">connect</span>
              <span className="text-neutral-500"> · </span>
              <span className="text-[#06B6D4]">grow</span>
            </div>
          </div>
          <div className="leading-none flex lg:hidden flex-col items-stretch">
            <div className="font-logo font-extrabold text-xl sm:text-2xl text-white uppercase leading-[0.9] tracking-[0.18em] text-center">
              KREEDA
            </div>
            <div className="mt-0.5 flex items-center justify-between gap-1.5">
              <span className="h-px flex-1 bg-[#22C55E] rounded-full" aria-hidden="true" />
              <span className="font-logo font-light text-[10px] tracking-[0.32em] text-[#22C55E] uppercase leading-none">NATION</span>
              <span className="h-px flex-1 bg-[#22C55E] rounded-full" aria-hidden="true" />
            </div>
          </div>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-0.5 flex-1 justify-center">
          {visiblePublicLinks.map((n) => <DesktopLink key={n.to} link={n} />)}
          {primaryRoleLinks.map((n) => <DesktopLink key={n.to} link={n} />)}
        </nav>

        {/* Right side actions */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Universal "Book a venue" CTA — guests can browse; login is required only at booking submit. */}
          <Button
            data-testid="nav-book-venue-btn"
            size="sm"
            onClick={() => navigate("/hire")}
            className="hidden md:inline-flex bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm gap-1"
          >
            <Store className="w-3.5 h-3.5" /> Book a venue
          </Button>
          {isAuthed ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  data-testid="nav-user-menu"
                  className="hidden md:flex items-center gap-2 px-2 py-1.5 rounded-sm hover:bg-white/5 transition-colors"
                  aria-label="Open account menu"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#84CC16] to-[#06B6D4] flex items-center justify-center text-black font-bold text-sm shrink-0">
                    {(user.name || user.email || "?").charAt(0).toUpperCase()}
                  </div>
                  <div className="flex flex-col items-start leading-tight max-w-[160px]">
                    {companyName ? (
                      <span className="text-xs font-mono text-[#84CC16] truncate max-w-full">{companyName}</span>
                    ) : (
                      <span className="text-xs font-medium text-neutral-200 truncate max-w-full">{user.name || "Account"}</span>
                    )}
                    <span data-testid="nav-user-email" className="text-[10px] text-neutral-500 font-mono truncate max-w-full">{user.email}</span>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-neutral-500" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                data-testid="nav-user-menu-content"
                align="end"
                sideOffset={6}
                className="bg-[#0c0c0c] border-white/10 text-white w-64"
              >
                <DropdownMenuLabel className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">
                  Signed in as
                </DropdownMenuLabel>
                <div className="px-2 pb-2">
                  <div className="text-sm text-neutral-200 truncate">{user.name || user.email}</div>
                  <div className="text-[11px] text-neutral-500 font-mono truncate">{user.email}</div>
                  {companyName && <div className="text-[11px] text-[#84CC16] font-mono truncate mt-0.5">{companyName}</div>}
                  {user.also_player && user.role !== "player" && inPlayerMode && (
                    <div className="mt-2 inline-flex items-center gap-1 text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-sm bg-[#84CC16]/20 text-[#84CC16] border border-[#84CC16]/40" data-testid="nav-player-mode-badge">
                      <User className="w-2.5 h-2.5" /> Player mode active
                    </div>
                  )}
                </div>
                {user.role !== "player" && (
                  <>
                    <DropdownMenuSeparator className="bg-white/10" />
                    <DropdownMenuItem
                      data-testid="nav-toggle-also-player"
                      onSelect={async (e) => {
                        e.preventDefault();
                        // Case 1 — not yet opted in: enable also_player on the
                        // server, then flip the local mode. One-time API call.
                        if (!user.also_player) {
                          try {
                            await api.post("/auth/also-player", { enabled: true });
                            setActiveMode("player");
                            toast.success("Switched to player mode");
                            setTimeout(() => window.location.reload(), 500);
                          } catch (err) {
                            toast.error(err.response?.data?.detail || "Failed to enable");
                          }
                          return;
                        }
                        // Case 2 — already opted in: just flip the view mode,
                        // no API call, no reload. Route the user to a page
                        // that fits the new mode so they don't sit on a page
                        // that just got hidden from the nav.
                        const next = inPlayerMode ? "primary" : "player";
                        setActiveMode(next);
                        toast.success(next === "player" ? "Switched to player mode" : "Switched back to your workspace");
                        if (next === "player") navigate("/players/me");
                        else if (isVendor) navigate("/vendor/dashboard");
                        else if (isSponsor) navigate("/sponsors/me");
                        else if (isPlatformAdmin) navigate("/platform-admin");
                        else if (isCompanyAdmin) navigate("/dashboard");
                      }}
                      className="cursor-pointer focus:bg-white/5 focus:text-white flex items-center gap-2"
                    >
                      {inPlayerMode ? (
                        <><ToggleRight className="w-4 h-4 text-[#84CC16]" /> <span>Back to my workspace</span></>
                      ) : user.also_player ? (
                        <><ToggleLeft className="w-4 h-4 text-[#06B6D4]" /> <span>Switch to player mode</span></>
                      ) : (
                        <><ToggleLeft className="w-4 h-4 text-neutral-400" /> <span>Enable player mode</span></>
                      )}
                    </DropdownMenuItem>
                  </>
                )}
                {moreRoleLinks.length > 0 && (
                  <>
                    <DropdownMenuSeparator className="bg-white/10" />
                    <DropdownMenuLabel className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">
                      Workspace
                    </DropdownMenuLabel>
                    {moreRoleLinks.map((n) => {
                      const Icon = n.icon;
                      return (
                        <DropdownMenuItem
                          key={n.to}
                          asChild
                          data-testid={`nav-menu-${n.label.toLowerCase().replace(/\s/g, "-")}`}
                          className="cursor-pointer focus:bg-white/5 focus:text-white"
                        >
                          <Link to={n.to} className="flex items-center gap-2 w-full">
                            {Icon ? <Icon className="w-4 h-4 text-neutral-400" /> : <span className="w-4 h-4" />}
                            <span style={n.accent ? { color: n.accent } : undefined}>{n.label}</span>
                          </Link>
                        </DropdownMenuItem>
                      );
                    })}
                  </>
                )}
                {guide && (
                  <>
                    <DropdownMenuSeparator className="bg-white/10" />
                    <DropdownMenuItem asChild className="cursor-pointer focus:bg-white/5 focus:text-white">
                      <a
                        href={guide.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={guide.testid}
                        className="flex items-center gap-2 w-full"
                      >
                        <BookOpen className="w-4 h-4 text-neutral-400" />
                        {guide.label}
                      </a>
                    </DropdownMenuItem>
                  </>
                )}
                <DropdownMenuSeparator className="bg-white/10" />
                <DropdownMenuItem
                  data-testid="nav-logout-btn"
                  onClick={async () => { await logout(); navigate("/"); }}
                  className="cursor-pointer focus:bg-[#FF3B30]/10 focus:text-[#FF3B30] text-[#FF3B30]"
                >
                  <LogOut className="w-4 h-4 mr-2" /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <>
              <Button
                data-testid="nav-login-btn"
                variant="ghost"
                size="sm"
                onClick={() => navigate("/login")}
                className="text-neutral-300 hover:text-white hidden sm:inline-flex"
              >
                Sign in
              </Button>
              <Button
                data-testid="nav-signup-organiser-btn"
                size="sm"
                onClick={() => navigate("/signup-organiser")}
                className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm hidden md:inline-flex"
              >
                For Organisers
              </Button>
              <Button
                data-testid="nav-signup-company-btn"
                size="sm"
                onClick={() => navigate("/signup-company")}
                className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm hidden sm:inline-flex"
              >
                For Companies
              </Button>
            </>
          )}

          {/* Mobile hamburger */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button
                data-testid="nav-mobile-toggle"
                variant="ghost"
                size="icon"
                className="md:hidden text-white hover:bg-white/10 rounded-sm"
                aria-label="Open menu"
              >
                <Menu className="w-5 h-5" />
              </Button>
            </SheetTrigger>
            <SheetContent
              side="right"
              data-testid="nav-mobile-drawer"
              className="bg-[#0a0a0a] border-l border-white/10 text-white w-[85vw] sm:w-96 p-0 overflow-y-auto"
            >
              <SheetTitle className="sr-only">Kreeda Nation menu</SheetTitle>
              <SheetDescription className="sr-only">Navigation links and account actions for mobile.</SheetDescription>

              <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
                <div className="flex items-center gap-3">
                  <img src={LOGO_URL} alt="" className="w-9 h-9 object-cover rounded-full border border-white/10 bg-black" />
                  <span className="font-brand text-lg">
                    <span className="text-white">KREEDA</span><span className="text-[#84CC16]"> NATION</span>
                  </span>
                </div>
                <button
                  data-testid="nav-mobile-close"
                  onClick={closeMobile}
                  className="text-neutral-400 hover:text-white p-1 rounded-sm"
                  aria-label="Close menu"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {isAuthed && (
                <div className="px-5 py-3 border-b border-white/10 bg-white/[0.02]">
                  {companyName && <div className="text-xs font-mono text-[#84CC16]">{companyName}</div>}
                  <div className="text-sm text-neutral-300 truncate">{user.email}</div>
                </div>
              )}

              <div className="px-3 py-3 flex flex-col gap-0.5">
                <div className="text-[10px] font-mono uppercase text-neutral-500 px-2 mt-1 mb-1 tracking-widest">/ Browse</div>
                {visiblePublicLinks.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    end={n.to === "/"}
                    onClick={closeMobile}
                    data-testid={`nav-mobile-link-${n.label.toLowerCase()}`}
                    className={({ isActive }) =>
                      `px-3 py-3 text-base font-medium rounded-sm transition-colors ${
                        isActive ? "bg-white/5 text-white" : "text-neutral-300 hover:bg-white/5 hover:text-white"
                      }`
                    }
                  >
                    {n.label}
                  </NavLink>
                ))}

                {allRoleLinks.length > 0 && (
                  <>
                    <div className="text-[10px] font-mono uppercase text-neutral-500 px-2 mt-4 mb-1 tracking-widest">/ My Workspace</div>
                    {allRoleLinks.map((n) => {
                      const Icon = n.icon;
                      return (
                        <NavLink
                          key={n.to}
                          to={n.to}
                          end={n.to === "/"}
                          onClick={closeMobile}
                          data-testid={`nav-mobile-link-${n.label.toLowerCase().replace(/\s/g, "-")}`}
                          className={({ isActive }) =>
                            `px-3 py-3 text-base font-medium rounded-sm flex items-center gap-2 transition-colors ${
                              isActive ? "bg-white/10 text-white" : "hover:bg-white/5"
                            }`
                          }
                          style={n.accent ? { color: n.accent } : undefined}
                        >
                          {Icon && <Icon className="w-4 h-4" />}
                          {n.label}
                        </NavLink>
                      );
                    })}
                  </>
                )}

                {guide && (
                  <>
                    <div className="text-[10px] font-mono uppercase text-neutral-500 px-2 mt-4 mb-1 tracking-widest">/ Help</div>
                    <a
                      href={guide.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={closeMobile}
                      data-testid={`${guide.testid}-mobile`}
                      className="px-3 py-3 text-base font-medium rounded-sm flex items-center gap-2 text-neutral-300 hover:bg-white/5 hover:text-white transition-colors"
                    >
                      <BookOpen className="w-4 h-4" /> {guide.label}
                    </a>
                  </>
                )}

                <div className="border-t border-white/10 my-4" />

                {/* Universal "Book a venue" CTA — always visible so guests can browse the marketplace. */}
                <Button
                  data-testid="nav-mobile-book-venue"
                  onClick={() => { closeMobile(); navigate("/hire"); }}
                  className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm justify-start gap-2 mb-2"
                >
                  <Store className="w-4 h-4" /> Book a venue
                </Button>

                {isAuthed ? (
                  <Button
                    data-testid="nav-mobile-logout"
                    variant="outline"
                    onClick={async () => { closeMobile(); await logout(); navigate("/"); }}
                    className="border-white/10 bg-transparent text-neutral-300 hover:bg-white/5 rounded-sm justify-start"
                  >
                    <LogOut className="w-4 h-4 mr-2" /> Sign out
                  </Button>
                ) : (
                  <div className="flex flex-col gap-2">
                    <Button
                      data-testid="nav-mobile-login"
                      variant="outline"
                      onClick={() => { closeMobile(); navigate("/login"); }}
                      className="border-white/10 bg-transparent text-neutral-300 hover:bg-white/5 rounded-sm"
                    >
                      Sign in
                    </Button>
                    <Button
                      data-testid="nav-mobile-signup-organiser"
                      onClick={() => { closeMobile(); navigate("/signup-organiser"); }}
                      className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm"
                    >
                      For Organisers
                    </Button>
                    <Button
                      data-testid="nav-mobile-signup"
                      onClick={() => { closeMobile(); navigate("/signup-company"); }}
                      className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"
                    >
                      For Companies
                    </Button>
                  </div>
                )}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
