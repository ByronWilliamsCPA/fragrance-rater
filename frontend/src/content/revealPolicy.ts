import type { RevealPolicy } from '../api/types'

/**
 * The plain-language name of each reveal policy, lower case so it reads
 * inside a sentence ("Reveal policy: whole household together, ...").
 *
 * One table so the family pilot page, the advanced setup page and the
 * activation warning all name a policy the same way.
 */
export const REVEAL_POLICY_PHRASES: Record<RevealPolicy, string> = {
  ENROLLMENT: 'each evaluator separately',
  HOUSEHOLD: 'whole household together, after the final samples',
}

/** A program's effective policy; a server older than the household policy means per evaluator. */
export function revealPolicyOf(program: { reveal_policy?: RevealPolicy }): RevealPolicy {
  return program.reveal_policy ?? 'ENROLLMENT'
}
