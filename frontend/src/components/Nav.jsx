import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { LogOut, Shield, Briefcase, Crown, User, Store, Menu, X, BookOpen, ChevronDown } from "lucide-react";
import { getRoleGuide } from "@/lib/guides";

const LOGO_URL = "/kreeda-mark.png";

const publicLinks = [
  { to: "/", label: "Home" },
  { to: "/events", label: "Events" },
  { to: "/services", label: "Services" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

/**
 * Each role exposes a `primary` list (rendered horizontally in the header) and
 * an optional `more` list (folded into the user-menu dropdown). Keep primary at
 * 2-3 items max to avoid horizontal scroll on HR / admin accounts.
 */
function roleLinks({ isCompanyAdmin, isPlayer, isVendor, isSponsor, isPlatformAdmin, isScorer }) {
  const primary = [];
  const more = [];
  if (isCompanyAdmin) {
    primary.push({ to: "/dashboard", label: "Dashboard", icon: Briefcase, accent: "#84CC16" });
    primary.push({ to: "/admin", label: "Manage", icon: Shield, accent: "#84CC16" });
    more.push({ to: "/hire", label: "Hire vendors", icon: Store });
    more.push({ to: "/my-memberships", label: "Memberships", accent: "#EC4899" });
    more.push({ to: "/players/profiles", label: "Players", icon: User });
    more.push({ to: "/sponsors/me", label: "Sponsor hub", accent: "#FACC15" });
  }
  if (isPlayer) {
    primary.push({ to: "/players/me", label: "My profile", icon: User, accent: "#84CC16" });
    more.push({ to: "/players/profiles", label: "Find players" });
    more.push({ to: "/my-memberships", label: "Memberships", accent: "#EC4899" });
  }
  if (isVendor) {
    primary.push({ to: "/vendor/dashboard", label: "Vendor", icon: Store, accent: "#EC4899" });
    primary.push({ to: "/bookings", label: "Requests" });
  }
  if (isSponsor) {
    primary.push({ to: "/sponsors/me", label: "Sponsor profile", icon: Briefcase, accent: "#FACC15" });
    primary.push({ to: "/sponsorships", label: "Sponsorships" });
  }
  if (isScorer) {
    primary.push({ to: "/scorer/dashboard", label: "Scorer", icon: Shield, accent: "#06B6D4" });
  }
  if (isPlatformAdmin) {
    primary.push({ to: "/platform-admin", label: "HQ", icon: Crown, accent: "#FF3B30" });
  }
  return { primary, more };
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
  const { user, isCompanyAdmin, isPlatformAdmin, isPlayer, isVendor, isSponsor, isScorer, companyName, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isAuthed = user && user !== false;
  const roles = { isCompanyAdmin, isPlayer, isVendor, isSponsor, isPlatformAdmin, isScorer };
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
      <div className="mx-auto max-w-7xl px-4 sm:px-6 h-20 flex items-center justify-between gap-3">
        <Link to="/" data-testid="nav-logo" className="flex items-center gap-3 shrink-0">
          <img src={LOGO_URL} alt="Kreeda Nation" className="w-16 h-16 object-contain" />
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
                </div>
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
                  <img src={LOGO_URL} alt="" className="w-9 h-9 object-contain" />
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
