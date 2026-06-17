<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('rps.eyebrow') }}</div>
      <h1 class="config__title">{{ t('rps.title') }}</h1>
      <p class="config__sub">{{ t('rps.sub') }}</p>
    </header>

    <section class="form-card">
      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('rps.enableLabel') }}</div>
          <div class="row__hint">{{ t('rps.enableHint') }}</div>
        </div>
        <AppToggle v-model="form.enabled" />
      </div>

      <div class="row">
        <label class="row__label">{{ t('rps.channelLabel') }}</label>
        <div class="row__hint">{{ t('rps.channelHint') }}</div>
        <ChannelSelector v-model="form.games_channel_id" :guild-id="guildId" :types="['text']" />
      </div>

      <div class="form-card__note form-card__note--info">{{ t('rps.usageNote') }}</div>

      <div class="form-card__actions">
        <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.saveChanges') }}</AppButton>
      </div>
    </section>

    <section class="form-card lb-card">
      <h2 class="lb-card__title">{{ t('rps.leaderboardTitle') }}</h2>
      <div v-if="leaderboard.length === 0" class="lb-empty">{{ t('rps.leaderboardEmpty') }}</div>
      <table v-else class="lb-table">
        <thead>
          <tr><th>#</th><th>{{ t('rps.playerCol') }}</th><th class="num">{{ t('rps.winsCol') }}</th><th class="num">{{ t('rps.playsCol') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="e in leaderboard" :key="e.user_id">
            <td>{{ e.rank }}</td>
            <td class="mono">{{ e.user_id }}</td>
            <td class="num">{{ e.wins }}</td>
            <td class="num">{{ e.plays }}</td>
          </tr>
        </tbody>
      </table>
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

const gameKey = 'rps'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const form = reactive({ enabled: false, games_channel_id: '' })
const leaderboard = ref([])
const saving = ref(false)
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/games`)
    if (data?.success) {
      const s = data.settings || {}
      form.enabled = !!s[`${gameKey}_enabled`]
      form.games_channel_id = s.games_channel_id || ''
      initial = JSON.stringify(form)
    }
  } catch (err) {
    toast.error(t('rps.loadError'))
  }
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/games/leaderboard?game=${gameKey}`)
    leaderboard.value = (data?.success && Array.isArray(data.leaderboard)) ? data.leaderboard : []
  } catch {
    leaderboard.value = []
  }
}

onMounted(load)
watch(guildId, load)

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/games`, {
      [`${gameKey}_enabled`]: !!form.enabled,
      games_channel_id: form.games_channel_id || null
    })
    if (data?.success) initial = JSON.stringify(form)
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
.form-card { max-width: 720px; background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-6); box-shadow: var(--shadow-inset); display: flex; flex-direction: column; gap: var(--space-5); margin-bottom: var(--space-5); }
.row { display: flex; flex-direction: column; gap: var(--space-2); }
.row--toggle { flex-direction: row; align-items: center; justify-content: space-between; gap: var(--space-4); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }
.input { width: 100%; padding: 0.7rem 0.85rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.95rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.form-card__note { font-size: 0.82rem; border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); line-height: 1.5; }
.form-card__note--info { color: var(--color-text-muted); background: var(--color-bg-elevated); border: 1px solid var(--color-border); }
.form-card__actions { display: flex; justify-content: flex-end; }
.lb-card__title { font-size: 1.1rem; }
.lb-empty { color: var(--color-text-muted); font-size: 0.9rem; }
.lb-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.lb-table th, .lb-table td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--color-border); }
.lb-table th { color: var(--color-text-soft); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; }
.lb-table .num { text-align: right; font-family: var(--font-mono); }
.lb-table .mono { font-family: var(--font-mono); font-size: 0.82rem; color: var(--color-text-muted); }
</style>
