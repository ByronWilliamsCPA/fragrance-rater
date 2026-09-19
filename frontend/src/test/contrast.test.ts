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
  ['body text on canvas', '--color-text-primary', '--color-canvas', TEXT],
  ['body text on surface', '--color-text-primary', '--color-surface', TEXT],
  ['body text on sunken', '--color-text-primary', '--color-sunken', TEXT],
  ['body text in a field', '--color-text-primary', '--color-field', TEXT],
  ['secondary text on canvas', '--color-text-secondary', '--color-canvas', TEXT],
  ['secondary text on surface', '--color-text-secondary', '--color-surface', TEXT],
  ['muted text on canvas', '--color-text-muted', '--color-canvas', TEXT],
  ['muted text on surface', '--color-text-muted', '--color-surface', TEXT],
  ['muted text on sunken', '--color-text-muted', '--color-sunken', TEXT],
  ['link on canvas', '--color-brand', '--color-canvas', TEXT],
  ['link on surface', '--color-brand', '--color-surface', TEXT],
  ['button label', '--color-on-brand', '--color-brand', TEXT],
  ['button label on hover', '--color-on-brand', '--color-brand-hover', TEXT],
  ['chip text', '--color-brand-subtle-text', '--color-brand-subtle-bg', TEXT],
  ['eyebrow on canvas', '--color-accent', '--color-canvas', TEXT],
  ['eyebrow on surface', '--color-accent', '--color-surface', TEXT],
  ['accent on its own tint', '--color-accent', '--color-accent-subtle-bg', TEXT],
  ['error text', '--color-danger-text', '--color-danger-bg', TEXT],
  ['confirmation text', '--color-warn-text', '--color-warn-bg', TEXT],
  ['notice text', '--color-success-text', '--color-success-bg', TEXT],
  ['info text', '--color-info-text', '--color-info-bg', TEXT],
  ['blind-code text', '--color-sealed-text', '--color-sealed-bg', TEXT],

  // 1.4.11 Non-text Contrast: control boundaries
  ['control border on surface', '--color-border-default', '--color-surface', NON_TEXT],
  ['control border in a field', '--color-border-default', '--color-field', NON_TEXT],
  ['control border on canvas', '--color-border-default', '--color-canvas', NON_TEXT],
  ['emphasised border on surface', '--color-border-strong', '--color-surface', NON_TEXT],
  ['filled button vs canvas', '--color-brand', '--color-canvas', NON_TEXT],
  ['filled button vs surface', '--color-brand', '--color-surface', NON_TEXT],
  ['error border', '--color-danger-border', '--color-surface', NON_TEXT],
  ['confirmation border', '--color-warn-border', '--color-surface', NON_TEXT],
  ['notice border', '--color-success-border', '--color-surface', NON_TEXT],
  ['info border', '--color-info-border', '--color-surface', NON_TEXT],
  ['blind-code border', '--color-sealed-border', '--color-surface', NON_TEXT],

  // 1.4.11 / 2.4.11: the two-tone focus indicator. The ring carries light
  // surfaces; the halo carries the filled brand buttons the ring cannot.
  ['focus ring on canvas', '--color-focus-ring', '--color-canvas', NON_TEXT],
  ['focus ring on surface', '--color-focus-ring', '--color-surface', NON_TEXT],
  ['focus ring in a field', '--color-focus-ring', '--color-field', NON_TEXT],
  ['focus halo on a filled button', '--color-focus-halo', '--color-brand', NON_TEXT],
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
