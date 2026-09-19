import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Contrast contract for the design tokens.
 *
 * Automated rule scanners (axe-core) check the contrast of text they can see
 * rendered. They do not check a palette, they never check focus-indicator
 * contrast at all, and they only ever see whichever theme the browser happened
 * to be in. The audit that produced this design pass found four separate
 * WCAG 2.2 AA failures that the passing axe suite could not see:
 *
 *   focus ring #b3893e vs page background   2.88:1  (needs 3:1)
 *   focus ring #b3893e vs brand button      2.88:1  (needs 3:1)
 *   input border #bbc8bf on white           1.73:1  (needs 3:1)
 *   pressed-state outline #9bbcaf           1.85:1  (needs 3:1)
 *
 * This test reads the real token values out of tokens.css and re-derives every
 * ratio, in both themes, so a colour cannot regress without failing here.
 */

// Resolved from the Vitest root (frontend/), not from import.meta.url, which
// the jsdom environment serves over a non-file scheme.
const tokensPath = resolve(process.cwd(), 'src/styles/tokens.css')
const source = readFileSync(tokensPath, 'utf8')

/** Extracts a declaration block by its selector, matching braces. */
function block(selector: string): Record<string, string> {
  const start = source.indexOf(`${selector} {`)
  if (start === -1) throw new Error(`Selector not found in tokens.css: ${selector}`)
  const open = source.indexOf('{', start)
  let depth = 0
  let end = open
  for (let index = open; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1
    if (source[index] === '}') {
      depth -= 1
      if (depth === 0) {
        end = index
        break
      }
    }
  }
  const declarations: Record<string, string> = {}
  for (const match of source.slice(open + 1, end).matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g))
    declarations[match[1]] = match[2].trim()
  return declarations
}

const rootTokens = block(':root')
const autoDarkTokens = block(":root:not([data-theme='light'])")
const explicitDarkTokens = block(":root[data-theme='dark']")

const lightTheme = rootTokens
const darkTheme = { ...rootTokens, ...explicitDarkTokens }

