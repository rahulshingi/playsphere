import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { QrCode, ScanLine, MapPin, Clock, Check, Loader2 } from "lucide-react";
import QrScannerModal, { parseScanned } from "@/components/QrScannerModal";

function fmtTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function BookingCard({ b, onCheckIn, checking }) {
  const already = Boolean(b.checked_in_at);
  const canCheckIn = b.within_window && !already && b.status !== "completed" && b.status !== "cancelled";
  return (
    <div data-testid={`scan-booking-${b.id}`}
         className="border border-white/10 rounded-sm bg-[#141414] p-4 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-display tracking-wider text-lg text-white">{b.listing_title || "Booking"}</div>
          <div className="text-xs font-mono uppercase text-neutral-500 flex items-center gap-3 mt-1">
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{b.start_time}{b.end_time ? `–${b.end_time}` : ""}</span>
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
          <Check className="w-3 h-3" /> Checked in at {fmtTime(b.checked_in_at)}
        </div>
      ) : canCheckIn ? (
        <Button data-testid={`checkin-btn-${b.id}`} onClick={() => onCheckIn(b)} disabled={checking}
                className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm w-full">
          {checking ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ScanLine className="w-4 h-4 mr-1" />}
          Check in now
        </Button>
      ) : (
        <div className="text-[11px] font-mono text-neutral-500">
          {b.within_window ? "Not open for check-in" : `Available near ${b.start_time}`}
        </div>
      )}
    </div>
  );
}

export default function PlayerCheckIn() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [profile, setProfile] = useState(null);
  const [scanOpen, setScanOpen] = useState(false);
  const [tab, setTab] = useState("qr");
  const [bookings, setBookings] = useState([]);
  const [scannedVendor, setScannedVendor] = useState("");
  const [loadingScan, setLoadingScan] = useState(false);
  const [checkingId, setCheckingId] = useState("");

  useEffect(() => {
    if (!ready) return;
    if (!user) { nav("/players/login"); return; }
    api.get("/players/me").then((r) => setProfile(r.data)).catch(() => {
      toast.error("Unable to load your profile");
    });
  }, [ready, user, nav]);

  const loadVenueBookings = useCallback(async (listingId) => {
    setLoadingScan(true);
    try {
      const { data } = await api.get(`/checkin/venue/${listingId}/my-bookings`);
      setBookings(data || []);
      setScannedVendor(data?.[0]?.vendor_name || "");
      if (!data?.length) toast.info("No active bookings at this venue for today.");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to load bookings for this venue");
    } finally {
      setLoadingScan(false);
    }
  }, []);

  const handleScan = useCallback((decoded) => {
    setScanOpen(false);
    const p = parseScanned(decoded, "listing");
    if (!p || p.kind !== "listing") {
      toast.error("This QR is not a Kreeda Nation venue code.");
      return;
    }
    loadVenueBookings(p.id);
  }, [loadVenueBookings]);

  const handleCheckIn = useCallback(async (b) => {
    setCheckingId(b.id);
    try {
      await api.post(`/checkin/vendor-booking/${b.id}`);
      toast.success("Checked in!");
      // refresh the list to reflect state
      setBookings((prev) => prev.map((x) => x.id === b.id ? { ...x, checked_in_at: new Date().toISOString(), status: "checked_in" } : x));
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
  }, []);

  const qrValue = profile ? `${window.location.origin}/p/${profile.slug || profile.id}` : "";

  if (!ready || !profile) {
    return (
      <div className="bg-[#0a0a0a] min-h-screen text-white">
        <Nav />
        <div className="max-w-3xl mx-auto px-6 py-24 text-center text-neutral-500 font-mono">Loading…</div>
      </div>
    );
  }

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-3xl mx-auto px-6 py-12">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Player</div>
        <h1 className="font-display text-4xl sm:text-5xl tracking-wide mt-2" data-testid="checkin-title">CHECK-IN</h1>
        <p className="text-sm text-neutral-400 mt-2 max-w-2xl">
          Show your QR to the venue staff for a lightning-fast check-in, or scan the venue&apos;s poster QR to check in yourself.
        </p>

        <Tabs value={tab} onValueChange={setTab} className="mt-8">
          <TabsList data-testid="checkin-tabs" className="bg-black/40 border border-white/10 rounded-sm">
            <TabsTrigger data-testid="checkin-tab-qr" value="qr" className="data-[state=active]:bg-[#84CC16] data-[state=active]:text-black rounded-sm">
              <QrCode className="w-4 h-4 mr-1.5" /> My QR
            </TabsTrigger>
            <TabsTrigger data-testid="checkin-tab-scan" value="scan" className="data-[state=active]:bg-[#06B6D4] data-[state=active]:text-black rounded-sm">
              <ScanLine className="w-4 h-4 mr-1.5" /> Scan Venue
            </TabsTrigger>
          </TabsList>

          <TabsContent value="qr" className="mt-6">
            <div className="border border-white/10 rounded-sm bg-[#141414] p-8 flex flex-col items-center gap-4">
              <div className="bg-white p-4 rounded-sm" data-testid="player-qr-code">
                <QRCodeSVG value={qrValue} size={220} level="M" />
              </div>
              <div className="text-center">
                <div className="font-display tracking-wider text-xl">{profile.name?.toUpperCase()}</div>
                <div className="text-xs font-mono text-neutral-500 mt-1">{profile.mobile}</div>
              </div>
              <div className="text-[11px] font-mono text-neutral-500 text-center max-w-sm">
                Show this to the venue when you arrive. They&apos;ll scan it and check you into your active booking.
              </div>
            </div>
          </TabsContent>

          <TabsContent value="scan" className="mt-6">
            <div className="border border-white/10 rounded-sm bg-[#141414] p-6 flex flex-col gap-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-display tracking-wider text-lg">SCAN VENUE POSTER</div>
                  <div className="text-xs text-neutral-500 font-mono mt-1">Point at the QR poster at the venue&apos;s reception.</div>
                </div>
                <Button data-testid="player-open-scanner" onClick={() => setScanOpen(true)}
                        className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
                  <ScanLine className="w-4 h-4 mr-1" /> Open scanner
                </Button>
              </div>

              {scannedVendor && (
                <div className="text-xs font-mono uppercase text-neutral-400 flex items-center gap-1">
                  <MapPin className="w-3 h-3" /> {scannedVendor}
                </div>
              )}

              {loadingScan && <div className="text-neutral-500 text-sm font-mono">Loading your bookings…</div>}

              <div className="grid gap-3" data-testid="scan-results">
                {bookings.map((b) => (
                  <BookingCard key={b.id} b={b} onCheckIn={handleCheckIn} checking={checkingId === b.id} />
                ))}
              </div>

              {!loadingScan && bookings.length === 0 && scannedVendor && (
                <div className="text-xs font-mono text-neutral-500 border border-white/10 p-4 rounded-sm text-center">
                  No active bookings at this venue for today.
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>

      <QrScannerModal
        open={scanOpen}
        onOpenChange={setScanOpen}
        onScan={handleScan}
        title="SCAN VENUE QR"
        description="Aim the camera at the venue's poster."
        testid="player-qr-scanner"
      />
      <Footer />
    </div>
  );
}
