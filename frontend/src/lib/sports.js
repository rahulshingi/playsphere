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
    case "quiz":
      return `${side.points ?? 0}`;
    case "hackathon":
      return `${side.score ?? 0}`;
    default:
      return `${side.score ?? 0}`;
  }
}

export function sportColor(sport) {
  return ({
    cricket: "#10B981",
    football: "#84CC16",
    basketball: "#F59E0B",
    badminton: "#A855F7",
    tabletennis: "#EC4899",
    volleyball: "#06B6D4",
    chess: "#94A3B8",
    quiz: "#FACC15",
    hackathon: "#FF3B30",
  })[sport] || "#84CC16";
}
