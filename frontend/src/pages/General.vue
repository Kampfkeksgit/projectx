<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('general.eyebrow') }}</div>
      <h1 class="config__title">{{ t('general.title') }}</h1>
      <p class="config__sub">{{ t('general.sub') }}</p>
    </header>

    <section class="form-card">
      <!-- Language -->
      <div class="row">
        <label class="row__label" for="gen-lang">{{ t('general.languageLabel') }}</label>
        <div class="row__hint">{{ t('general.languageHint') }}</div>
        <select id="gen-lang" v-model="form.language" class="input">
          <option v-for="l in LANGUAGES" :key="l.code" :value="l.code">{{ l.name }}</option>
        </select>
      </div>

      <!-- Timezone -->
      <div class="row">
        <label class="row__label" for="gen-tz">{{ t('general.timezoneLabel') }}</label>
        <div class="row__hint">{{ t('general.timezoneHint') }}</div>
        <select id="gen-tz" v-model="form.timezone" class="input">
          <option v-for="tz in TIMEZONES" :key="tz" :value="tz">{{ tz }}</option>
        </select>
      </div>

      <!-- Embed color -->
      <div class="row">
        <label class="row__label" for="gen-color">{{ t('general.embedColorLabel') }}</label>
        <div class="row__hint">{{ t('general.embedColorHint') }}</div>
        <div class="color-row">
          <input id="gen-color" v-model="colorPicker" class="color-swatch" type="color" />
          <input
            v-model="form.embed_color"
            class="input input--narrow"
            type="text"
            maxlength="7"
            placeholder="#5865F2"
            @blur="normalizeColor"
          />
          <span class="color-preview" :style="{ background: previewColor }"></span>
        </div>
      </div>

      <!-- Dashboard theme -->
      <div class="row">
        <label class="row__label">{{ t('general.themeLabel') }}</label>
        <div class="row__hint">{{ t('general.themeHint') }}</div>
        <div class="theme-grid">
          <button
            v-for="th in THEMES"
            :key="th.key"
            type="button"
            class="theme-card"
            :class="[`theme-card--${th.key}`, { 'is-active': form.dashboard_theme === th.key }]"
            @click="selectTheme(th.key)"
          >
            <span class="theme-card__preview" :class="`theme-card__preview--${th.key}`">
              <span class="theme-card__bar"></span>
              <span class="theme-card__bar theme-card__bar--short"></span>
            </span>
            <span class="theme-card__name">{{ t(`general.theme_${th.key}`) }}</span>
          </button>
        </div>
      </div>

      <div class="form-card__note form-card__note--info">{{ t('general.usageNote') }}</div>

      <div class="form-card__actions">
        <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.saveChanges') }}</AppButton>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { applyDashboardTheme } from '../composables/useDashboardTheme.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

// Kept in sync with GENERAL_LANGUAGES / GENERAL_TIMEZONES / GENERAL_THEMES in backend/db.js.
const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'de', name: 'Deutsch' },
  { code: 'tr', name: 'Türkçe' },
  { code: 'ru', name: 'Русский' },
  { code: 'pl', name: 'Polski' }
]
const TIMEZONES = [
  'UTC',
  'Europe/London', 'Europe/Berlin', 'Europe/Paris', 'Europe/Madrid', 'Europe/Rome',
  'Europe/Istanbul', 'Europe/Moscow', 'Europe/Warsaw', 'Europe/Athens',
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Sao_Paulo', 'America/Mexico_City',
  'Asia/Dubai', 'Asia/Kolkata', 'Asia/Shanghai', 'Asia/Tokyo', 'Asia/Singapore',
  'Australia/Sydney', 'Pacific/Auckland'
]
const THEMES = [{ key: 'dark' }, { key: 'light' }]
const HEX_RE = /^#[0-9A-Fa-f]{6}$/

const form = reactive({ language: 'en', timezone: 'UTC', embed_color: '#5865F2', dashboard_theme: 'dark' })
const saving = ref(false)
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

const previewColor = computed(() => (HEX_RE.test(form.embed_color) ? form.embed_color : '#5865F2'))

// Two-way bridge between the native color picker and the hex text field.
const colorPicker = computed({
  get: () => previewColor.value,
  set: (v) => { form.embed_color = v }
})

function normalizeColor() {
  if (!HEX_RE.test(form.embed_color)) form.embed_color = '#5865F2'
}

function selectTheme(key) {
  form.dashboard_theme = key
  applyDashboardTheme(key) // live preview
}

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/general`)
    if (data?.success) {
      const s = data.settings || {}
      form.language = s.language || 'en'
      form.timezone = s.timezone || 'UTC'
      form.embed_color = s.embed_color || '#5865F2'
      form.dashboard_theme = s.dashboard_theme || 'dark'
      applyDashboardTheme(form.dashboard_theme)
      initial = JSON.stringify(form)
    }
  } catch (err) {
    toast.error(t('general.loadError'))
  }
}

onMounted(load)
watch(guildId, load)

async function save() {
  saving.value = true
  try {
    normalizeColor()
    const { data } = await api.put(`/guilds/${guildId.value}/general`, {
      language: form.language,
      timezone: form.timezone,
      embed_color: form.embed_color,
      dashboard_theme: form.dashboard_theme
    })
    if (data?.success && data.settings) {
      Object.assign(form, {
        language: data.settings.language || 'en',
        timezone: data.settings.timezone || 'UTC',
        embed_color: data.settings.embed_color || '#5865F2',
        dashboard_theme: data.settings.dashboard_theme || 'dark'
      })
      applyDashboardTheme(form.dashboard_theme)
      initial = JSON.stringify(form)
    }
    toast.success(t('common.allSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }

.form-card {
  max-width: 720px;
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-inset);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.row { display: flex; flex-direction: column; gap: var(--space-2); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }

.input {
  width: 100%;
  padding: 0.7rem 0.85rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.95rem;
}
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--narrow { max-width: 140px; font-family: var(--font-mono); }

.color-row { display: flex; align-items: center; gap: var(--space-3); }
.color-swatch {
  width: 46px;
  height: 42px;
  padding: 0;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  cursor: pointer;
}
.color-preview {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-inset);
}

.theme-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); max-width: 360px; }
.theme-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-bg-elevated);
  transition: border-color var(--transition-fast), transform var(--transition-fast);
}
.theme-card:hover { transform: translateY(-1px); border-color: var(--color-border-strong); }
.theme-card.is-active { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.theme-card__preview {
  height: 48px;
  border-radius: var(--radius-sm);
  padding: 8px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.theme-card__preview--dark { background: #0b0d12; }
.theme-card__preview--light { background: #f4f6fb; border-color: rgba(0, 0, 0, 0.08); }
.theme-card__bar { height: 6px; border-radius: 3px; }
.theme-card__bar--short { width: 60%; }
.theme-card__preview--dark .theme-card__bar { background: #2e3650; }
.theme-card__preview--light .theme-card__bar { background: #cbd5e1; }
.theme-card__name { font-size: 0.85rem; font-weight: 600; color: var(--color-text); text-align: center; }

.form-card__note {
  font-size: 0.82rem;
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  line-height: 1.5;
}
.form-card__note--info {
  color: var(--color-text-muted);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
}

.form-card__actions { display: flex; justify-content: flex-end; }
</style>
