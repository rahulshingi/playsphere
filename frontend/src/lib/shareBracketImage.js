/**
 * Canvas-based bracket image generator.
 *
 * Produces a 1080×1350 Instagram-story-ready PNG summarising a tournament
 * bracket. Supports single-elimination (round-by-round columns) and
 * double-elimination (Winners bracket top, Losers bracket bottom, Grand Final).
 *
 * Contract:
 *   generateBracketImage({ event, fixtures, teamMap }) -> Promise<Blob>
 *
 * Zero server dependency — runs entirely in the browser.
 */

const W = 1080;
const H = 1350;
const BG = "#0a0a0a";
const FG = "#ffffff";
const MUTED = "#737373";
const ACCENT = "#84CC16";
const LOSER = "#EC4899";

export async function generateBracketImage({ event, fixtures, teamMap }) {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D context unavailable");

  // Background gradient
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, "#0a0a0a");
  grad.addColorStop(1, "#111111");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // Header
  ctx.fillStyle = ACCENT;
  ctx.font = "700 20px ui-monospace, monospace";
  ctx.fillText("/ BRACKET", 60, 80);

  ctx.fillStyle = FG;
  ctx.font = "700 48px 'Bebas Neue', Impact, sans-serif";
  const title = (event?.name || "TOURNAMENT").toUpperCase();
  ctx.fillText(trimForCanvas(ctx, title, W - 120), 60, 130);

  ctx.fillStyle = MUTED;
  ctx.font = "500 16px ui-monospace, monospace";
  const chips = [];
  if (event?.sport) chips.push(String(event.sport).toUpperCase());
  if (event?.format) chips.push(String(event.format).replace(/_/g, " ").toUpperCase());
  ctx.fillText(chips.join("  ·  "), 60, 160);

  // Layout
  if (event?.format === "double_elimination") {
    drawDoubleElimination(ctx, fixtures, teamMap);
  } else {
    drawSingleElimination(ctx, fixtures, teamMap);
  }

  // Footer
  ctx.fillStyle = MUTED;
  ctx.font = "500 14px ui-monospace, monospace";
  ctx.fillText("KREEDANATION.COM", 60, H - 60);
  ctx.fillStyle = ACCENT;
  ctx.fillText("WHERE TEAMS COMPETE, CONNECT & GROW", 60, H - 40);

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("toBlob failed"))), "image/png");
  });
}

function drawSingleElimination(ctx, fixtures, teamMap) {
  // Group by round
  const rounds = {};
  fixtures.forEach((f) => {
    if (!rounds[f.round]) rounds[f.round] = [];
    rounds[f.round].push(f);
  });
  const roundNums = Object.keys(rounds).map(Number).sort((a, b) => a - b);
  if (roundNums.length === 0) {
    drawEmpty(ctx);
    return;
  }
  const startY = 220;
  const availableW = W - 120;
  const colW = availableW / roundNums.length;
  const rowH = 78;
  const availableH = H - startY - 140;

  roundNums.forEach((rnd, colIdx) => {
    const list = rounds[rnd].sort((a, b) => a.match_number - b.match_number);
    // Column header
    ctx.fillStyle = MUTED;
    ctx.font = "600 12px ui-monospace, monospace";
    ctx.fillText(`/ R${rnd}`, 60 + colIdx * colW, startY - 10);

    const availPerRow = Math.max(rowH, availableH / Math.max(list.length, 1));
    list.forEach((f, rowIdx) => {
      const x = 60 + colIdx * colW + 6;
      const y = startY + rowIdx * availPerRow + (availPerRow - rowH) / 2;
      drawMatchCard(ctx, f, teamMap, x, y, colW - 20);
    });
  });
}

function drawDoubleElimination(ctx, fixtures, teamMap) {
  const wb = fixtures.filter((f) => (f.bracket_position || "").startsWith("WB-"));
  const lb = fixtures.filter((f) => (f.bracket_position || "").startsWith("LB-"));
  const gf = fixtures.filter((f) => (f.bracket_position || "").startsWith("GF-"));

  // Winners bracket in top half
  ctx.fillStyle = ACCENT;
  ctx.font = "700 18px ui-monospace, monospace";
  ctx.fillText("/ WINNERS BRACKET", 60, 210);
  drawBracketBlock(ctx, wb, teamMap, 60, 230, W - 120, 380);

  // Losers bracket in middle
  ctx.fillStyle = LOSER;
  ctx.font = "700 18px ui-monospace, monospace";
  ctx.fillText("/ LOSERS BRACKET", 60, 660);
  drawBracketBlock(ctx, lb, teamMap, 60, 680, W - 120, 320);

  // Grand Final
  ctx.fillStyle = "#F59E0B";
  ctx.font = "700 18px ui-monospace, monospace";
  ctx.fillText("/ GRAND FINAL", 60, 1050);
  if (gf.length > 0) {
    drawMatchCard(ctx, gf[0], teamMap, 60, 1070, W - 120, true);
  }
}

