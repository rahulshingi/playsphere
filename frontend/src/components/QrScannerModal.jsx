import { useEffect, useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Camera, X } from "lucide-react";

/**
 * QR camera scanner modal built on top of html5-qrcode.
 *
 * Behaviour:
 *  - Opens the rear camera (falls back to any camera on desktops).
 *  - On successful scan, calls `onScan(decodedText)` exactly once and closes.
 *  - Callers pass a `matcher` regex to extract the id from a URL/raw payload
 *    (e.g. `/p/([\w-]+)` for player QRs). If matcher returns null → shows a
 *    toast and keeps scanning.
 *
 * html5-qrcode is imported dynamically so it doesn't block first paint.
 */
export default function QrScannerModal({ open, onOpenChange, onScan, title, description, testid }) {
  const containerRef = useRef(null);
  const scannerRef = useRef(null);
  const handledRef = useRef(false);
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) return;
    handledRef.current = false;
    setErr("");
    setStarting(true);

    let cancelled = false;
    (async () => {
      try {
        const { Html5Qrcode } = await import("html5-qrcode");
        if (cancelled) return;
        const el = containerRef.current;
        if (!el) return;
        const scanner = new Html5Qrcode(el.id, { verbose: false });
        scannerRef.current = scanner;
        await scanner.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 240, height: 240 } },
          (decodedText) => {
            if (handledRef.current) return;
            handledRef.current = true;
            onScan(decodedText);
          },
          () => { /* scan error frame — ignore */ },
        );
        setStarting(false);
      } catch (e) {
        setStarting(false);
        setErr(e?.message || "Camera not available");
        toast.error("Unable to access camera. Grant permission and retry.");
      }
    })();

    return () => {
      cancelled = true;
      const s = scannerRef.current;
      if (s) {
        s.stop().catch(() => {}).finally(() => { try { s.clear(); } catch { /* noop */ } });
        scannerRef.current = null;
      }
    };
  }, [open, onScan]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid={testid || "qr-scanner-modal"} className="bg-[#141414] text-white border-white/10 max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display tracking-wider text-2xl flex items-center gap-2">
            <Camera className="w-5 h-5 text-[#84CC16]" /> {title || "SCAN QR"}
          </DialogTitle>
          <DialogDescription className="text-neutral-400 text-sm">
            {description || "Point the camera at the QR code. It will scan automatically."}
          </DialogDescription>
        </DialogHeader>

        <div id="kn-qr-reader" ref={containerRef} className="w-full aspect-square bg-black rounded-sm overflow-hidden" data-testid="qr-scanner-viewport" />

        {starting && <div className="text-xs font-mono text-neutral-500 text-center">Starting camera…</div>}
        {err && (
          <div className="text-xs font-mono text-red-400 text-center border border-red-500/40 bg-red-500/10 p-3 rounded-sm">
            {err}
          </div>
        )}

        <Button onClick={() => onOpenChange(false)} variant="outline" className="border-white/10 text-white" data-testid="qr-scanner-close">
          <X className="w-4 h-4 mr-1" /> Cancel
        </Button>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Parses a scanned string and returns a payload of the form
 *   { kind: "player"|"listing", id: string } | null
 *
 * Accepts many friendly formats — a URL of any shape that contains a known
 * path prefix, a bare UUID / long slug, or a prefixed protocol string
 * (`kn:player:<id>`). If a hint kind is provided and the payload looks like
 * a plain id, we honour the hint so both the player and vendor scanners can
 * work with the same person's QR.
 */
export function parseScanned(text, hintKind) {
  const s = String(text || "").trim();
  if (!s) return null;
  // Prefixed protocol form
  const proto = s.match(/^kn:(player|listing):([\w-]+)$/i);
  if (proto) return { kind: proto[1].toLowerCase(), id: proto[2] };
  try {
    // URL form
    const url = new URL(s);
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "p" && parts[1]) return { kind: "player", id: parts[1] };
    if (parts[0] === "players" && parts[1] === "profiles" && parts[2]) return { kind: "player", id: parts[2] };
    if (parts[0] === "players" && parts[1] && parts[1] !== "profiles") return { kind: "player", id: parts[1] };
    if (parts[0] === "vendor-listing" && parts[1]) return { kind: "listing", id: parts[1] };
    if (parts[0] === "vendors" && parts[1]) return { kind: "listing", id: parts[1] };
  } catch {
    /* not a URL — fall through */
  }
  // Bare UUID/slug — treat as the hinted kind (defaults to player when the
  // caller is a vendor's scanner).
  if (/^[\w-]{6,}$/.test(s)) return { kind: hintKind || "player", id: s };
  return null;
}
