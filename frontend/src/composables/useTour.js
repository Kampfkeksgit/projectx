// Guided onboarding tour — a tiny, dependency-free spotlight tour.
//
// The TourOverlay component renders the active step (a spotlight hole around a
// target element + a tooltip card). Pages trigger it via maybeStart(steps),
// which only fires the first time a user reaches the dashboard (persisted in
// localStorage, same pattern as cookie consent / theme / sidebar collapse).
//
// A step is { selector?, placement?, titleKey, bodyKey }:
//   - selector: CSS selector of the element to highlight (omit for a centered
//     intro/outro card with a plain dark backdrop).
//   - placement: 'top' | 'bottom' | 'left' | 'right' | 'center' (default 'bottom').
//   - titleKey / bodyKey: i18n keys, resolved live in the overlay so the tour
//     follows language switches.

import { reactive, computed } from 'vue'

// Bump the suffix to re-show the tour to everyone after a major redesign.
const STORAGE_KEY = 'projectx_tour_done_v1'

const state = reactive({
  active: false,
  stepIndex: 0,
  steps: []
})

function hasSeenTour() {
  try { return localStorage.getItem(STORAGE_KEY) === '1' } catch { return false }
}

function markSeen() {
  try { localStorage.setItem(STORAGE_KEY, '1') } catch { /* ignore */ }
}

/** Start the tour now (used for an explicit "replay" action). */
function start(steps) {
  if (!Array.isArray(steps) || steps.length === 0) return false
  state.steps = steps
  state.stepIndex = 0
  state.active = true
  return true
}

/** Start only if the user has never seen the tour. Returns true if it started. */
function maybeStart(steps) {
  if (hasSeenTour()) return false
  return start(steps)
}

function next() {
  if (state.stepIndex < state.steps.length - 1) state.stepIndex++
  else finish()
}

function prev() {
  if (state.stepIndex > 0) state.stepIndex--
}

/** Close the tour and remember it so it won't auto-open again. */
function finish() {
  state.active = false
  state.steps = []
  state.stepIndex = 0
  markSeen()
}

// Skip and finish behave the same — both dismiss and persist.
const dismiss = finish

export function useTour() {
  return {
    state,
    hasSeenTour,
    start,
    maybeStart,
    next,
    prev,
    finish,
    dismiss,
    currentStep: computed(() => state.steps[state.stepIndex] || null),
    isFirst: computed(() => state.stepIndex === 0),
    isLast: computed(() => state.stepIndex === state.steps.length - 1),
    total: computed(() => state.steps.length)
  }
}

export default useTour
