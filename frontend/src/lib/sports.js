// Helpers for rendering sport-specific scores
export const SPORTS = [
  { value: "cricket", label: "Cricket" },
  { value: "football", label: "Football" },
  { value: "basketball", label: "Basketball" },
  { value: "badminton", label: "Badminton" },
  { value: "tabletennis", label: "Table Tennis" },
  { value: "volleyball", label: "Volleyball" },
  { value: "chess", label: "Chess" },
  { value: "quiz", label: "Quiz" },
  { value: "hackathon", label: "Hackathon" },
  { value: "other", label: "Other" },
];

export function renderScore(sport, side) {
  if (!side) return "0";
  switch (sport) {
    case "cricket":
      return `${side.runs ?? 0}/${side.wickets ?? 0} (${(side.overs ?? 0).toFixed(1)})`;
    case "football":
      return `${side.goals ?? 0}`;
    case "basketball":
      return `${side.points ?? 0}`;
    case "badminton":
    case "tabletennis":
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
    football: "#007AFF",
    basketball: "#F59E0B",
    badminton: "#A855F7",
    tabletennis: "#EC4899",
    volleyball: "#06B6D4",
    chess: "#94A3B8",
    quiz: "#FACC15",
    hackathon: "#FF3B30",
  })[sport] || "#007AFF";
}