function channel(value: number): number {
  const ratio = value / 255
  return ratio <= 0.03928 ? ratio / 12.92 : ((ratio + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const match = /^#([0-9a-f]{6})$/i.exec(hex.trim())
  if (!match) throw new Error(`Expected a 6-digit hex colour, received: ${hex}`)
  const value = match[1]
  return (
    0.2126 * channel(parseInt(value.slice(0, 2), 16)) +
    0.7152 * channel(parseInt(value.slice(2, 4), 16)) +
    0.0722 * channel(parseInt(value.slice(4, 6), 16))
  )
}

function contrast(foreground: string, background: string): number {
  const first = luminance(foreground)
  const second = luminance(background)
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
}

/** WCAG 2.2 AA: 4.5:1 for body text, 3:1 for UI boundaries and state. */
const TEXT = 4.5
const NON_TEXT = 3

type Pair = [description: string, foreground: string, background: string, minimum: number]

const pairs: Pair[] = [
  // 1.4.3 Contrast (Minimum)
  ['ink on paper', '--color-ink', '--color-paper', TEXT],
  ['ink on a raised field', '--color-ink', '--color-paper-raised', TEXT],
  ['ink on a tint', '--color-ink', '--color-tint', TEXT],
  ['secondary ink on paper', '--color-ink-secondary', '--color-paper', TEXT],
  ['secondary ink on a tint', '--color-ink-secondary', '--color-tint', TEXT],
  ['muted ink on paper', '--color-ink-muted', '--color-paper', TEXT],
  ['muted ink on a raised field', '--color-ink-muted', '--color-paper-raised', TEXT],
  ['muted ink on a tint', '--color-ink-muted', '--color-tint', TEXT],
  ['link on paper', '--color-mark', '--color-paper', TEXT],
  ['link on a tint', '--color-mark', '--color-tint', TEXT],
  ['button label', '--color-on-mark', '--color-mark', TEXT],
  ['button label on hover', '--color-on-mark', '--color-mark-hover', TEXT],
  ['text on the mark tint', '--color-mark-tint-ink', '--color-mark-tint', TEXT],
  ['blind code on its own tint', '--color-sealed-ink', '--color-sealed-tint', TEXT],
  ['blind code on paper', '--color-sealed-ink', '--color-paper', TEXT],
  ['error text', '--color-error-ink', '--color-error-bg', TEXT],
  ['confirmation text', '--color-warn-ink', '--color-warn-bg', TEXT],
  ['notice text', '--color-ok-ink', '--color-ok-bg', TEXT],

  // 1.4.11 Non-text Contrast: control boundaries and state
  ['control border on paper', '--color-rule', '--color-paper', NON_TEXT],
  ['control border on a raised field', '--color-rule', '--color-paper-raised', NON_TEXT],
  ['control border on a tint', '--color-rule', '--color-tint', NON_TEXT],
  ['emphasised border on paper', '--color-rule-strong', '--color-paper', NON_TEXT],
  ['filled control vs paper', '--color-mark', '--color-paper', NON_TEXT],
  ['filled control vs a tint', '--color-mark', '--color-tint', NON_TEXT],
  ['sealed border on paper', '--color-sealed-rule', '--color-paper', NON_TEXT],
  ['sealed border on its own tint', '--color-sealed-rule', '--color-sealed-tint', NON_TEXT],
  ['error rule on paper', '--color-error-rule', '--color-paper', NON_TEXT],
  ['confirmation rule on paper', '--color-warn-rule', '--color-paper', NON_TEXT],
  ['notice rule on paper', '--color-ok-rule', '--color-paper', NON_TEXT],

  // 1.4.11 / 2.4.11: the two-tone focus indicator. The ring carries paper
  // surfaces; the halo carries the ink-filled controls the ring cannot.
  ['focus ring on paper', '--color-focus-ring', '--color-paper', NON_TEXT],
  ['focus ring on a raised field', '--color-focus-ring', '--color-paper-raised', NON_TEXT],
  ['focus ring on a tint', '--color-focus-ring', '--color-tint', NON_TEXT],
  ['focus ring on a sealed surface', '--color-focus-ring', '--color-sealed-tint', NON_TEXT],
  ['focus halo on a filled control', '--color-focus-halo', '--color-mark', NON_TEXT],
  ['focus halo against its own ring', '--color-focus-halo', '--color-focus-ring', NON_TEXT],
]

describe.each([
  ['light', lightTheme],
  ['dark', darkTheme],
])('%s theme meets WCAG 2.2 AA contrast', (_themeName, theme) => {
  it.each(pairs)('%s', (_description, foregroundToken, backgroundToken, minimum) => {
    const foreground = theme[foregroundToken]
    const background = theme[backgroundToken]
    expect(foreground, `${foregroundToken} is not defined`).toBeDefined()
    expect(background, `${backgroundToken} is not defined`).toBeDefined()
    expect(contrast(foreground, background)).toBeGreaterThanOrEqual(minimum)
  })
})

describe('theme definitions stay in step', () => {
  /*
   * The dark palette is declared twice: once under prefers-color-scheme for
   * people who never touch the toggle, and once under an explicit
   * [data-theme='dark'] for people who do. Custom properties cannot be
   * aliased across an @media boundary without losing the ability to override
   * them, so the duplication is deliberate. This test is what stops the two
   * copies from drifting, which would give the two groups different colours
   * and silently take one of them out of the contrast contract above.
   */
  it('declares identical colours in both dark-theme blocks', () => {
    const colourOnly = (declarations: Record<string, string>) =>
      Object.fromEntries(
        Object.entries(declarations).filter(([name]) => name.startsWith('--color-'))
      )

    expect(colourOnly(autoDarkTokens)).toEqual(colourOnly(explicitDarkTokens))
  })

  it('overrides every colour token the light theme defines', () => {
    const lightColours = Object.keys(rootTokens).filter((name) => name.startsWith('--color-'))
    const darkColours = Object.keys(explicitDarkTokens).filter((name) =>
      name.startsWith('--color-')
    )

    expect(darkColours.sort()).toEqual(lightColours.sort())
  })
})
