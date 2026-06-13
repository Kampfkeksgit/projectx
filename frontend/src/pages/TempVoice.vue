<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('tempvoice.eyebrow') }}</div>
      <h1 class="config__title">{{ t('tempvoice.title') }}</h1>
      <p class="config__sub">{{ t('tempvoice.sub') }}</p>
    </header>

    <section class="form-card">
      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('tempvoice.enableLabel') }}</div>
          <div class="row__hint">{{ t('tempvoice.enableHint') }}</div>
        </div>
        <AppToggle v-model="form.enabled" />
      </div>

      <div class="row">
        <label class="row__label">{{ t('tempvoice.hubLabel') }}</label>
        <div class="row__hint">{{ t('tempvoice.hubHint') }}</div>
        <ChannelSelector v-model="form.hub_channel_id" :guild-id="guildId" :types="['voice']" />
      </div>

      <div class="row">
        <label class="row__label">{{ t('tempvoice.categoryLabel') }}</label>
        <div class="row__hint">{{ t('tempvoice.categoryHint') }}</div>
        <ChannelSelector v-model="form.category_id" :guild-id="guildId" :types="['category']" :placeholder="t('tempvoice.categoryPlaceholder')" />
      </div>

      <div class="row">
        <label class="row__label" for="tv-name">{{ t('tempvoice.nameLabel') }}</label>
        <div class="row__hint">{{ t('tempvoice.nameHint') }}</div>
        <input id="tv-name" v-model="form.name_template" class="input" type="text" maxlength="100" placeholder="🔊 {user}" />
      </div>

      <div class="row">
        <label class="row__label" for="tv-limit">{{ t('tempvoice.limitLabel') }}</label>
        <div class="row__hint">{{ t('tempvoice.limitHint') }}</div>
        <input id="tv-limit" v-model.number="form.user_limit" class="input input--narrow" type="number" min="0" max="99" />
      </div>

      <div class="form-card__note">{{ t('tempvoice.permNote') }}</div>

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

const form = reactive({ enabled: false, hub_channel_id: '', category_id: '', name_template: '🔊 {user}', user_limit: 0 })
const saving = ref(false)
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/tempvoice`)
    if (data?.success) {
      const s = data.settings || {}
      form.enabled = !!s.enabled
      form.hub_channel_id = s.hub_channel_id || ''
      form.category_id = s.category_id || ''
      form.name_template = s.name_template || '🔊 {user}'
      form.user_limit = s.user_limit || 0
      initial = JSON.stringify(form)
    }
  } catch (err) {
    toast.error(t('tempvoice.loadError'))
  }
}

onMounted(load)
watch(guildId, load)

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/tempvoice`, {
      enabled: !!form.enabled,
      hub_channel_id: form.hub_channel_id || null,
      category_id: form.category_id || null,
      name_template: form.name_template || '🔊 {user}',
      user_limit: form.user_limit || 0
    })
    if (data?.success && data.settings) {
      Object.assign(form, {
        enabled: !!data.settings.enabled,
        hub_channel_id: data.settings.hub_channel_id || '',
        category_id: data.settings.category_id || '',
        name_template: data.settings.name_template || '🔊 {user}',
        user_limit: data.settings.user_limit || 0
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
.input--narrow { max-width: 140px; }

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
</style>
