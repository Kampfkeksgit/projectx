<template>
  <div class="row">
    <label class="row__label">{{ t('games.languageLabel') }}</label>
    <div class="row__hint">{{ t('games.languageHint') }}</div>
    <select class="lang-select" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
      <option v-for="l in LANGUAGES" :key="l.key" :value="l.key">{{ l.label }}</option>
    </select>
  </div>
</template>

<script setup>
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

defineProps({ modelValue: { type: String, default: 'en' } })
defineEmits(['update:modelValue'])

// Language display names stay in their native form (UI-locale independent).
// Keys mirror GAME_LANGUAGES in backend db.js + game_i18n.py in the bot.
const LANGUAGES = [
  { key: 'en', label: 'English' },
  { key: 'de', label: 'Deutsch' },
  { key: 'tr', label: 'Türkçe' },
  { key: 'ru', label: 'Русский' },
  { key: 'pl', label: 'Polski' }
]
</script>

<style scoped>
.row { display: flex; flex-direction: column; gap: var(--space-2); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }
.lang-select { width: 100%; padding: 0.7rem 0.85rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.95rem; cursor: pointer; }
.lang-select:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
</style>
