<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('starboard.eyebrow') }}</div>
      <h1 class="config__title">{{ t('starboard.title') }}</h1>
      <p class="config__sub">{{ t('starboard.sub') }}</p>
    </header>

    <section class="form-card">
      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('starboard.enableLabel') }}</div>
          <div class="row__hint">{{ t('starboard.enableHint') }}</div>
        </div>
        <AppToggle v-model="form.enabled" />
      </div>

      <div class="row">
        <label class="row__label">{{ t('starboard.channelLabel') }}</label>
        <div class="row__hint">{{ t('starboard.channelHint') }}</div>
        <ChannelSelector v-model="form.star_channel_id" :guild-id="guildId" :types="['text', 'announcement']" />
      </div>

      <div class="row-grid">
        <div class="row">
          <label class="row__label" for="sb-emoji">{{ t('starboard.emojiLabel') }}</label>
          <div class="row__hint">{{ t('starboard.emojiHint') }}</div>
          <input id="sb-emoji" v-model="form.emoji" class="input input--narrow" type="text" maxlength="64" placeholder="⭐" />
        </div>
        <div class="row">
          <label class="row__label" for="sb-threshold">{{ t('starboard.thresholdLabel') }}</label>
          <div class="row__hint">{{ t('starboard.thresholdHint') }}</div>
          <input id="sb-threshold" v-model.number="form.threshold" class="input input--narrow" type="number" min="1" max="50" />
        </div>
      </div>

      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('starboard.selfStarLabel') }}</div>
          <div class="row__hint">{{ t('starboard.selfStarHint') }}</div>
        </div>
        <AppToggle v-model="form.self_star" />
      </div>

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

const form = reactive({ enabled: false, star_channel_id: '', emoji: '⭐', threshold: 3, self_star: false })
const saving = ref(false)
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/starboard`)
    if (data?.success) {
      const s = data.settings || {}
      form.enabled = !!s.enabled
      form.star_channel_id = s.star_channel_id || ''
      form.emoji = s.emoji || '⭐'
      form.threshold = s.threshold || 3
      form.self_star = !!s.self_star
      initial = JSON.stringify(form)
    }
  } catch (err) {
    toast.error(t('starboard.loadError'))
  }
}

onMounted(load)
watch(guildId, load)

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/starboard`, {
      enabled: !!form.enabled,
      star_channel_id: form.star_channel_id || null,
      emoji: form.emoji || '⭐',
      threshold: form.threshold || 3,
      self_star: !!form.self_star
    })
    if (data?.success && data.settings) {
      Object.assign(form, {
        enabled: !!data.settings.enabled,
        star_channel_id: data.settings.star_channel_id || '',
        emoji: data.settings.emoji || '⭐',
        threshold: data.settings.threshold || 3,
        self_star: !!data.settings.self_star
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
.input--narrow { max-width: 140px; }

.form-card__actions { display: flex; justify-content: flex-end; }

@media (max-width: 560px) { .row-grid { grid-template-columns: 1fr; } }
</style>
