/**
 * The participant-instrument build this page was served from, or null for a
 * development build. Injected at build time (`VITE_INSTRUMENT_VERSION`) and
 * matched to the `INSTRUMENT_VERSION` the backend records at activation.
 */
export function instrumentVersion(configured = import.meta.env.VITE_INSTRUMENT_VERSION) {
  const value = configured?.trim()
  return value ? value : null
}
