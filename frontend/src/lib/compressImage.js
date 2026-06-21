/**
 * Client-side image compression via HTML5 canvas.
 *
 * Used by ImageUpload to shrink user-uploaded photos BEFORE they hit the backend.
 * This keeps server storage small and dramatically reduces upload time on slow networks.
 *
 * Pipeline:
 *   1. Read the chosen File into an in-memory Image.
 *   2. If `maxWidth`/`maxHeight` are exceeded, scale down proportionally with canvas.
 *   3. Re-encode as JPEG at `quality` (default 0.82).
 *   4. If still over `maxBytes`, lower quality in 0.1 steps down to 0.5.
 *
 * Returns a new File ready for upload. Skips compression for SVG/GIF (preserves animation).
 */
export async function compressImage(file, { maxWidth = 1280, maxHeight = 1280, quality = 0.82, maxBytes = 500_000 } = {}) {
  if (!file) return file;
  // Never re-encode GIF (animation) or SVG (vector). Just enforce hard size cap.
  if (file.type === "image/gif" || file.type === "image/svg+xml") {
    if (file.size > 2 * 1024 * 1024) throw new Error("GIF/SVG must be under 2 MB");
    return file;
  }

  const img = await loadImage(file);
  let { width, height } = img;
  const ratio = Math.min(maxWidth / width, maxHeight / height, 1);
  width = Math.round(width * ratio);
  height = Math.round(height * ratio);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, width, height);

  let q = quality;
  let blob = await canvasToBlob(canvas, q);
  // Step quality down until under cap or we hit floor.
  while (blob.size > maxBytes && q > 0.5) {
    q = Math.max(0.5, q - 0.1);
    blob = await canvasToBlob(canvas, q);
  }
  return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg", lastModified: Date.now() });
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e); };
    img.src = url;
  });
}

function canvasToBlob(canvas, quality) {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
}
