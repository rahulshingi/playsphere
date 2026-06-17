/**
 * Lightweight dev-only logger. In production builds (process.env.NODE_ENV === 'production')
 * the logger silently swallows messages so we don't leak debugging info or burn cycles.
 * In dev/test, messages are forwarded to console.error for visibility.
 */
const isDev = process.env.NODE_ENV !== "production";

export const devError = (...args) => {
  if (isDev) {
    // eslint-disable-next-line no-console
    console.error(...args);
  }
};

export const devWarn = (...args) => {
  if (isDev) {
    // eslint-disable-next-line no-console
    console.warn(...args);
  }
};

export const devLog = (...args) => {
  if (isDev) {
    // eslint-disable-next-line no-console
    console.log(...args);
  }
};
