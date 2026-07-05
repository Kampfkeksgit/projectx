import { onMounted, onBeforeUnmount, unref } from 'vue'

// Gentle default cadence. Live-ish data feels current without hammering the API.
const DEFAULT_INTERVAL = 25000
const MIN_INTERVAL = 5000

/**
 * Keep the current page's data fresh without a manual reload.
 *
 * Re-runs `refetch` when the tab regains focus / becomes visible again and on a
 * gentle interval. It NEVER fetches while the tab is hidden (no background
 * traffic), and it never overlaps its own runs.
 *
 * For pages with editable forms, pass `isDirty` (a ref or a getter). A dirty
 * page is skipped entirely, so an auto-refresh can never clobber the user's
 * unsaved edits — the refresh simply resumes once they save or discard.
 *
 * @param {(reason: string) => any} refetch  Loads/re-loads the page data.
 * @param {object} [options]
 * @param {number} [options.interval]  Poll cadence in ms (default 25000, min 5000).
 * @param {import('vue').Ref<boolean>|(() => boolean)} [options.isDirty]  Skip while true.
 * @param {import('vue').Ref<boolean>|(() => boolean)} [options.enabled]  Gate the whole thing.
 * @returns {{ refreshNow: () => Promise<void> }}
 */
export function useAutoRefresh(refetch, options = {}) {
  const interval = Math.max(MIN_INTERVAL, options.interval ?? DEFAULT_INTERVAL)
  const isDirty = options.isDirty
  const enabled = options.enabled
  let timer = null
  let running = false

  const gate = (v) => (typeof v === 'function' ? v() : unref(v))
  const dirty = () => (isDirty == null ? false : !!gate(isDirty))
  const on = () => (enabled == null ? true : !!gate(enabled))

  async function run(reason) {
    if (typeof document !== 'undefined' && document.hidden) return
    if (running || !on() || dirty()) return
    running = true
    try {
      await refetch(reason)
    } catch {
      // Transient (offline, 5xx, navigating away) — the next tick/focus retries.
    } finally {
      running = false
    }
  }

  const onFocus = () => run('focus')
  const onVisibility = () => { if (!document.hidden) run('visible') }

  onMounted(() => {
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibility)
    timer = setInterval(() => run('poll'), interval)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('focus', onFocus)
    document.removeEventListener('visibilitychange', onVisibility)
    if (timer) { clearInterval(timer); timer = null }
  })

  return { refreshNow: () => run('manual') }
}
