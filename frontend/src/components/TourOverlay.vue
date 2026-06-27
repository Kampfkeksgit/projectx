<template>
  <Teleport to="body">
    <transition name="tour-fade">
      <div v-if="tour.state.active && step" class="tour" role="dialog" aria-modal="true" aria-live="polite">
        <!-- Dimmer: a spotlight "hole" around the target, or a plain backdrop for centered steps. -->
        <div
          v-if="rect"
          class="tour__hole"
          :style="holeStyle"
          @click="tour.dismiss()"
        ></div>
        <div v-else class="tour__backdrop" @click="tour.dismiss()"></div>

        <!-- Tooltip card -->
        <div
          ref="cardEl"
          class="tour__card"
          :class="{ 'tour__card--center': isCentered }"
          :style="cardStyle"
          @click.stop
        >
          <div class="tour__progress">
            {{ t('tour.step', { current: tour.state.stepIndex + 1, total: total }) }}
          </div>
          <h3 class="tour__title">{{ t(step.titleKey) }}</h3>
          <p class="tour__body">{{ t(step.bodyKey) }}</p>
          <div class="tour__actions">
            <button type="button" class="tour__skip" @click="tour.dismiss()">{{ t('tour.skip') }}</button>
            <div class="tour__nav">
              <button v-if="!isFirst" type="button" class="tour__btn tour__btn--ghost" @click="tour.prev()">
                {{ t('tour.back') }}
              </button>
              <button type="button" class="tour__btn tour__btn--primary" @click="tour.next()">
                {{ isLast ? t('tour.done') : t('tour.next') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useTour } from '../composables/useTour.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const tour = useTour()
const { currentStep: step, isFirst, isLast, total } = tour

const cardEl = ref(null)
const rect = ref(null)          // target element rect (null → centered step)
const pos = ref({ top: 0, left: 0 })
const isCentered = ref(true)

const GAP = 14        // distance between target and card
const PAD = 8         // spotlight padding around the target
const MARGIN = 12     // min distance from the viewport edges

const holeStyle = computed(() => {
  if (!rect.value) return {}
  return {
    top: `${rect.value.top - PAD}px`,
    left: `${rect.value.left - PAD}px`,
    width: `${rect.value.width + PAD * 2}px`,
    height: `${rect.value.height + PAD * 2}px`
  }
})

const cardStyle = computed(() => {
  if (isCentered.value) return {}
  return { top: `${pos.value.top}px`, left: `${pos.value.left}px` }
})

function findTarget() {
  const sel = step.value?.selector
  if (!sel) return null
  let el = null
  try { el = document.querySelector(sel) } catch { el = null }
  if (!el) return null
  const r = el.getBoundingClientRect()
  // Hidden / collapsed element → fall back to a centered card.
  if (r.width === 0 && r.height === 0) return null
  return { el, r }
}

function placeCard(targetRect) {
  const card = cardEl.value
  if (!card) return
  const cw = card.offsetWidth
  const ch = card.offsetHeight
  const vw = window.innerWidth
  const vh = window.innerHeight
  const placement = step.value?.placement || 'bottom'

  let top
  let left
  switch (placement) {
    case 'right':
      left = targetRect.right + GAP
      top = targetRect.top
      break
    case 'left':
      left = targetRect.left - cw - GAP
      top = targetRect.top
      break
    case 'top':
      top = targetRect.top - ch - GAP
      left = targetRect.left
      break
    case 'bottom':
    default:
      top = targetRect.bottom + GAP
      left = targetRect.left
      break
  }

  // Keep the card fully on screen.
  left = Math.min(Math.max(left, MARGIN), vw - cw - MARGIN)
  top = Math.min(Math.max(top, MARGIN), vh - ch - MARGIN)
  pos.value = { top, left }
}

async function update() {
  if (!tour.state.active || !step.value) return
  const target = findTarget()
  if (!target) {
    rect.value = null
    isCentered.value = true
    return
  }
  isCentered.value = false
  rect.value = target.r
  // Card size is known only after it renders → measure, then position.
  await nextTick()
  placeCard(target.r)
}

function scrollIntoViewIfNeeded() {
  const target = findTarget()
  if (!target) return
  const r = target.r
  const vh = window.innerHeight
  if (r.top < MARGIN || r.bottom > vh - MARGIN) {
    target.el.scrollIntoView({ block: 'center', inline: 'nearest' })
  }
}

// On each step change: scroll the target into view, then measure on the next frame.
watch(
  () => [tour.state.active, tour.state.stepIndex],
  async ([active]) => {
    if (!active) return
    scrollIntoViewIfNeeded()
    // Let the scroll settle before measuring.
    await nextTick()
    requestAnimationFrame(update)
  },
  { immediate: true }
)

function onViewportChange() {
  if (tour.state.active) update()
}

window.addEventListener('resize', onViewportChange)
window.addEventListener('scroll', onViewportChange, true) // capture: catch inner scrollers too

onBeforeUnmount(() => {
  window.removeEventListener('resize', onViewportChange)
  window.removeEventListener('scroll', onViewportChange, true)
})
</script>

<style scoped>
.tour {
  position: fixed;
  inset: 0;
  z-index: 9990;
}

/* Plain dimmer for centered intro/outro steps */
.tour__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(5, 7, 12, 0.72);
  backdrop-filter: blur(1px);
}

