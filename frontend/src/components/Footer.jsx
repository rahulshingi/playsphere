import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Facebook, Instagram, Linkedin, Twitter, Youtube } from "lucide-react";

const ICON = { facebook_url: Facebook, instagram_url: Instagram, linkedin_url: Linkedin, twitter_url: Twitter, youtube_url: Youtube };

export default function Footer() {
  const [settings, setSettings] = useState({});
  useEffect(() => { api.get("/settings").then((r) => setSettings(r.data)); }, []);

  return (
    <footer data-testid="site-footer" className="border-t border-white/10 mt-24">
      <div className="max-w-7xl mx-auto px-6 py-12 grid md:grid-cols-4 gap-8">
        <div>
          <div className="flex items-center gap-3">
            <img src="/kreeda-mark.png" alt="Kreeda Nation" className="w-12 h-12 object-contain" />
            <div className="font-brand text-3xl">
              <span className="text-white">KREEDA</span><span className="text-[#84CC16]"> NATION</span>
            </div>
          </div>
          <p className="text-xs font-mono mt-3 tracking-wide">
            <span className="text-[#EC4899]">WHERE TEAMS COMPETE,</span> <span className="text-[#84CC16]">CONNECT</span> &amp; <span className="text-[#06B6D4]">GROW</span>
          </p>
          <p className="text-sm text-neutral-400 mt-4 max-w-xs">
            Employee engagement, built for teams that play to win — together.
          </p>
          <div className="flex gap-2 mt-5">
            {Object.entries(ICON).map(([key, Icon]) => {
              const url = settings[key];
              if (!url) return null;
              return (
                <a key={key} href={url} target="_blank" rel="noopener noreferrer" data-testid={`social-${key.replace("_url", "")}`}
                  className="w-9 h-9 rounded-sm border border-white/10 grid place-items-center text-neutral-400 hover:text-[#84CC16] hover:border-[#84CC16]/40 transition">
                  <Icon className="w-4 h-4" />
                </a>
              );
            })}
          </div>
        </div>
        <div>
          <div className="text-xs font-mono uppercase text-neutral-500 mb-3">Platform</div>
          <ul className="space-y-2 text-sm">
            <li><Link className="hover:text-[#84CC16]" to="/events">Events</Link></li>
            <li><Link className="hover:text-[#84CC16]" to="/players/profiles">Players</Link></li>
            <li><Link className="hover:text-[#84CC16]" to="/standings">Standings</Link></li>
            <li><Link className="hover:text-[#84CC16]" to="/services">Services</Link></li>
            <li><Link className="hover:text-[#84CC16]" to="/sponsors">Sponsors</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs font-mono uppercase text-neutral-500 mb-3">Join</div>
          <ul className="space-y-2 text-sm">
            <li><Link className="hover:text-[#84CC16]" to="/signup-company">Onboard a company</Link></li>
            <li><Link className="hover:text-[#84CC16]" to="/players/signup">Player account</Link></li>
            <li><Link className="hover:text-[#84CC16]" to="/vendor/signup">Become a vendor</Link></li>
            <li><Link className="hover:text-[#84CC16]" to="/login">Sign in</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs font-mono uppercase text-neutral-500 mb-3">Contact</div>
          <p className="text-sm text-neutral-400" data-testid="footer-contact-email">contact@kreedanation.com</p>
          <p className="text-sm text-neutral-400" data-testid="footer-contact-phone">+91 9923114499</p>
          <p className="text-xs text-neutral-500 font-mono mt-4">
            Looking for a manual?<br/>
            Sign in and your role-specific guide appears in the top nav.
          </p>
        </div>
      </div>
      <div className="border-t border-white/5 py-5 text-center text-xs text-neutral-500 font-mono">
        © 2026 KREEDA NATION · ALL RIGHTS RESERVED
      </div>
    </footer>
  );
}
