import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { getRoleGuide } from "@/lib/guides";
import { Button } from "@/components/ui/button";
import { BookOpen, X, Sparkles } from "lucide-react";

/**
 * One-paragraph elevator pitch shown to every freshly-signed-in user the FIRST time their
 * role lands on the platform. Persists dismissal per (user_id + role) in localStorage so a
 * single user with multiple sessions only sees it once per role.
 *
 * Roles intentionally get a tailored CTA: open the role-specific PDF guide. That's the
 * biggest activation lever — the data shows people who open the guide on day 1 are 3-4x
 * more likely to complete profile setup.
 */
const PITCHES = {
  platform_admin: {
    title: "Welcome to Kreeda Nation HQ",
    body: "You're at the helm — companies, organisers, vendors and sponsors all flow through your dashboard. Start by enabling staff admins under Team, then keep an eye on the Sponsorship Marketplace card for live deal flow.",
    accent: "#FF3B30",
  },
  admin: {
    title: "Welcome to Kreeda Nation HQ",
    body: "You're at the helm — companies, organisers, vendors and sponsors all flow through your dashboard. Start by enabling staff admins under Team, then keep an eye on the Sponsorship Marketplace card for live deal flow.",
    accent: "#FF3B30",
  },
  company_admin: {
    title: "Welcome, HR captain",
    body: "Kreeda Nation runs your corporate sports league end-to-end — register teams, generate fixtures, score live, and now monetise your events with the sponsorship marketplace or sponsor other companies' tournaments from the same login.",
    accent: "#84CC16",
  },
  organiser: {
    title: "Welcome, tournament organiser",
    body: "Launch tournaments in minutes — set up events, invite companies, generate fixtures, and open them to sponsors with one click. Your sponsor revenue is now a tab away on every event you run.",
    accent: "#06B6D4",
  },
  vendor: {
    title: "Welcome to the Kreeda Nation marketplace",
    body: "Lists your grounds, slots, coaches and equipment in front of every company and organiser running corporate sports across India. Get verified, publish listings, and confirm bookings as they roll in.",
    accent: "#EC4899",
  },
  player: {
    title: "Welcome, athlete",
    body: "Your universal corporate sports profile lives here — pick the sports you play, fill out per-sport roles, and let your career stats auto-track as you play Kreeda Nation tournaments. Captains find you here.",
    accent: "#84CC16",
  },
  sponsor: {
    title: "Welcome to the marketplace",
    body: "Discover live corporate-sports tournaments by sport, location, budget and audience size. Express interest in any slot in one click — organisers review your profile + proposal and lock you in as the official sponsor.",
    accent: "#FACC15",
  },
};

const storageKey = (uid, role) => `kn_welcome_v1_${uid || "anon"}_${role || "guest"}`;

export default function WelcomeModal() {
  const { user, ready } = useAuth();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!ready || !user || user === false) return;
    const key = storageKey(user.id, user.role);
    if (!window.localStorage.getItem(key)) setOpen(true);
  }, [ready, user]);

  if (!open || !user) return null;
  const pitch = PITCHES[user.role];
  if (!pitch) return null;
  const guide = getRoleGuide(user.role);

  const dismiss = () => {
    window.localStorage.setItem(storageKey(user.id, user.role), new Date().toISOString());
    setOpen(false);
  };

  return (
    <div className="fixed inset-0 z-[60] bg-black/85 backdrop-blur-sm flex items-center justify-center p-6" data-testid="welcome-modal">
      <div className="bg-[#0c0c0c] border rounded-sm w-full max-w-lg p-7 text-white shadow-2xl relative" style={{ borderColor: `${pitch.accent}40` }}>
        <button onClick={dismiss} aria-label="Close" data-testid="welcome-close"
          className="absolute top-3 right-3 text-neutral-500 hover:text-white">
          <X className="w-4 h-4" />
        </button>

        <div className="font-mono text-[10px] uppercase tracking-[0.3em] flex items-center gap-2" style={{ color: pitch.accent }}>
          <Sparkles className="w-3 h-3" /> First-time orientation
        </div>
        <h2 className="font-display text-3xl tracking-wide mt-3" data-testid="welcome-title">{pitch.title.toUpperCase()}</h2>
        <p className="text-sm text-neutral-300 leading-relaxed mt-4" data-testid="welcome-body">{pitch.body}</p>

        <div className="flex flex-wrap gap-2 mt-6">
          {guide && (
            <a
              href={guide.href}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="welcome-open-guide"
              onClick={dismiss}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-sm font-semibold text-black"
              style={{ backgroundColor: pitch.accent }}
            >
              <BookOpen className="w-4 h-4" /> Open my {guide.label.toLowerCase()}
            </a>
          )}
          <Button data-testid="welcome-dismiss" onClick={dismiss} variant="ghost" className="text-neutral-400 hover:text-white">
            Got it — let me explore
          </Button>
        </div>

        {user.role === "sponsor" && (
          <Link to="/sponsorships" onClick={dismiss} data-testid="welcome-sponsor-cta"
            className="block mt-4 text-[11px] font-mono uppercase tracking-widest text-[#FACC15] hover:underline">
            → Browse the sponsorship marketplace now
          </Link>
        )}
        {user.role === "company_admin" && (
          <Link to="/dashboard" onClick={dismiss} data-testid="welcome-company-cta"
            className="block mt-4 text-[11px] font-mono uppercase tracking-widest text-[#84CC16] hover:underline">
            → Open your dashboard
          </Link>
        )}
      </div>
    </div>
  );
}
