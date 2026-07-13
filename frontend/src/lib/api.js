import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const client = axios.create({
  baseURL: API,
  withCredentials: true,
});

// Silence expected 401s on the anonymous /auth/me probe. Every visitor triggers
// this call once on mount to detect their login state; a 401 simply means "not
// logged in". We swallow the console error so anonymous marketing-site visits
// stay clean of red network banners in devtools while still letting the caller
// handle the promise rejection.
client.interceptors.response.use(
  (r) => r,
  (err) => {
    const url = err?.config?.url || "";
    const status = err?.response?.status;
    if (status === 401 && url.includes("/auth/me")) {
      // Convert to a silent rejection — caller's try/catch still runs.
      return Promise.reject(Object.assign(err, { silent: true }));
    }
    return Promise.reject(err);
  },
);

export default client;

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}
