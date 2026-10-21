/**
 * Splits a pasted or typed run of entries. Houses often paste a published
 * list ("Bergamot, pink pepper, cardamom"); one entry per comma, semicolon,
 * or line keeps the order they gave.
 */
export function splitEntries(raw: string): string[] {
  return raw
    .split(/[,;\n]/)
    .map((entry) => entry.trim())
    .filter(Boolean)
}
