import { useCallback, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { ScanLine, Clock, Check, Loader2, User } from "lucide-react";
import QrScannerModal, { parseScanned } from "@/components/QrScannerModal";

function fmtTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); } catch { return iso; }
}

/**
 * Vendor-side "Scan Player QR" widget. Renders a button + two dialogs:
 *   1. QrScannerModal — camera scan of a player's QR (contains /p/<slug> URL).
 *   2. Results dialog — lists the player's active bookings today at THIS vendor
 *      (both platform and offline). Vendor taps a row → check-in.
 *
 * onCheckIn: optional parent callback so a listing / bookings widget can
 * refresh after a successful check-in.
 */
export default function VendorScanPlayer({ onCheckIn }) {
  const [scanOpen, setScanOpen] = useState(false);
  const [resultsOpen, setResultsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [bookings, setBookings] = useState([]);
  const [playerName, setPlayerName] = useState("");
  const [checkingId, setCheckingId] = useState("");

  const handleScan = useCallback(async (decoded) => {
    setScanOpen(false);
    const p = parseScanned(decoded, "player");
    if (!p || p.kind !== "player") {
      toast.error("This QR is not a Kreeda Nation player code.");
      return;
    }
    setLoading(true);
    setResultsOpen(true);
    try {
      const { data } = await api.get(`/checkin/player/${p.id}/bookings`);
      setBookings(data || []);
      setPlayerName(data?.[0]?.player_name || "");
      if (!data?.length) toast.info("No active bookings for this player at your venue today.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to look up player bookings");
      setResultsOpen(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleCheckIn = useCallback(async (b) => {
    setCheckingId(b.id);
    const url = b.source === "offline" ? `/checkin/private-booking/${b.id}` : `/checkin/vendor-booking/${b.id}`;
    try {
      await api.post(url);
      toast.success("Checked in!");
      setBookings((prev) => prev.map((x) => x.id === b.id ? { ...x, checked_in_at: new Date().toISOString(), status: "checked_in" } : x));
      onCheckIn?.();
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (e.response?.status === 409 && detail?.checked_in_at) {
        toast.info(`Already checked in at ${fmtTime(detail.checked_in_at)}`);
        setBookings((prev) => prev.map((x) => x.id === b.id ? { ...x, checked_in_at: detail.checked_in_at, status: "checked_in" } : x));
      } else {
        toast.error(typeof detail === "string" ? detail : "Check-in failed");
      }
    } finally {
      setCheckingId("");
    }
  }, [onCheckIn]);

  return (
    <>
      <Button data-testid="vendor-scan-player" onClick={() => setScanOpen(true)}
              className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
        <ScanLine className="w-4 h-4 mr-1.5" /> Scan player QR
      </Button>

      <QrScannerModal
        open={scanOpen}
        onOpenChange={setScanOpen}
        onScan={handleScan}
        title="SCAN PLAYER QR"
        description="Aim the camera at the player's QR shown in their app."
        testid="vendor-qr-scanner"
      />

      <Dialog open={resultsOpen} onOpenChange={setResultsOpen}>
        <DialogContent data-testid="vendor-scan-results" className="bg-[#141414] text-white border-white/10 max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-display tracking-wider text-2xl flex items-center gap-2">
              <User className="w-5 h-5 text-[#84CC16]" /> {playerName ? playerName.toUpperCase() : "PLAYER"}
            </DialogTitle>
            <DialogDescription className="text-neutral-400 text-sm">
              Active bookings at your venue today. Tap one to check-in.
            </DialogDescription>
          </DialogHeader>

          {loading ? (
            <div className="py-8 text-center text-neutral-500 font-mono text-sm">
              <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" /> Loading…
            </div>
          ) : bookings.length === 0 ? (
            <div className="text-xs font-mono text-neutral-500 border border-white/10 p-4 rounded-sm text-center">
              No active bookings for this player today.
            </div>
          ) : (
            <div className="grid gap-3">
              {bookings.map((b) => {
                const already = Boolean(b.checked_in_at);
                const canCheckIn = b.within_window && !already;
                return (
                  <div key={b.id} data-testid={`vendor-scan-booking-${b.id}`}
                       className="border border-white/10 rounded-sm bg-black/40 p-4 flex flex-col gap-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-display tracking-wider text-lg">{b.listing_title || "Booking"}</div>
                        <div className="text-xs font-mono uppercase text-neutral-500 flex items-center gap-2 mt-1">
                          <Clock className="w-3 h-3" />{b.start_time}{b.end_time ? `–${b.end_time}` : ""}
                          {b.sport && <span>· {b.sport}</span>}
                          {b.source === "offline" && <span className="text-[#FACC15]">· OFFLINE</span>}
                        </div>
                      </div>
                      <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-sm ${
                        already ? "bg-[#84CC16]/20 text-[#84CC16] border border-[#84CC16]/40"
                                : b.within_window ? "bg-[#06B6D4]/20 text-[#06B6D4] border border-[#06B6D4]/40"
                                                  : "bg-neutral-800 text-neutral-500 border border-white/10"
                      }`}>{already ? "CHECKED IN" : b.status.toUpperCase()}</span>
                    </div>

                    {already ? (
                      <div className="text-xs font-mono text-[#84CC16] flex items-center gap-1">
                        <Check className="w-3 h-3" /> {fmtTime(b.checked_in_at)}
                      </div>
                    ) : canCheckIn ? (
                      <Button data-testid={`vendor-checkin-btn-${b.id}`} onClick={() => handleCheckIn(b)} disabled={checkingId === b.id}
                              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
                        {checkingId === b.id ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Check className="w-4 h-4 mr-1" />}
                        Check in
                      </Button>
                    ) : (
                      <div className="text-[11px] font-mono text-neutral-500">Available near {b.start_time}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
