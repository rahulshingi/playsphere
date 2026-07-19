import { Apple, Play } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Monochrome App Store / Play Store badges that respect the site theme.
 * - If `url` is set → renders an anchor opening the store in a new tab.
 * - If `url` is empty → renders a disabled badge with a "Stay tuned — launching soon"
 *   tooltip so users know the mobile apps are on the roadmap.
 *
 * Design intent: small, minimal, monochrome. No third-party colored badge assets.
 */
function StoreBadge({ Icon, primary, secondary, url, testid }) {
  const active = Boolean(url && url.trim());

  const badge = (
    <div
      className={[
        "flex items-center gap-2 px-3 py-2 rounded-sm border transition select-none",
        active
          ? "border-white/15 text-neutral-200 hover:text-[#84CC16] hover:border-[#84CC16]/40 cursor-pointer"
          : "border-white/10 text-neutral-500 cursor-not-allowed",
      ].join(" ")}
      data-testid={testid}
      data-active={active ? "true" : "false"}
    >
      <Icon className="w-5 h-5 shrink-0" strokeWidth={1.75} />
      <div className="flex flex-col leading-none">
        <span className="text-[9px] font-mono uppercase tracking-widest opacity-70">
          {active ? primary : "Stay tuned"}
        </span>
        <span className="text-[11px] font-semibold tracking-wide mt-0.5">{secondary}</span>
      </div>
    </div>
  );

  if (active) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" aria-label={`${secondary} — ${primary}`}>
        {badge}
      </a>
    );
  }

  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div aria-disabled="true" role="button" tabIndex={-1}>{badge}</div>
        </TooltipTrigger>
        <TooltipContent side="top" className="bg-black text-neutral-200 border border-white/10 font-mono text-[11px]">
          Stay tuned — launching soon
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export default function AppStoreBadges({ iosUrl, androidUrl }) {
  return (
    <div className="flex flex-wrap gap-2 mt-5" data-testid="app-store-badges">
      <StoreBadge
        Icon={Apple}
        primary="Download on the"
        secondary="App Store"
        url={iosUrl}
        testid="badge-ios-app"
      />
      <StoreBadge
        Icon={Play}
        primary="Get it on"
        secondary="Google Play"
        url={androidUrl}
        testid="badge-android-app"
      />
    </div>
  );
}
