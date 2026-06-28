// Helpers to prevent users from selecting past dates / times in booking flows.
// Works in the user's local timezone (not UTC) so it matches what a user sees
// when they open a browser-native <input type="date"> / <input type="time">.

/** YYYY-MM-DD for "today" in the local timezone. */
export const todayLocalISO = () => {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
};

/** HH:MM for "now" in the local timezone. */
export const nowLocalHHMM = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

/**
 * Returns the minimum allowed time for a <input type="time"> based on the
 * companion date. If the date is today, returns the current HH:MM; otherwise
 * returns undefined (no constraint — the entire day is allowed).
 */
export const minTimeForDate = (selectedDate) => {
  if (!selectedDate) return undefined;
  return selectedDate === todayLocalISO() ? nowLocalHHMM() : undefined;
};

/**
 * Validates a date+time picked by the user. Returns a user-facing error
 * message string if invalid, or null if OK. The `timeStr` is optional —
 * date-only fields can still call this with a missing time.
 */
export const validateFutureDateTime = (dateStr, timeStr) => {
  if (!dateStr) return "Please pick a date";
  const today = todayLocalISO();
  if (dateStr < today) return "Date cannot be in the past";
  if (timeStr && dateStr === today && timeStr < nowLocalHHMM()) {
    return "Time cannot be in the past";
  }
  return null;
};
