<template>
  <Teleport to="body">
    <transition name="cookie">
      <aside v-if="visible" class="cookie-banner" role="dialog" aria-live="polite" :aria-label="t('cookieBanner.title')">
        <div class="cookie-banner__inner">
          <h2 class="cookie-banner__title">{{ t('cookieBanner.title') }}</h2>
          <p class="cookie-banner__body">{{ t('cookieBanner.body') }}</p>
          <p class="cookie-banner__learn">
            <router-link to="/legal/datenschutz" @click="onLearnMore">
              {{ t('cookieBanner.learnMore') }}
            </router-link>
          </p>
          <div class="cookie-banner__actions">
            <button type="button" class="cookie-banner__btn cookie-banner__btn--ghost" @click="onNecessary">
              {{ t('cookieBanner.necessaryOnly') }}
            </button>
            <button type="button" class="cookie-banner__btn cookie-banner__btn--primary" @click="onAccept">
              {{ t('cookieBanner.acceptAll') }}
            </button>
          </div>
        </div>
      </aside>
    </transition>
  </Teleport>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

const STORAGE_KEY = 'projectx_cookie_consent'
const SHOW_DELAY_MS = 600

const visible = ref(false)
let showTimer = null

function readConsent() {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function setConsent(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value)
  } catch {
    // localStorage might be unavailable (private mode, SSR-ish, quota)
  }
}

function dismiss(value) {
  setConsent(value)
  visible.value = false
}

function onAccept() {
  dismiss('accepted')
}

function onNecessary() {
  dismiss('necessary')
}

function onLearnMore() {
  // Treat reading the policy as acknowledging the banner so it doesn't
  // float over the privacy page itself.
  dismiss('necessary')
}

onMounted(() => {
  if (readConsent()) return
  showTimer = window.setTimeout(() => {
    visible.value = true
    showTimer = null
  }, SHOW_DELAY_MS)
})

onBeforeUnmount(() => {
  if (showTimer != null) {
    window.clearTimeout(showTimer)
    showTimer = null
  }
})
</script>

<style scoped>
.cookie-banner {
  position: fixed;
  right: var(--space-6);
  bottom: var(--space-6);
  z-index: 9000;
  max-width: 380px;
  width: calc(100vw - 2 * var(--space-6));
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  color: var(--color-text);
}

.cookie-banner__inner {
  padding: var(--space-5) var(--space-5) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.cookie-banner__title {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: -0.015em;
  margin: 0;
  color: var(--color-text);
}

.cookie-banner__body {
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--color-text-muted);
  margin: 0;
}

.cookie-banner__learn {
  margin: 0;
  font-size: 0.82rem;
}

.cookie-banner__learn a {
  color: var(--color-primary);
  border-bottom: 1px solid var(--color-primary);
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.cookie-banner__learn a:hover {
  color: var(--color-primary-hover);
  border-bottom-color: var(--color-primary-hover);
}

.cookie-banner__actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.cookie-banner__btn {
  flex: 1;
  padding: 0.6rem 0.9rem;
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-weight: 600;
  font-size: 0.85rem;
  line-height: 1;
  cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition);
  border: 1px solid transparent;
}

.cookie-banner__btn--primary {
  background: var(--color-primary);
  color: #fff;
  box-shadow: 0 6px 18px -8px rgba(88, 101, 242, 0.7);
}

.cookie-banner__btn--primary:hover {
  background: var(--color-primary-hover);
}

.cookie-banner__btn--ghost {
  background: transparent;
  color: var(--color-text);
  border-color: var(--color-border-strong);
}

.cookie-banner__btn--ghost:hover {
  background: var(--color-surface-2);
}

.cookie-enter-from {
  opacity: 0;
  transform: translateY(20px);
}
.cookie-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
.cookie-enter-active,
.cookie-leave-active {
  transition: opacity var(--transition), transform var(--transition) var(--ease-out-expo);
}

@media (max-width: 640px) {
  .cookie-banner {
    right: var(--space-4);
    left: var(--space-4);
    bottom: var(--space-4);
    max-width: none;
    width: auto;
  }
}
</style>
