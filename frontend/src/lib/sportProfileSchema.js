/**
 * Schema-driven sport-specific player profile fields.
 *
 * Each schema declares the fields that should appear when a player picks that sport
 * in their "interested sports" multi-select. The PlayerProfile editor renders these
 * dynamically — adding a new sport here makes it instantly available end-to-end.
 *
 * Field shape:
 *   { key, label, type: "text"|"number"|"select"|"textarea", options?: [...], placeholder?, testid }
 *
 * Values are stored under `profile.sport_profiles[sport_slug][field_key]`.
 */

const ROLES_CRICKET = ["any", "batsman", "bowler", "all-rounder", "wicket-keeper"];
const HAND = ["right", "left"];
const BOWLING_STYLES = [
  "none", "right-arm-fast", "right-arm-medium", "right-arm-spin",
  "left-arm-fast", "left-arm-medium", "left-arm-spin",
];

export const SPORT_SCHEMAS = {
  cricket: {
    color: "#10B981",
    label: "Cricket",
    fields: [
      { key: "role", label: "Playing role", type: "select", options: ROLES_CRICKET, default: "any" },
      { key: "batting_hand", label: "Batting hand", type: "select", options: HAND, default: "right" },
      { key: "bowling_style", label: "Bowling style", type: "select", options: BOWLING_STYLES, default: "none" },
      { key: "jersey_number", label: "Jersey number", type: "number" },
      { key: "cricheroes_url", label: "Cric Heroes profile URL", type: "text", placeholder: "https://cricheroes.com/player/…" },
    ],
  },
  football: {
    color: "#84CC16",
    label: "Football",
    fields: [
      { key: "position", label: "Position", type: "select",
        options: ["any", "goalkeeper", "defender", "midfielder", "forward", "winger"], default: "any" },
      { key: "preferred_foot", label: "Preferred foot", type: "select", options: ["right", "left", "both"], default: "right" },
      { key: "jersey_number", label: "Jersey number", type: "number" },
    ],
  },
  basketball: {
    color: "#F59E0B",
    label: "Basketball",
    fields: [
      { key: "position", label: "Position", type: "select",
        options: ["point-guard", "shooting-guard", "small-forward", "power-forward", "center"], default: "shooting-guard" },
      { key: "shooting_hand", label: "Shooting hand", type: "select", options: HAND, default: "right" },
      { key: "jersey_number", label: "Jersey number", type: "number" },
    ],
  },
  badminton: {
    color: "#A855F7",
    label: "Badminton",
    fields: [
      { key: "hand", label: "Playing hand", type: "select", options: HAND, default: "right" },
      { key: "grip", label: "Grip style", type: "select", options: ["forehand", "backhand", "panhandle"], default: "forehand" },
      { key: "format", label: "Preferred format", type: "select", options: ["singles", "doubles", "mixed-doubles", "any"], default: "any" },
    ],
  },
  tabletennis: {
    color: "#EC4899",
    label: "Table Tennis",
    fields: [
      { key: "hand", label: "Playing hand", type: "select", options: HAND, default: "right" },
      { key: "grip", label: "Grip", type: "select", options: ["shakehand", "penhold"], default: "shakehand" },
      { key: "style", label: "Playing style", type: "select", options: ["offensive", "defensive", "all-round"], default: "all-round" },
    ],
  },
  volleyball: {
    color: "#06B6D4",
    label: "Volleyball",
    fields: [
      { key: "position", label: "Position", type: "select",
        options: ["setter", "outside-hitter", "opposite", "middle-blocker", "libero"], default: "outside-hitter" },
      { key: "hand", label: "Spiking hand", type: "select", options: HAND, default: "right" },
      { key: "jersey_number", label: "Jersey number", type: "number" },
    ],
  },
  chess: {
    color: "#94A3B8",
    label: "Chess",
    fields: [
      { key: "rating", label: "Rating (FIDE / online)", type: "number", placeholder: "e.g. 1850" },
      { key: "title", label: "Title", type: "select", options: ["none", "CM", "FM", "IM", "GM", "WCM", "WFM", "WIM", "WGM"], default: "none" },
      { key: "preferred_color", label: "Preferred color", type: "select", options: ["white", "black", "either"], default: "either" },
      { key: "chesscom_url", label: "Chess.com / Lichess URL", type: "text", placeholder: "https://chess.com/member/…" },
    ],
  },
  quiz: {
    color: "#FACC15",
    label: "Quiz",
    fields: [
      { key: "specialty", label: "Specialty", type: "select",
        options: ["general-knowledge", "sports", "films", "history", "science", "business", "tech", "literature"], default: "general-knowledge" },
      { key: "format", label: "Preferred format", type: "select", options: ["solo", "team", "any"], default: "any" },
    ],
  },
  hackathon: {
    color: "#FF3B30",
    label: "Hackathon",
    fields: [
      { key: "domain", label: "Primary domain", type: "select",
        options: ["frontend", "backend", "full-stack", "mobile", "ai-ml", "data", "devops", "design", "product"], default: "full-stack" },
      { key: "languages", label: "Languages / stack", type: "text", placeholder: "e.g. Python, React, AWS" },
      { key: "github_url", label: "GitHub URL", type: "text", placeholder: "https://github.com/…" },
    ],
  },
  other: {
    color: "#84CC16",
    label: "Other",
    fields: [
      { key: "sport_name", label: "Sport name", type: "text", placeholder: "e.g. Kabaddi, Squash" },
      { key: "role", label: "Role / position", type: "text" },
    ],
  },
};

export const SPORT_KEYS = Object.keys(SPORT_SCHEMAS);

/** Quick lookup: primary tag to show on a player card given their interested sports + sport_profiles. */
export function getPrimaryRole(sport, sportProfile) {
  if (!sport || !sportProfile) return null;
  const schema = SPORT_SCHEMAS[sport];
  if (!schema) return null;
  // Prefer role/position/specialty/domain field, falling back to the first non-default selectable.
  const candidates = ["role", "position", "specialty", "domain", "style", "format"];
  for (const k of candidates) {
    if (sportProfile[k]) return String(sportProfile[k]).replace(/-/g, " ");
  }
  return null;
}
