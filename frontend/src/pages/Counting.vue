<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('counting.eyebrow') }}</div>
      <h1 class="config__title">{{ t('counting.title') }}</h1>
      <p class="config__sub">{{ t('counting.sub') }}</p>
    </header>

    <section class="form-card">
      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('counting.enableLabel') }}</div>
          <div class="row__hint">{{ t('counting.enableHint') }}</div>
        </div>
        <AppToggle v-model="form.enabled" />
      </div>

      <div class="row">
        <label class="row__label">{{ t('counting.channelLabel') }}</label>
        <div class="row__hint">{{ t('counting.channelHint') }}</div>
        <ChannelSelector v-model="form.channel_id" :guild-id="guildId" :types="['text']" />
      </div>

      <div class="row-grid">
        <div class="row">
          <label class="row__label" for="ct-emoji">{{ t('counting.emojiLabel') }}</label>
          <input id="ct-emoji" v-model="form.count_emoji" class="input input--narrow" type="text" maxlength="64" placeholder="✅" />
        </div>
        <div class="row row--toggle">
          <div>
            <div class="row__label">{{ t('counting.resetLabel') }}</div>
            <div class="row__hint">{{ t('counting.resetHint') }}</div>
          </div>
          <AppToggle v-model="form.reset_on_fail" />
        </div>
      </div>

      <div class="stat-grid">
        <div class="stat">
          <div class="stat__value">{{ current }}</div>
          <div class="stat__label">{{ t('counting.currentLabel') }}</div>
        </div>
        <div class="stat">
          <div class="stat__value">{{ high }}</div>
          <div class="stat__label">{{ t('counting.highLabel') }}</div>
        </div>
      </div>

      <div class="form-card__note form-card__note--info">{{ t('counting.usageNote') }}</div>

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

const form = reactive({ enabled: false, channel_id: '', count_emoji: '✅', reset_on_fail: true })
const current = ref(0)
const high = ref(0)
const saving = ref(false)
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/counting`)
    if (data?.success) {
      const s = data.settings || {}
      form.enabled = !!s.enabled
      form.channel_id = s.channel_id || ''
      form.count_emoji = s.count_emoji || '✅'
      form.reset_on_fail = s.reset_on_fail !== false
      current.value = s.current_count || 0
      high.value = s.high_score || 0
      initial = JSON.stringify(form)
    }
  } catch (err) {
    toast.error(t('counting.loadError'))
  }
}

onMounted(load)
watch(guildId, load)

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/counting`, {
      enabled: !!form.enabled,
      channel_id: form.channel_id || null,
      count_emoji: form.count_emoji || '✅',
      reset_on_fail: !!form.reset_on_fail
    })
    if (data?.success && data.settings) {
      current.value = data.settings.current_count || 0
      high.value = data.settings.high_score || 0
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
.form-card { max-width: 720px; background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-6); box-shadow: var(--shadow-inset); display: flex; flex-direction: column; gap: var(--space-5); }
.row { display: flex; flex-direction: column; gap: var(--space-2); }
.row--toggle { flex-direction: row; align-items: center; justify-content: space-between; gap: var(--space-4); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }
.row-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); align-items: start; }
.input { width: 100%; padding: 0.7rem 0.85rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.95rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--narrow { max-width: 140px; }
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.stat { background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-4); text-align: center; }
.stat__value { font-family: var(--font-mono); font-size: 1.6rem; font-weight: 700; color: var(--color-text); }
.stat__label { font-size: 0.78rem; color: var(--color-text-soft); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
.form-card__note { font-size: 0.82rem; border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); line-height: 1.5; }
.form-card__note--info { color: var(--color-text-muted); background: var(--color-bg-elevated); border: 1px solid var(--color-border); }
.form-card__actions { display: flex; justify-content: flex-end; }
@media (max-width: 560px) { .row-grid, .stat-grid { grid-template-columns: 1fr; } }
</style>
