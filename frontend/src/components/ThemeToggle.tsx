import { useTheme } from '../hooks/useTheme'

/**
 * Light/dark switch.
 *
 * The visible word names the theme the button will switch *to*, and the
 * accessible name says so in full, so the control is unambiguous without
 * relying on the icon (which is decorative and hidden from assistive tech).
 */
export function ThemeToggle() {
  const { resolved, toggle } = useTheme()
  const next = resolved === 'dark' ? 'light' : 'dark'

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={`Switch to ${next} theme`}
    >
      {next === 'dark' ? 'Dark' : 'Light'}
    </button>
  )
}
