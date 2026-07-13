/**
 * Generates a shareable match-result PNG on the client using HTML canvas.
 * Returns a Blob (image/png).
 *
 * The card layout mirrors the small MatchScoreCard on the player profile:
 *   • Hero image (if any) as top banner
 *   • Event name + sport + LOCAL badge
 *   • Team vs team + big score, winner accent
 *   • WON/LOST/TIE chip
 *   • Player of the match / Best batter / etc. chips
 *   • Kreeda Nation footer with player name
 */
const CARD_W = 1080;
const CARD_H = 1350;
const BG = "#0a0a0a";
const ACCENT = "#84CC16";
const FG = "#FFFFFF";
const MUTE = "#9CA3AF";
const AWARD_COLOR = "#F59E0B";

function loadImage(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(null);
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    // If the src is a same-origin relative URL, browsers still hit CORS on
    // toBlob when crossOrigin is set; skip the header for relative refs.
    if (!/^https?:/i.test(src)) img.crossOrigin = "";
    img.src = src;
  });
}

const AWARD_LABELS = {
  mom: "Player of the Match",
  best_batter: "Best Batter",
  best_bowler: "Best Bowler",
  top_scorer: "Top Scorer",
};

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight) {
  const words = String(text || "").split(" ");
  let line = "";
  let lines = 0;
  for (const w of words) {
    const test = line ? line + " " + w : w;
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, y + lines * lineHeight);
      line = w;
      lines++;
    } else {
      line = test;
    }
  }
  if (line) ctx.fillText(line, x, y + lines * lineHeight);
  return (lines + 1) * lineHeight;
}

function pillChip(ctx, text, x, y, { bg = "#1a1a1a", color = MUTE, border = "#2a2a2a", pad = 24, height = 44, fontSize = 20 } = {}) {
  ctx.font = `600 ${fontSize}px "IBM Plex Mono", monospace`;
  const w = ctx.measureText(text.toUpperCase()).width + pad * 2;
  ctx.fillStyle = bg;
  ctx.strokeStyle = border;
  ctx.lineWidth = 2;
  ctx.beginPath();
  const r = height / 2;
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + height, r);
  ctx.arcTo(x + w, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.textBaseline = "middle";
  ctx.fillText(text.toUpperCase(), x + pad, y + height / 2 + 2);
  return w;
}