function drawBracketBlock(ctx, list, teamMap, x, y, w, h) {
  if (list.length === 0) {
    ctx.fillStyle = MUTED;
    ctx.font = "500 14px ui-monospace, monospace";
    ctx.fillText("· No matches yet ·", x, y + 30);
    return;
  }
  // Group by round
  const rounds = {};
  list.forEach((f) => {
    const key = f.round || 1;
    if (!rounds[key]) rounds[key] = [];
    rounds[key].push(f);
  });
  const roundNums = Object.keys(rounds).map(Number).sort((a, b) => a - b);
  const colW = w / roundNums.length;
  roundNums.forEach((rnd, colIdx) => {
    const items = rounds[rnd].sort((a, b) => a.match_number - b.match_number);
    const rowH = h / Math.max(items.length, 1);
    items.forEach((f, i) => {
      const cx = x + colIdx * colW + 4;
      const cy = y + i * rowH + (rowH - 68) / 2;
      drawMatchCard(ctx, f, teamMap, cx, cy, colW - 12);
    });
  });
}

function drawMatchCard(ctx, fixture, teamMap, x, y, w, isGrandFinal = false) {
  const a = teamMap[fixture.team_a_id];
  const b = teamMap[fixture.team_b_id];
  const cardH = 68;
  // Frame
  ctx.fillStyle = isGrandFinal ? "rgba(245,158,11,0.08)" : "rgba(255,255,255,0.03)";
  ctx.strokeStyle = isGrandFinal ? "rgba(245,158,11,0.4)" : "rgba(255,255,255,0.12)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect ? ctx.roundRect(x, y, w, cardH, 4) : ctx.rect(x, y, w, cardH);
  ctx.fill();
  ctx.stroke();

  // Match number
  ctx.fillStyle = MUTED;
  ctx.font = "500 10px ui-monospace, monospace";
  ctx.fillText(`M${fixture.match_number}${fixture.bracket_position ? ` · ${fixture.bracket_position}` : ""}`, x + 8, y + 14);

  // Teams
  const rows = [
    { team: a, score: fixture.score?.team_a, winner: fixture.winner_id === a?.id },
    { team: b, score: fixture.score?.team_b, winner: fixture.winner_id === b?.id },
  ];
  rows.forEach((row, i) => {
    const ry = y + 22 + i * 22;
    // Colour bar
    ctx.fillStyle = row.team?.color || "#333";
    ctx.fillRect(x + 8, ry - 2, 4, 18);
    // Name
    ctx.fillStyle = row.winner ? FG : "#a3a3a3";
    ctx.font = row.winner ? "700 14px ui-monospace, monospace" : "500 14px ui-monospace, monospace";
    const name = row.team?.name ? row.team.name : "TBD";
    ctx.fillText(trimForCanvas(ctx, name, w - 90), x + 18, ry + 12);
    // Score
    ctx.fillStyle = row.winner ? ACCENT : MUTED;
    ctx.font = "700 14px ui-monospace, monospace";
    ctx.textAlign = "right";
    ctx.fillText(scoreLabel(row.score), x + w - 8, ry + 12);
    ctx.textAlign = "left";
  });
}

function scoreLabel(side) {
  if (!side) return "—";
  if (typeof side.runs === "number") return `${side.runs}/${side.wickets ?? 0}`;
  if (typeof side.goals === "number") return `${side.goals}`;
  if (typeof side.points === "number") return `${side.points}`;
  if (typeof side.frames_won === "number") return `${side.frames_won}`;
  if (Array.isArray(side.sets)) return side.sets.join(" ");
  if (typeof side.score === "number") return `${side.score}`;
  return "—";
}

function drawEmpty(ctx) {
  ctx.fillStyle = MUTED;
  ctx.font = "500 16px ui-monospace, monospace";
  ctx.fillText("· No fixtures generated yet ·", 60, 400);
}

function trimForCanvas(ctx, text, maxWidth) {
  if (!text) return "";
  if (ctx.measureText(text).width <= maxWidth) return text;
  let out = text;
  while (out.length > 4 && ctx.measureText(`${out}…`).width > maxWidth) {
    out = out.slice(0, -1);
  }
  return `${out}…`;
}

/** Trigger a share sheet (mobile) or a download (desktop). */
export async function shareOrDownloadBracket({ event, fixtures, teamMap }) {
  const blob = await generateBracketImage({ event, fixtures, teamMap });
  const filename = `bracket-${(event?.name || "event").replace(/[^a-z0-9]/gi, "-").toLowerCase()}.png`;
  const file = new File([blob], filename, { type: "image/png" });
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: event?.name || "Bracket", text: "Tournament bracket" });
      return { shared: true };
    } catch {
      // fall through to download
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return { shared: false };
}
