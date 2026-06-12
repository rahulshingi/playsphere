import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer data-testid="site-footer" className="border-t border-white/10 mt-24">
      <div className="max-w-7xl mx-auto px-6 py-12 grid md:grid-cols-4 gap-8">
        <div>
          <div className="font-display text-3xl tracking-wider">PLAYSPHERE</div>
          <p className="text-xs text-neutral-500 font-mono mt-1 tracking-wide">
            WHERE TEAMS COMPETE, CONNECT &amp; GROW
          </p>
          <p className="text-sm text-neutral-400 mt-4 max-w-xs">
            Employee engagement, built for teams that play to win — together.
          </p>
        </div>
        <div>
          <div className="text-xs font-mono uppercase text-neutral-500 mb-3">Platform</div>
          <ul className="space-y-2 text-sm">
            <li><Link className="hover:text-[#007AFF]" to="/events">Events</Link></li>
            <li><Link className="hover:text-[#007AFF]" to="/teams">Teams</Link></li>
            <li><Link className="hover:text-[#007AFF]" to="/standings">Standings</Link></li>
            <li><Link className="hover:text-[#007AFF]" to="/sponsors">Sponsors</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs font-mono uppercase text-neutral-500 mb-3">Get Involved</div>
          <ul className="space-y-2 text-sm">
            <li><Link className="hover:text-[#007AFF]" to="/register-team">Register a team</Link></li>
            <li><Link className="hover:text-[#007AFF]" to="/login">Admin sign in</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs font-mono uppercase text-neutral-500 mb-3">Contact</div>
          <p className="text-sm text-neutral-400">hello@playsphere.io</p>
          <p className="text-sm text-neutral-400">+1 (415) 555-0142</p>
        </div>
      </div>
      <div className="border-t border-white/5 py-5 text-center text-xs text-neutral-500 font-mono">
        © 2026 PLAYSPHERE · ALL RIGHTS RESERVED
      </div>
    </footer>
  );
}
