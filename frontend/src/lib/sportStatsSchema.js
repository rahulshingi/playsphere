/**
 * Per-sport stat fields shown in the player profile career dashboard.
 *
 * Each entry declares a list of `manual` fields the player can self-enter, and
 * optionally a list of `auto` fields that are computed by the backend (cricket only
 * for now). Auto values always take precedence over manual ones unless the player
 * overrides them explicitly.
 *
 * Field: { key, label, type: "number"|"text", unit?, format?: "decimal" }
 */

const NUM = (key, label, opts = {}) => ({ key, label, type: "number", ...opts });
const TXT = (key, label) => ({ key, label, type: "text" });

export const STATS_SCHEMAS = {
  cricket: {
    label: "Cricket",
    color: "#10B981",
    // Auto-computed by backend from completed fixtures
    auto: [
      NUM("matches", "Matches"),
      NUM("runs", "Runs"),
      NUM("balls_faced", "Balls faced"),
      NUM("fours", "Fours"),
      NUM("sixes", "Sixes"),
      NUM("highest_score", "Highest score"),
      NUM("wickets", "Wickets"),
      NUM("overs_bowled", "Overs bowled", { format: "decimal" }),
      NUM("runs_conceded", "Runs conceded"),
      NUM("batting_average", "Batting avg", { format: "decimal" }),
      NUM("strike_rate", "Strike rate", { format: "decimal" }),
      NUM("bowling_economy", "Economy", { format: "decimal" }),
      NUM("bowling_average", "Bowling avg", { format: "decimal" }),
    ],
    // Manual entry for stats earned OUTSIDE Kreeda Nation (club, state, etc.)
    manual: [
      NUM("external_matches", "Matches (other tournaments)"),
      NUM("external_runs", "Runs (other tournaments)"),
      NUM("external_wickets", "Wickets (other tournaments)"),
      TXT("notable_achievement", "Notable achievement"),
    ],
  },
  football: {
    label: "Football",
    color: "#84CC16",
    auto: [],
    manual: [
      NUM("matches", "Matches"),
      NUM("goals", "Goals"),
      NUM("assists", "Assists"),
      NUM("clean_sheets", "Clean sheets (GK)"),
      NUM("yellow_cards", "Yellow cards"),
      NUM("red_cards", "Red cards"),
    ],
  },
  basketball: {
    label: "Basketball",
    color: "#F59E0B",
    auto: [],
    manual: [
      NUM("games", "Games"),
      NUM("points", "Points"),
      NUM("rebounds", "Rebounds"),
      NUM("assists", "Assists"),
      NUM("steals", "Steals"),
      NUM("blocks", "Blocks"),
    ],
  },
  badminton: {
    label: "Badminton",
    color: "#A855F7",
    auto: [],
    manual: [
      NUM("matches", "Matches"),
      NUM("wins", "Wins"),
      NUM("tournament_titles", "Tournament titles"),
      TXT("highest_ranking", "Highest ranking"),
    ],
  },
  tabletennis: {
    label: "Table Tennis",
    color: "#EC4899",
    auto: [],
    manual: [
      NUM("matches", "Matches"),
      NUM("wins", "Wins"),
      NUM("tournament_titles", "Tournament titles"),
      TXT("highest_ranking", "Highest ranking"),
    ],
  },
  volleyball: {
    label: "Volleyball",
    color: "#06B6D4",
    auto: [],
    manual: [
      NUM("matches", "Matches"),
      NUM("spikes", "Spikes"),
      NUM("blocks", "Blocks"),
      NUM("aces", "Aces"),
    ],
  },
  chess: {
    label: "Chess",
    color: "#94A3B8",
    auto: [],
    manual: [
      NUM("games", "Games"),
      NUM("wins", "Wins"),
      NUM("draws", "Draws"),
      NUM("losses", "Losses"),
      NUM("current_rating", "Current rating"),
      NUM("peak_rating", "Peak rating"),
    ],
  },
  quiz: {
    label: "Quiz",
    color: "#FACC15",
    auto: [],
    manual: [
      NUM("events", "Events"),
      NUM("wins", "Wins"),
      NUM("podium_finishes", "Top-3 finishes"),
    ],
  },
  hackathon: {
    label: "Hackathon",
    color: "#FF3B30",
    auto: [],
    manual: [
      NUM("hackathons", "Hackathons"),
      NUM("wins", "Wins"),
      NUM("prizes_won", "Prizes won"),
      TXT("biggest_win", "Biggest win"),
    ],
  },
  other: {
    label: "Other",
    color: "#84CC16",
    auto: [],
    manual: [
      NUM("matches", "Matches"),
      NUM("wins", "Wins"),
      TXT("notes", "Notes"),
    ],
  },
};

export function formatStatValue(v, field) {
  if (v == null || v === "") return "—";
  if (field?.format === "decimal" && typeof v === "number") return v.toFixed(2);
  return v;
}
