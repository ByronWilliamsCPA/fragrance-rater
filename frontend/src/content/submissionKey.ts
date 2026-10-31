/**
 * One idempotency key per observation submission (R8, architecture review
 * D-22 / Q18).
 *
 * A flaky phone connection can drop the response to a POST that the server
 * already stored; the recorder then presses Save again. The server dedupes on
 * `idempotency_key`, so the retry must carry the same key, and the same
 * client-clock `observed_at` the first attempt stamped, or it would be a
 * different submission. Anything the recorder changes before retrying is a
 * new submission and gets a fresh key. After a save succeeds the next
 * submission always starts fresh, even if its answers are identical: a
 * genuine repeat is a new observation.
 */

export type PendingSubmission = {
  /** Everything the recorder entered, plus the endpoint, as stable JSON. */
  fingerprint: string
  /** Sent as `idempotency_key`; 8-64 of `[A-Za-z0-9_-]`. */
  key: string
  /** The client-clock time the first attempt stamped. */
  observedAt: string
}

function randomKey(): string {
  const source = globalThis.crypto
  if (source && typeof source.randomUUID === 'function') return source.randomUUID()
  const bytes = new Uint8Array(16)
  source.getRandomValues(bytes)
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

/**
 * Returns the submission to send: the pending one when this is a retry of
 * exactly the same answers, otherwise a new one with a fresh key.
 */
export function submissionFor(
  pending: PendingSubmission | null,
  fingerprint: string,
  now: () => string = () => new Date().toISOString(),
  makeKey: () => string = randomKey
): PendingSubmission {
  if (pending && pending.fingerprint === fingerprint) return pending
  return { fingerprint, key: makeKey(), observedAt: now() }
}
