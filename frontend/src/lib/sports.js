// Helpers for rendering sport-specific scores. The `SPORTS` array below is a
// FALLBACK list used only when the /api/sports network fetch fails. All UIs
// should prefer `useSports()` from `@/hooks/useSports` so admin-added sports
// (e.g. pickleball) appear immediately in dropdowns.
export const SPORTS = [
  { value: "cricket", label: "Cricket", scoring_pattern: "cricket", player_format: "team" },
  { value: "football", label: "Football", scoring_pattern: "football", player_format: "team" },
  { value: "basketball", label: "Basketball", scoring_pattern: "basketball", player_format: "team" },
  { value: "badminton", label: "Badminton", scoring_pattern: "racket", player_format: "both" },
  { value: "tabletennis", label: "Table Tennis", scoring_pattern: "racket", player_format: "both" },
  { value: "tennis", label: "Tennis", scoring_pattern: "racket", player_format: "both" },
  { value: "lawntennis", label: "Lawn Tennis", scoring_pattern: "racket", player_format: "both" },
  { value: "pickleball", label: "Pickleball", scoring_pattern: "racket", player_format: "both" },
  { value: "volleyball", label: "Volleyball", scoring_pattern: "racket", player_format: "team" },
  { value: "chess", label: "Chess", scoring_pattern: "chess", player_format: "individual" },
  { value: "quiz", label: "Quiz", scoring_pattern: "quiz", player_format: "individual" },
  { value: "hackathon", label: "Hackathon", scoring_pattern: "hackathon", player_format: "team" },
  { value: "other", label: "Other", scoring_pattern: "generic", player_format: "team" },
];

export function renderScore(sport, side) {
  if (!side) return "0";
  // Accepts either a raw sport slug OR an event object with `scoring_pattern`.
  const pattern = typeof sport === "object" ? (sport.scoring_pattern || sport.sport) : sport;
  switch (pattern) {
    case "cricket":
      return `${side.runs ?? 0}/${side.wickets ?? 0} (${(side.overs ?? 0).toFixed(1)})`;
    case "football":
      return `${side.goals ?? 0}`;
    case "basketball":
      return `${side.points ?? 0}`;
    case "racket":
    case "badminton":
    case "tabletennis":
    case "tennis":
    case "lawntennis":
    case "pickleball":
    case "volleyball":
      return (side.sets || []).join(" · ") || "0";
    case "chess":
      // Chess score can be either the classic points (win=1 / draw=0.5) or
      // raw wins for scoreboard-style events. Support both by preferring an
      // explicit `points` field, falling back to `result_points`.
      return `${side.points ?? side.result_points ?? 0}`;
    case "quiz":
      return `${side.points ?? 0}`;
    case "hackathon":
      return `${side.score ?? 0}`;
    case "snooker":
    case "pool":
    case "generic":
      // Snooker / Pool: total frames won is the primary scoreline.
      if (typeof side.frames_won === "number") return `${side.frames_won}`;
      return `${side.score ?? side.points ?? 0}`;
    default:
      return `${side.score ?? 0}`;
  }
}

/**
 * Sport-specific rule config used by the live scorer to enforce win conditions
 * (best-of-sets, points-to-win-set, race-to-frames, chess time control, etc.).
 * Kept in-sync with backend `_SPORT_DEFAULTS.config` — advisory only, backend
 * is still the source of truth.
 */
export const SPORT_RULES = {
  cricket:     { pattern: "cricket",     has_toss: true, has_playing_xi: true },
  football:    { pattern: "football",    has_cards: true, has_substitutions: true },
  basketball:  { pattern: "basketball",  has_substitutions: true, quarters: 4 },
  badminton:   { pattern: "racket",      best_of_sets: 3, points_to_win_set: 21, deuce_win_by: 2, hard_cap: 30 },
  tabletennis: { pattern: "racket",      best_of_sets: 5, points_to_win_set: 11, deuce_win_by: 2 },
  tennis:      { pattern: "racket",      best_of_sets: 3, has_tiebreak: true, games_per_set: 6 },
  lawntennis:  { pattern: "racket",      best_of_sets: 3, has_tiebreak: true, games_per_set: 6 },
  pickleball:  { pattern: "racket",      best_of_sets: 3, points_to_win_set: 11, deuce_win_by: 2 },
  volleyball:  { pattern: "racket",      best_of_sets: 5, points_to_win_set: 25, deuce_win_by: 2, final_set_points: 15 },
  squash:      { pattern: "racket",      best_of_sets: 5, points_to_win_set: 11, deuce_win_by: 2 },
  snooker:     { pattern: "generic",     race_to_frames: 5 },
  pool:        { pattern: "generic",     race_to_frames: 5 },
  chess:       { pattern: "chess",       time_control: "10+5", has_draws: true, win_points: 1, draw_points: 0.5 },
  quiz:        { pattern: "quiz" },
  hackathon:   { pattern: "hackathon" },
};

export function rulesFor(sport, override = null) {
  const base = SPORT_RULES[sport] || { pattern: "generic" };
  return override ? { ...base, ...override } : base;
}

export function sportColor(sport) {
  return ({
    cricket: "#10B981",
    football: "#84CC16",
    basketball: "#F59E0B",
    badminton: "#A855F7",
    tabletennis: "#EC4899",
    tennis: "#06B6D4",
    lawntennis: "#06B6D4",
    pickleball: "#84CC16",
    volleyball: "#06B6D4",
    snooker: "#8B5CF6",
    pool: "#8B5CF6",
    chess: "#94A3B8",
    quiz: "#FACC15",
    hackathon: "#FF3B30",
  })[sport] || "#84CC16";
}

