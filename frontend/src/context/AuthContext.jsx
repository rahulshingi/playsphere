import { createContext, useContext, useEffect, useMemo, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { devError } from "@/lib/devLog";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null); // null = checking
  const [ready, setReady] = useState(false);
  // "primary" = show the account's original role nav (vendor / HR / sponsor / …)
  // "player" = show only the player nav for dual-role users. Persisted in
  // localStorage so a mode switch survives page reloads.
  const [activeMode, setActiveModeState] = useState(() => {
    try { return localStorage.getItem("kn_active_mode") || "primary"; } catch { return "primary"; }
  });
  const setActiveMode = (m) => {
    setActiveModeState(m);
    try { localStorage.setItem("kn_active_mode", m); } catch { /* noop */ }
  };

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        setUser(data);
      } catch {
        setUser(false);
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const login = async (email, password) => {
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setUser(data);
      return { ok: true, user: data };
    } catch (e) {
      return { ok: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  const register = async (email, password, name) => {
    try {
      const { data } = await api.post("/auth/register", { email, password, name });
      setUser(data);
      return { ok: true, user: data };
    } catch (e) {
      return { ok: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  const signupCompany = async (body) => {
    try {
      const { data } = await api.post("/companies/signup", body);
      setUser(data);
      return { ok: true, user: data };
    } catch (e) {
      return { ok: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  const signupOrganiser = async (body) => {
    try {
      const { data } = await api.post("/organisers/signup", body);
      setUser(data);
      return { ok: true, user: data };
    } catch (e) {
      return { ok: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  const refreshMe = async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      return data;
    } catch {
      setUser(false);
      return null;
    }
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (err) {
      devError("[AuthContext] Logout request failed:", err);
    }
    setUser(false);
    // Reset mode on logout so the next user starts on their primary nav.
    setActiveMode("primary");
  };

  // Whether the user is actually operating as a player right now.
  // - Native players are always in "player" mode implicitly.
  // - Dual-role users toggle via the nav dropdown; `activeMode==="player"`
  //   collapses their nav to only player links so the UI stays clean.
  const inPlayerMode = !!user && (
    user.role === "player" ||
    (user.also_player === true && activeMode === "player")
  );

  // Memoise the context value so consumers only re-render when auth state
  // actually changes — a new object identity on every provider render would
  // otherwise cascade a full app re-render on unrelated state updates.
  const contextValue = useMemo(() => ({
    user,
    ready,
    login,
    register,
    signupCompany,
    signupOrganiser,
    refreshMe,
    logout,
    isAdmin: !!user && (user.role === "admin" || user.role === "platform_admin" || user.role === "company_admin" || user.role === "organiser"),
    isPlatformAdmin: !!user && (user.role === "platform_admin" || user.role === "admin"),
    isSuperAdmin: !!user && (user.role === "platform_admin" || user.role === "admin") && !!user.is_super_admin,
    adminPermissions: (user && user.permissions) || [],
    hasPermission: (perm) => !!user && (user.role === "platform_admin" || user.role === "admin") && (user.is_super_admin || (user.permissions || []).includes(perm)),
    isCompanyAdmin: !!user && (user.role === "company_admin" || user.role === "organiser"),
    isOrganiser: !!user && user.role === "organiser",
    // Native player role OR any user (HR/organiser/admin) who opted in
    // as a player via `POST /auth/also-player`. Every place we check
    // `isPlayer` also needs to be reachable by these dual-role users —
    // /players/me, /admin (host match), match-history, etc.
    isPlayer: !!user && (user.role === "player" || user.also_player === true),
    // NEW — reflects the active *view* mode. When a dual-role user picks
    // "Switch to player mode" from the nav dropdown, we set this so the nav
    // hides their primary-role links and shows only the player links.
    activeMode,
    setActiveMode,
    inPlayerMode,
    isVendor: !!user && user.role === "vendor",
    isSponsor: !!user && user.role === "sponsor",
    isScorer: !!user && user.role === "scorer",
    canSponsor: !!user && (user.role === "sponsor" || user.role === "company_admin"),
    companyId: user && user.company_id,
    companyName: user && user.company_name,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [user, ready, activeMode]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
