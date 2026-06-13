export const CURRENCIES = [
  { code: "USD", symbol: "$", label: "USD ($)" },
  { code: "INR", symbol: "₹", label: "INR (₹)" },
];

const SYMBOLS = { USD: "$", INR: "₹" };

export function currencySymbol(code) {
  return SYMBOLS[code] || "$";
}

/**
 * Format a numeric amount with the correct currency symbol and locale separators.
 * Returns e.g. "$1,250", "₹1,25,000".
 */
export function fmtPrice(amount, code = "USD", { decimals = 0, signed = false } = {}) {
  const sym = currencySymbol(code);
  const n = Number(amount) || 0;
  const locale = code === "INR" ? "en-IN" : "en-US";
  const abs = Math.abs(n).toLocaleString(locale, { maximumFractionDigits: decimals, minimumFractionDigits: decimals });
  if (signed) {
    if (n > 0) return `+ ${sym}${abs}`;
    if (n < 0) return `- ${sym}${abs}`;
    return "Included";
  }
  return n < 0 ? `-${sym}${abs}` : `${sym}${abs}`;
}
