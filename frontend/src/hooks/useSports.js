import { useEffect, useState } from "react";
import api from "@/lib/api";
import { SPORTS as FALLBACK_SPORTS } from "@/lib/sports";

// Cache the /api/sports response process-wide so every dropdown in the app
// isn't re-fetching the same list. TTL is short so admin-added sports show up
// within a page navigation.
let _cache = null;
let _cachedAt = 0;
const TTL_MS = 60_000;

export function useSports() {
  const [sports, setSports] = useState(_cache || FALLBACK_SPORTS);
  const [ready, setReady] = useState(!!_cache);

  useEffect(() => {
    // Serve cached list within TTL.
    if (_cache && Date.now() - _cachedAt < TTL_MS) {
      setSports(_cache);
      setReady(true);
      return;
    }
    let alive = true;
    api.get("/sports")
      .then((r) => {
        if (!alive) return;
        const list = Array.isArray(r.data) && r.data.length > 0 ? r.data : FALLBACK_SPORTS;
        _cache = list;
        _cachedAt = Date.now();
        setSports(list);
        setReady(true);
      })
      .catch(() => {
        if (!alive) return;
        setSports(FALLBACK_SPORTS);
        setReady(true);
      });
    return () => { alive = false; };
  }, []);

  return { sports, ready };
}

// Small helper — given a sport slug (or full sport object) return its
// `player_format` ("team"|"individual"|"both") so callers can decide whether
// to show a Singles/Doubles picker.
export function getPlayerFormat(sports, sport) {
  if (typeof sport === "object" && sport?.player_format) return sport.player_format;
  const doc = (sports || []).find((s) => s.value === (typeof sport === "string" ? sport : sport?.value));
  return doc?.player_format || "team";
}