/* Spotlight: a transparent box whose giant outer shadow darkens everything else */
.tour__hole {
  position: absolute;
  border-radius: var(--radius-lg);
  box-shadow: 0 0 0 9999px rgba(5, 7, 12, 0.72), 0 0 0 2px var(--color-primary, #5865f2) inset;
  outline: 2px solid rgba(167, 139, 250, 0.7);
  outline-offset: 2px;
  transition: top 0.2s ease, left 0.2s ease, width 0.2s ease, height 0.2s ease;
  pointer-events: auto;
}

.tour__card {
  position: absolute;
  width: min(340px, calc(100vw - 24px));
  background: var(--color-surface, #14171f);
  border: 1px solid var(--color-border-strong, #2a2f3a);
  border-radius: var(--radius-lg, 14px);
  box-shadow: var(--shadow-xl, 0 24px 60px -12px rgba(0, 0, 0, 0.6));
  padding: var(--space-5, 1.25rem);
  z-index: 1;
  transition: top 0.2s ease, left 0.2s ease;
}

.tour__card--center {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.tour__progress {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-soft, #8b93a7);
  margin-bottom: var(--space-2, 0.5rem);
}

.tour__title {
  font-family: var(--font-display, inherit);
  font-size: 1.15rem;
  letter-spacing: -0.01em;
  margin: 0 0 var(--space-2, 0.5rem);
}

.tour__body {
  color: var(--color-text-muted, #b6bdcc);
  font-size: 0.92rem;
  line-height: 1.55;
  margin: 0 0 var(--space-5, 1.25rem);
}

.tour__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3, 0.75rem);
}

.tour__nav {
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
}

.tour__skip {
  background: none;
  border: none;
  color: var(--color-text-soft, #8b93a7);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  padding: 0.4rem 0;
  transition: color var(--transition-fast, 0.15s);
}
.tour__skip:hover { color: var(--color-text, #fff); }

.tour__btn {
  border-radius: var(--radius-md, 10px);
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0.5rem 0.95rem;
  border: 1px solid transparent;
  transition: background var(--transition-fast, 0.15s), border-color var(--transition-fast, 0.15s), transform var(--transition-fast, 0.15s);
}

.tour__btn--ghost {
  background: var(--color-surface-2, #1b1f29);
  border-color: var(--color-border, #232834);
  color: var(--color-text, #fff);
}
.tour__btn--ghost:hover { border-color: var(--color-border-strong, #2a2f3a); }

.tour__btn--primary {
  background: var(--gradient-brand, linear-gradient(135deg, #5865f2, #a78bfa));
  color: #fff;
}
.tour__btn--primary:hover { transform: translateY(-1px); }

.tour-fade-enter-from,
.tour-fade-leave-to { opacity: 0; }
.tour-fade-enter-active,
.tour-fade-leave-active { transition: opacity 0.2s ease; }
</style>
