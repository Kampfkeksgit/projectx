// Dashboard theme (dark|light) — applied as a `data-app-theme` attribute on
// <html>, with light-mode token overrides defined in styles/tokens.css.
//
// The per-guild theme lives in the General module's DB settings; this helper
// applies it live and mirrors the last choice into localStorage so main.js can
// re-apply it on the next boot before any settings request resolves (no flash).

const STORAGE_KEY = 'projectx_dashboard_theme'
const THEMES = ['dark', 'light']

export function applyDashboardTheme(theme) {
  const value = THEMES.includes(theme) ? theme : 'dark'
  const el = document.documentElement
  if (value === 'dark') {
    el.removeAttribute('data-app-theme') // dark is the default token set
  } else {
    el.setAttribute('data-app-theme', value)
  }
  try { localStorage.setItem(STORAGE_KEY, value) } catch { /* ignore */ }
  return value
}

export function getStoredTheme() {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return THEMES.includes(v) ? v : 'dark'
  } catch {
    return 'dark'
  }
}

/** Re-apply the last stored theme (called at boot). */
export function initDashboardTheme() {
  applyDashboardTheme(getStoredTheme())
}