/**
 * Sport-specific fallback banner images. Used by Events.jsx + EventDetail.jsx
 * whenever an event has no `banner_url` set — high-quality Pexels photos one
 * per sport so cricket / badminton / tennis / snooker etc. get themed images
 * instead of the generic football fallback.
 */
export const SPORT_IMAGES = {
  cricket: "https://images.pexels.com/photos/3628912/pexels-photo-3628912.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  football: "https://images.pexels.com/photos/1657324/pexels-photo-1657324.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  basketball: "https://images.pexels.com/photos/1080882/pexels-photo-1080882.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  badminton: "https://images.pexels.com/photos/6203519/pexels-photo-6203519.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  tabletennis: "https://images.pexels.com/photos/976873/pexels-photo-976873.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  tennis: "https://images.pexels.com/photos/1432034/pexels-photo-1432034.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  lawntennis: "https://images.pexels.com/photos/8224057/pexels-photo-8224057.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  pickleball: "https://images.pexels.com/photos/8224706/pexels-photo-8224706.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  volleyball: "https://images.pexels.com/photos/1263426/pexels-photo-1263426.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  squash: "https://images.pexels.com/photos/8007488/pexels-photo-8007488.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  snooker: "https://images.pexels.com/photos/1329717/pexels-photo-1329717.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  pool: "https://images.pexels.com/photos/1329717/pexels-photo-1329717.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  chess: "https://images.pexels.com/photos/163150/chess-play-checkmate-black-163150.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  quiz: "https://images.pexels.com/photos/5428003/pexels-photo-5428003.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
  hackathon: "https://images.pexels.com/photos/1181677/pexels-photo-1181677.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
};

export function sportImage(sport) {
  return SPORT_IMAGES[sport] || "https://images.pexels.com/photos/2263436/pexels-photo-2263436.jpeg?auto=compress&cs=tinysrgb&h=650&w=940";
}


/**
 * Compute suggested winner + auto-complete for a match given a score dict.
 *
 * Returns { winner_id, isComplete, note } where:
 *   • winner_id — id of the team that has won (or null if inconclusive / draw)
 *   • isComplete — true when the match satisfies the win condition per rules
 *   • note — user-facing status string (e.g. "Match complete — best of 3 won 2-1")
 *
 * Racket sports (pickleball / tt / badminton / squash / volleyball): counts
 * sets won by comparing per-set point counts; complete when someone reaches
 * majority of `best_of_sets`.
 *
 * Snooker/pool: complete when either frames_won reaches `race_to_frames`.
 *
 * Chess: single-game — completes when a `result` field is set (white/draw/black).
 *
 * Anything else — null / not-decidable; the manual "Save & mark completed"
 * flow still applies.
 */
export function computeMatchOutcome(sport, score, teamAId, teamBId) {
  const rules = SPORT_RULES[sport] || { pattern: "generic" };
  const a = score?.team_a || {};
  const b = score?.team_b || {};
  if (rules.pattern === "racket" && rules.best_of_sets) {
    const setsA = a.sets || [];
    const setsB = b.sets || [];
    const target = rules.points_to_win_set || 21;
    const winBy = rules.deuce_win_by || 2;
    const hardCap = rules.hard_cap || null;
    let wonA = 0, wonB = 0;
    const rounds = Math.max(setsA.length, setsB.length);
    for (let i = 0; i < rounds; i += 1) {
      const pa = setsA[i] || 0;
      const pb = setsB[i] || 0;
      const winner = _setWinner(pa, pb, target, winBy, hardCap);
      if (winner === "a") wonA += 1;
      else if (winner === "b") wonB += 1;
    }
    const need = Math.ceil(rules.best_of_sets / 2);
    if (wonA >= need) return { winner_id: teamAId, isComplete: true, note: `Match won ${wonA}-${wonB} (best of ${rules.best_of_sets})` };
    if (wonB >= need) return { winner_id: teamBId, isComplete: true, note: `Match won ${wonB}-${wonA} (best of ${rules.best_of_sets})` };
    return { winner_id: null, isComplete: false, note: `${wonA}-${wonB} sets · to ${target}, best of ${rules.best_of_sets}` };
  }
  if (rules.race_to_frames) {
    const fa = a.frames_won || 0;
    const fb = b.frames_won || 0;
    if (fa >= rules.race_to_frames) return { winner_id: teamAId, isComplete: true, note: `Race to ${rules.race_to_frames} won ${fa}-${fb}` };
    if (fb >= rules.race_to_frames) return { winner_id: teamBId, isComplete: true, note: `Race to ${rules.race_to_frames} won ${fb}-${fa}` };
    return { winner_id: null, isComplete: false, note: `${fa}-${fb} frames · race to ${rules.race_to_frames}` };
  }
  if (rules.pattern === "chess") {
    const r = score?.result || null; // "white" | "black" | "draw"
    if (r === "white") return { winner_id: teamAId, isComplete: true, note: "White wins" };
    if (r === "black") return { winner_id: teamBId, isComplete: true, note: "Black wins" };
    if (r === "draw") return { winner_id: null, isComplete: true, note: "Draw · ½-½" };
    return { winner_id: null, isComplete: false, note: "Pick a result" };
  }
  return { winner_id: null, isComplete: false, note: "" };
}

function _setWinner(pa, pb, target, winBy, hardCap) {
  if (pa < target && pb < target) return null;
  if (Math.abs(pa - pb) >= winBy) return pa > pb ? "a" : "b";
  if (hardCap) {
    if (pa >= hardCap) return "a";
    if (pb >= hardCap) return "b";
  }
  return null;
}
