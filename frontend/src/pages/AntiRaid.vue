<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('antiraid.eyebrow') }}</div>
      <h1 class="config__title">{{ t('antiraid.title') }}</h1>
      <p class="config__sub">{{ t('antiraid.sub') }}</p>
    </header>

    <section class="form-card">
      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('antiraid.enableLabel') }}</div>
          <div class="row__hint">{{ t('antiraid.enableHint') }}</div>
        </div>
        <AppToggle v-model="form.enabled" />
      </div>

      <div class="row">
        <label class="row__label" for="ar-age">{{ t('antiraid.ageLabel') }}</label>
        <div class="row__hint">{{ t('antiraid.ageHint') }}</div>
        <input id="ar-age" v-model.number="form.account_age_days" class="input input--narrow" type="number" min="0" max="3650" />
      </div>

      <div class="row-grid">
        <div class="row">
          <label class="row__label" for="ar-count">{{ t('antiraid.countLabel') }}</label>
          <input id="ar-count" v-model.number="form.join_rate_count" class="input input--narrow" type="number" min="2" max="100" />
        </div>
        <div class="row">
          <label class="row__label" for="ar-seconds">{{ t('antiraid.secondsLabel') }}</label>
          <input id="ar-seconds" v-model.number="form.join_rate_seconds" class="input input--narrow" type="number" min="1" max="600" />
        </div>
      </div>
      <div class="row__hint">{{ t('antiraid.rateHint', { count: form.join_rate_count, seconds: form.join_rate_seconds }) }}</div>

      <div class="row">
        <label class="row__label" for="ar-action">{{ t('antiraid.actionLabel') }}</label>
        <div class="row__hint">{{ t('antiraid.actionHint') }}</div>
        <select id="ar-action" v-model="form.action" class="input input--narrow">
          <option value="alert">{{ t('antiraid.actionAlert') }}</option>
          <option value="kick">{{ t('antiraid.actionKick') }}</option>
          <option value="ban">{{ t('antiraid.actionBan') }}</option>
        </select>
      </div>

      <div class="row">
        <label class="row__label">{{ t('antiraid.alertChannelLabel') }}</label>
        <div class="row__hint">{{ t('antiraid.alertChannelHint') }}</div>
        <ChannelSelector v-model="form.alert_channel_id" :guild-id="guildId" :types="['text', 'announcement']" :placeholder="t('antiraid.alertChannelPlaceholder')" />
      </div>

      <div class="form-card__note">{{ t('antiraid.permNote') }}</div>

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
import AppToggle from '../components/AppToggle.vue'
import ChannelSelector from '../components/ChannelSelector.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const form = reactive({ enabled: false, join_rate_count: 5, join_rate_seconds: 10, action: 'alert', account_age_days: 0, alert_channel_id: '' })
const saving = ref(false)
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/antiraid`)
    if (data?.success) {
      const s = data.settings || {}
      form.enabled = !!s.enabled
      form.join_rate_count = s.join_rate_count ?? 5
      form.join_rate_seconds = s.join_rate_seconds ?? 10
      form.action = s.action || 'alert'
      form.account_age_days = s.account_age_days ?? 0
      form.alert_channel_id = s.alert_channel_id || ''
      initial = JSON.stringify(form)
    }
  } catch (err) {
    toast.error(t('antiraid.loadError'))
  }
}

onMounted(load)
watch(guildId, load)

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/antiraid`, {
      enabled: !!form.enabled,
      join_rate_count: form.join_rate_count,
      join_rate_seconds: form.join_rate_seconds,
      action: form.action,
      account_age_days: form.account_age_days,
      alert_channel_id: form.alert_channel_id || null
    })
    if (data?.success && data.settings) {
      Object.assign(form, {
        enabled: !!data.settings.enabled,
        join_rate_count: data.settings.join_rate_count,
        join_rate_seconds: data.settings.join_rate_seconds,
        action: data.settings.action,
        account_age_days: data.settings.account_age_days,
        alert_channel_id: data.settings.alert_channel_id || ''
      })
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
.row--toggle { flex-direction: row; align-items: center; justify-content: space-between; gap: var(--space-4); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }
.row-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }

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
.input--narrow { max-width: 160px; }
select.input--narrow {
  appearance: none; -webkit-appearance: none;
  background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6' fill='none' stroke='%2399a' stroke-width='2'%3E%3Cpolyline points='1 1 5 5 9 1'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 0.9rem center; padding-right: 2rem;
}

.form-card__note {
  font-size: 0.82rem;
  color: var(--color-warning);
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  line-height: 1.5;
}
.form-card__actions { display: flex; justify-content: flex-end; }

@media (max-width: 560px) { .row-grid { grid-template-columns: 1fr; } }
</style>
