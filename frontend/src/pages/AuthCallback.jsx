import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

/**
 * AuthCallback — Emergent-managed Google Auth landing page.
 *
 * Flow:
 *   1. User completes Google consent on auth.emergentagent.com.
 *   2. Redirected here with `#session_id=<opaque>` in the URL fragment.
 *   3. We POST that session_id to `/api/auth/google/session`. Backend
 *      exchanges it with Emergent, finds/provisions the user, sets the
 *      JWT `access_token` cookie, and returns the UserPublic payload.
 *   4. We refresh the AuthContext and route by role.
 */
export default function AuthCallback() {
  const nav = useNavigate();
  const { refreshMe } = useAuth();
  const [status, setStatus] = useState("processing"); // processing | error
  const [message, setMessage] = useState("Signing you in with Google…");

  useEffect(() => {
    const hash = window.location.hash || "";
    const params = new URLSearchParams(hash.startsWith("#") ? hash.slice(1) : hash);
    const sessionId = params.get("session_id");
    if (!sessionId) {
      setStatus("error");
      setMessage("Missing Google session — please try signing in again.");
      return;
    }
    // Scrub the fragment so refreshes don't replay it
    window.history.replaceState({}, document.title, "/auth/callback");
    api.post("/auth/google/session", { session_id: sessionId })
      .then(async ({ data }) => {
        toast.success(`Welcome, ${data.name || data.email}`);
        await refreshMe();
        const role = data.role;
        if (role === "platform_admin" || role === "admin") nav("/platform-admin", { replace: true });
        else if (role === "company_admin" || role === "organiser") nav("/dashboard", { replace: true });
        else if (role === "vendor") nav("/vendor/dashboard", { replace: true });
        else if (role === "player") nav("/players/me", { replace: true });
        else nav("/", { replace: true });
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err.response?.data?.detail || "Google sign-in failed — please try again.");
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center" data-testid="auth-callback">
        {status === "processing" && (
          <>
            <Loader2 className="w-12 h-12 text-[#84CC16] mx-auto animate-spin" />
            <div className="text-lg font-semibold mt-4">Signing you in…</div>
            <div className="text-sm text-neutral-400 mt-1">{message}</div>
          </>
        )}
        {status === "error" && (
          <>
            <AlertCircle className="w-12 h-12 text-[#FF3B30] mx-auto" />
            <div className="text-lg font-semibold mt-4">Sign-in didn&rsquo;t complete</div>
            <div className="text-sm text-neutral-400 mt-1">{message}</div>
            <button
              data-testid="auth-callback-retry"
              onClick={() => nav("/login", { replace: true })}
              className="mt-6 px-6 py-2 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"
            >
              Back to sign-in
            </button>
          </>
        )}
      </div>
    </div>
  );
}
