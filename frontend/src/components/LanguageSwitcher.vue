<template>
  <div class="lang" :class="{ 'is-open': open }" @click.stop="toggle">
    <svg class="lang__globe" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10"/>
      <line x1="2" y1="12" x2="22" y2="12"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
    <span class="lang__code">{{ currentFlag }}</span>
    <svg class="lang__chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <polyline points="6 9 12 15 18 9"/>
    </svg>

    <transition name="menu">
      <div v-if="open" class="lang__menu" @click.stop>
        <div class="lang__menu-label">{{ t('language.label') }}</div>
        <button
          v-for="l in SUPPORTED_LOCALES"
          :key="l.code"
          class="lang__option"
          :class="{ 'is-active': locale === l.code }"
          @click="choose(l.code)"
        >
          <span class="lang__option-flag">{{ l.flag }}</span>
          <span class="lang__option-label">{{ l.label }}</span>
          <svg v-if="locale === l.code" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n, SUPPORTED_LOCALES } from '../i18n/index.js'

const { t, locale, setLocale } = useI18n()
const open = ref(false)

const currentFlag = computed(() =>
  SUPPORTED_LOCALES.find(l => l.code === locale.value)?.flag || locale.value.toUpperCase()
)

function toggle() {
  open.value = !open.value
}

function choose(code) {
  setLocale(code)
  open.value = false
}

function onDocClick() {
  if (open.value) open.value = false
}

onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<style scoped>
.lang {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.4rem 0.65rem;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  user-select: none;
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
}

.lang:hover,
.lang.is-open {
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text);
  border-color: var(--color-border-strong);
}

.lang__globe { opacity: 0.85; }

.lang__chev {
  opacity: 0.7;
  transition: transform var(--transition-fast);
}
.lang.is-open .lang__chev { transform: rotate(180deg); }

.lang__menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 200px;
  background: rgba(22, 26, 35, 0.96);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  padding: var(--space-2);
  box-shadow: var(--shadow-lg);
  z-index: 60;
}

.lang__menu-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-text-soft);
  padding: var(--space-2) var(--space-3);
}

.lang__option {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: 0.55rem var(--space-3);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.lang__option:hover {
  background: var(--color-surface-2);
}

.lang__option.is-active {
  background: var(--color-primary-soft);
  color: #fff;
}

.lang__option-flag {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-muted);
}

.lang__option.is-active .lang__option-flag {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.lang__option-label {
  flex: 1;
}

.menu-enter-active,
.menu-leave-active {
  transition: opacity 140ms ease, transform 140ms ease;
}
.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