export async function generateMatchShareImage(match, { playerName = "" } = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext("2d");

  // Background
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, CARD_W, CARD_H);

  // Subtle diagonal accent stripe (Kreeda visual)
  ctx.save();
  ctx.fillStyle = ACCENT + "22"; // ~13% alpha
  ctx.beginPath();
  ctx.moveTo(0, CARD_H - 220);
  ctx.lineTo(CARD_W, CARD_H - 320);
  ctx.lineTo(CARD_W, CARD_H);
  ctx.lineTo(0, CARD_H);
  ctx.closePath();
  ctx.fill();
  ctx.restore();

  // Hero image band
  const heroSrc = match.hero_image_url || match.banner_url || "";
  const heroImg = await loadImage(heroSrc);
  const heroH = 480;
  if (heroImg) {
    // Cover-fit
    const ratio = Math.max(CARD_W / heroImg.width, heroH / heroImg.height);
    const dw = heroImg.width * ratio;
    const dh = heroImg.height * ratio;
    ctx.save();
    ctx.beginPath();
    ctx.rect(60, 60, CARD_W - 120, heroH);
    ctx.clip();
    ctx.drawImage(heroImg, 60 + (CARD_W - 120 - dw) / 2, 60 + (heroH - dh) / 2, dw, dh);
    ctx.restore();
    // Dim overlay
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    ctx.fillRect(60, 60, CARD_W - 120, heroH);
  } else {
    // Placeholder gradient
    const grad = ctx.createLinearGradient(60, 60, 60, 60 + heroH);
    grad.addColorStop(0, "#141414");
    grad.addColorStop(1, "#0a0a0a");
    ctx.fillStyle = grad;
    ctx.fillRect(60, 60, CARD_W - 120, heroH);
  }
  // Border
  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 2;
  ctx.strokeRect(60, 60, CARD_W - 120, heroH);

  // Chip row on hero (sport / local / M#)
  let chipX = 90;
  const chipY = 90;
  chipX += pillChip(ctx, match.sport || "", chipX, chipY, { bg: "#000000CC", border: ACCENT + "55", color: ACCENT }) + 12;
  if (match.is_local_match) {
    chipX += pillChip(ctx, "LOCAL MATCH", chipX, chipY, { bg: ACCENT, border: ACCENT, color: "#000000" }) + 12;
  }
  if (match.match_number != null) {
    pillChip(ctx, `M#${match.match_number}`, chipX, chipY, { bg: "#000000CC", border: "#ffffff33", color: "#ffffff" });
  }
  // Result chip top-right
  const result = match.result || "draw";
  const resultCfg = {
    won: { bg: ACCENT, color: "#000", label: "WON" },
    lost: { bg: "#FF3B30", color: "#fff", label: "LOST" },
    draw: { bg: "#9CA3AF", color: "#000", label: "TIE" },
    live: { bg: "#F59E0B", color: "#000", label: "LIVE" },
  }[result] || { bg: "#9CA3AF", color: "#000", label: "—" };
  ctx.font = `700 32px "IBM Plex Mono", monospace`;
  const rw = ctx.measureText(resultCfg.label).width + 60;
  ctx.fillStyle = resultCfg.bg;
  ctx.fillRect(CARD_W - 90 - rw, chipY, rw, 56);
  ctx.fillStyle = resultCfg.color;
  ctx.textBaseline = "middle";
  ctx.fillText(resultCfg.label, CARD_W - 90 - rw + 30, chipY + 30);

  // Body starts below hero
  const bodyTop = 60 + heroH + 60;

  // Event name — big
  ctx.textBaseline = "top";
  ctx.fillStyle = FG;
  ctx.font = `800 56px "Bebas Neue", "Arial Black", sans-serif`;
  const eventName = (match.event_name || "").toUpperCase();
  const nameHeight = drawWrappedText(ctx, eventName, 90, bodyTop, CARD_W - 180, 64);

  // Scores row
  const scoreY = bodyTop + nameHeight + 40;
  const boxW = (CARD_W - 180 - 40) / 2;
  const boxH = 220;
  const drawTeamBox = (team, x, isWinner) => {
    ctx.fillStyle = isWinner ? ACCENT + "1a" : "#141414";
    ctx.strokeStyle = isWinner ? ACCENT : "rgba(255,255,255,0.12)";
    ctx.lineWidth = 3;
    ctx.fillRect(x, scoreY, boxW, boxH);
    ctx.strokeRect(x, scoreY, boxW, boxH);
    ctx.fillStyle = MUTE;
    ctx.font = `600 22px "IBM Plex Mono", monospace`;
    ctx.textBaseline = "top";
    ctx.fillText((team.name || "TEAM").toUpperCase(), x + 24, scoreY + 24);
    if (isWinner) {
      ctx.fillStyle = AWARD_COLOR;
      ctx.font = `600 20px "IBM Plex Mono", monospace`;
      ctx.fillText("🏆 WINNER", x + 24, scoreY + 56);
    }
    ctx.fillStyle = isWinner ? ACCENT : FG;
    ctx.font = `900 96px "Bebas Neue", "Arial Black", sans-serif`;
    ctx.fillText(String(team.score_display || "—"), x + 24, scoreY + 100);
  };
  drawTeamBox(match.my_team || {}, 90, match.my_team?.is_winner);
  drawTeamBox(match.opp_team || {}, 90 + boxW + 40, !match.my_team?.is_winner && match.result !== "draw");

  // Award chips
  const awards = match.my_awards || [];
  if (awards.length > 0) {
    let ax = 90;
    const ay = scoreY + boxH + 40;
    ctx.font = `700 22px "IBM Plex Mono", monospace`;
    for (const key of awards) {
      const w = pillChip(ctx, AWARD_LABELS[key] || key, ax, ay, {
        bg: AWARD_COLOR + "22", border: AWARD_COLOR, color: AWARD_COLOR, pad: 30, height: 56, fontSize: 22,
      });
      ax += w + 16;
      if (ax > CARD_W - 200) break;
    }
  }

  // Footer — Kreeda Nation + player name
  ctx.fillStyle = FG;
  ctx.font = `900 40px "Bebas Neue", "Arial Black", sans-serif`;
  ctx.fillText("KREEDA NATION", 90, CARD_H - 130);
  ctx.fillStyle = ACCENT;
  ctx.font = `600 22px "IBM Plex Mono", monospace`;
  ctx.fillText("COMPETE · CONNECT · GROW", 90, CARD_H - 80);
  if (playerName) {
    ctx.fillStyle = MUTE;
    ctx.font = `600 24px "IBM Plex Mono", monospace`;
    ctx.textAlign = "right";
    ctx.fillText(("— " + playerName).toUpperCase(), CARD_W - 90, CARD_H - 90);
    ctx.textAlign = "start";
  }

  return await new Promise((resolve) => canvas.toBlob(resolve, "image/png", 0.92));
}

/** Download the generated image + attempt native Web Share when available. */
export async function shareMatchImage(match, { playerName = "" } = {}) {
  const blob = await generateMatchShareImage(match, { playerName });
  if (!blob) return { ok: false, reason: "generation-failed" };
  const filename = `kreeda-${(match.event_name || "match").toLowerCase().replace(/[^a-z0-9]+/g, "-")}.png`;
  const file = new File([blob], filename, { type: "image/png" });

  // Prefer native share (mobile Chrome/Safari + supported PWAs).
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({
        files: [file],
        title: `${match.event_name} — Match result`,
        text: `${match.my_team?.name || "My team"} ${match.my_team?.score_display || ""} vs ${match.opp_team?.score_display || ""} ${match.opp_team?.name || "Opponent"} · via Kreeda Nation`,
      });
      return { ok: true, mode: "native" };
    } catch (err) {
      // User cancelled OR host blocked native share — fall through to
      // download. AbortError is expected on cancel, so don't surface it.
      if (process.env.NODE_ENV !== "production" && err?.name !== "AbortError") {
        console.debug("shareMatchImage native share failed:", err?.message);
      }
    }
  }

  // Fallback: trigger a browser download of the PNG.
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  return { ok: true, mode: "download" };
}
