<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('music.eyebrow') }}</div>
      <h1 class="config__title">{{ t('music.title') }}</h1>
      <p class="config__sub">{{ t('music.sub') }}</p>
    </header>

    <div class="form-card note">{{ t('music.usageNote') }}</div>

    <!-- ===== Live player ===== -->
    <div class="form-card mu-player">
      <div class="mu-player__head">
        <h2 class="card-title">{{ t('music.nowPlaying') }}</h2>
        <span class="mu-player__status" :class="state.connected ? 'is-on' : 'is-off'">
          {{ state.connected ? t('music.connected') : t('music.idle') }}
        </span>
      </div>

      <div v-if="state.current" class="mu-now">
        <img v-if="state.current.artwork" :src="state.current.artwork" class="mu-now__art" alt="" />
        <div v-else class="mu-now__art mu-now__art--placeholder">🎵</div>
        <div class="mu-now__meta">
          <a v-if="state.current.uri" :href="state.current.uri" target="_blank" rel="noopener" class="mu-now__title">{{ state.current.title }}</a>
          <span v-else class="mu-now__title">{{ state.current.title }}</span>
          <div class="mu-now__sub">{{ state.current.author || '—' }} · {{ fmtMs(state.current.length_ms) }}</div>
          <div class="mu-now__badges">
            <span v-if="state.paused" class="mu-badge is-warn">{{ t('music.paused') }}</span>
            <span class="mu-badge">🔊 {{ state.volume }}%</span>
            <span v-if="state.loop_mode !== 'off'" class="mu-badge">🔁 {{ t('music.loop_' + state.loop_mode) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="mu-empty">{{ t('music.nothingPlaying') }}</div>

      <!-- Controls -->
      <div class="mu-controls">
        <button class="mu-btn" :disabled="!state.connected || busy" @click="control(state.paused ? 'resume' : 'pause')" :title="state.paused ? t('music.resume') : t('music.pause')">
          {{ state.paused ? '▶️' : '⏸️' }}
        </button>
        <button class="mu-btn" :disabled="!state.connected || busy" @click="control('skip')" :title="t('music.skip')">⏭️</button>
        <button class="mu-btn" :disabled="!state.connected || busy" @click="control('shuffle')" :title="t('music.shuffle')">🔀</button>
        <button class="mu-btn" :disabled="!state.connected || busy" @click="cycleLoop" :title="t('music.loop')">🔁</button>
        <button class="mu-btn mu-btn--danger" :disabled="!state.connected || busy" @click="control('stop')" :title="t('music.stop')">⏹️</button>
        <div class="mu-vol">
          <span>🔊</span>
          <input type="range" min="0" max="150" step="5" :value="state.volume" :disabled="!state.connected || busy" @change="setVolume($event)" />
          <span class="mu-vol__val">{{ state.volume }}%</span>
        </div>
      </div>

      <!-- Queue -->
      <div class="mu-queue">
        <div class="mu-queue__head">
          <span>{{ t('music.upNext') }} <span class="mu-queue__count">{{ state.queue.length }}</span></span>
          <button v-if="state.queue.length" class="mu-clear" :disabled="busy" @click="control('clear')">{{ t('music.clearQueue') }}</button>
        </div>
        <div v-if="!state.queue.length" class="mu-empty mu-empty--small">{{ t('music.queueEmpty') }}</div>
        <ul v-else class="mu-list">
          <li v-for="(tr, i) in state.queue" :key="i" class="mu-list__row">
            <span class="mu-list__idx">{{ i + 1 }}</span>
            <span class="mu-list__title">{{ tr.title }}</span>
            <span class="mu-list__time">{{ fmtMs(tr.length_ms) }}</span>
            <button class="mu-list__del" :disabled="busy" :title="t('music.remove')" @click="control('remove', i)">✕</button>
          </li>
        </ul>
      </div>
    </div>

    <!-- ===== Settings ===== -->
    <div class="form-card">
      <h2 class="card-title">{{ t('music.settingsTitle') }}</h2>

      <label class="mu-toggle">
        <AppToggle v-model="form.enabled" />
        <span>
          <span class="mu-toggle__label">{{ t('music.enableLabel') }}</span>
          <span class="mu-toggle__hint">{{ t('music.enableHint') }}</span>
        </span>
      </label>

      <div class="form-row">
        <label class="form-row__label">{{ t('music.djRoleLabel') }}</label>
        <RoleSelector v-model="form.dj_role_id" :guild-id="guildId" :placeholder="t('music.djRolePlaceholder')" />
        <div class="form-row__hint">{{ t('music.djRoleHint') }}</div>
      </div>

      <div class="mu-grid">
        <div class="form-row">
          <label class="form-row__label">{{ t('music.defaultVolumeLabel') }}</label>
          <div class="mu-inline"><input v-model.number="form.default_volume" class="input input--narrow" type="number" min="0" max="150" /> <span>%</span></div>
        </div>
        <div class="form-row">
          <label class="form-row__label">{{ t('music.autoDisconnectLabel') }}</label>
          <div class="mu-inline"><input v-model.number="autoDisconnectMin" class="input input--narrow" type="number" min="0" max="60" /> <span>{{ t('music.minutes') }}</span></div>
          <div class="form-row__hint">{{ t('music.autoDisconnectHint') }}</div>
        </div>
        <div class="form-row">
          <label class="form-row__label">{{ t('music.maxQueueLabel') }}</label>
          <input v-model.number="form.max_queue" class="input input--narrow" type="number" min="1" max="500" />
        </div>
      </div>

      <div class="form-row">
        <label class="form-row__label">{{ t('music.sourcesLabel') }}</label>
        <div class="form-row__hint">{{ t('music.sourcesHint') }}</div>
        <div class="mu-sources">
          <label class="mu-source"><AppToggle v-model="form.allow_soundcloud" /> <span>SoundCloud</span></label>
          <label class="mu-source"><AppToggle v-model="form.allow_bandcamp" /> <span>Bandcamp</span></label>
          <label class="mu-source"><AppToggle v-model="form.allow_twitch" /> <span>Twitch</span></label>
          <label class="mu-source"><AppToggle v-model="form.allow_http" /> <span>{{ t('music.sourceHttp') }}</span></label>
        </div>
      </div>

      <div class="config__footer">
        <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.save') }}</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import AppToggle from '../components/AppToggle.vue'
import RoleSelector from '../components/RoleSelector.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { useAutoRefresh } from '../composables/useAutoRefresh.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const saving = ref(false)
const busy = ref(false)
let initial = '{}'
let pollTimer = null

function emptyForm() {
  return {
    enabled: false, dj_role_id: '', default_volume: 100, auto_disconnect_seconds: 300,
    max_queue: 100, allow_soundcloud: true, allow_bandcamp: true, allow_http: true, allow_twitch: true
  }
}
const form = reactive(emptyForm())
const state = reactive({ connected: false, current: null, queue: [], paused: false, volume: 100, loop_mode: 'off' })

const autoDisconnectMin = computed({
  get: () => Math.round((form.auto_disconnect_seconds || 0) / 60),
  set: (v) => { form.auto_disconnect_seconds = Math.max(0, Math.min(60, Number(v) || 0)) * 60 }
})
const dirty = computed(() => JSON.stringify(form) !== initial)

function fmtMs(ms) {
  const s = Math.floor((ms || 0) / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

async function loadSettings() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/music`)
    if (data?.success) { Object.assign(form, data.settings); initial = JSON.stringify(form) }
  } catch { /* premium lock handles 403 at the layout level */ }
}

async function loadState() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/music/state`)
    if (data?.success) Object.assign(state, data.state)
  } catch { /* ignore transient */ }
}

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/music`, { ...form })
    if (data?.success) { Object.assign(form, data.settings); initial = JSON.stringify(form); toast.success(t('toast.saved')) }
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}

async function control(action, payload) {
  busy.value = true
  try {
    await api.post(`/guilds/${guildId.value}/music/control`, { action, payload })
    setTimeout(loadState, 800)
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    setTimeout(() => { busy.value = false }, 600)
  }
}

function setVolume(e) { control('volume', Number(e.target.value)) }
function cycleLoop() {
  const next = state.loop_mode === 'off' ? 'track' : state.loop_mode === 'track' ? 'queue' : 'off'
  control('loop', next)
}

function startPolling() {
  stopPolling()
  loadState()
  pollTimer = setInterval(loadState, 4000)
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

onMounted(() => { loadSettings(); startPolling() })
onUnmounted(stopPolling)
watch(guildId, () => { loadSettings(); startPolling() })
// Refresh only the settings on focus/interval; skip while the form is dirty.
// The live player state keeps its own 4s polling loop above (untouched).
useAutoRefresh(loadSettings, { isDirty: () => dirty.value })
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }
.form-card { max-width: 820px; background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5) var(--space-6); box-shadow: var(--shadow-inset); margin-bottom: var(--space-5); }
.note { color: var(--color-text-muted); font-size: 0.88rem; }
.card-title { font-family: var(--font-display); font-size: 1.1rem; font-weight: 600; margin-bottom: var(--space-4); }

.mu-player__head { display: flex; align-items: center; justify-content: space-between; }
.mu-player__status { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding: 2px 8px; border-radius: var(--radius-sm); color: #fff; }
.mu-player__status.is-on { background: var(--color-success); }
.mu-player__status.is-off { background: var(--color-text-soft); }

.mu-now { display: flex; gap: var(--space-4); align-items: center; margin: var(--space-4) 0; }
.mu-now__art { width: 72px; height: 72px; border-radius: var(--radius-md); object-fit: cover; flex-shrink: 0; }
.mu-now__art--placeholder { display: flex; align-items: center; justify-content: center; font-size: 1.8rem; background: var(--color-surface-2); }
.mu-now__meta { min-width: 0; }
.mu-now__title { font-weight: 600; font-size: 1.05rem; color: var(--color-text); text-decoration: none; }
.mu-now__title:hover { color: var(--color-primary); }
.mu-now__sub { color: var(--color-text-muted); font-size: 0.85rem; margin: 2px 0 6px; }
.mu-now__badges { display: flex; gap: 6px; flex-wrap: wrap; }
.mu-badge { font-size: 0.72rem; padding: 2px 8px; border-radius: var(--radius-sm); background: var(--color-surface-2); border: 1px solid var(--color-border-strong); color: var(--color-text-muted); }
.mu-badge.is-warn { background: rgba(245,158,11,0.15); color: var(--color-warning); border-color: transparent; }
.mu-empty { text-align: center; color: var(--color-text-muted); padding: var(--space-4); }
.mu-empty--small { padding: var(--space-2); font-size: 0.85rem; }

.mu-controls { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; padding: var(--space-3) 0; border-top: 1px solid var(--color-border); }
.mu-btn { font-size: 1.1rem; width: 42px; height: 38px; border-radius: var(--radius-md); background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); transition: border-color var(--transition), background var(--transition); }
.mu-btn:hover:not(:disabled) { border-color: var(--color-primary); background: var(--color-surface-2); }
.mu-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.mu-btn--danger:hover:not(:disabled) { border-color: var(--color-danger); }
.mu-vol { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.mu-vol input[type=range] { width: 120px; }
.mu-vol__val { font-family: var(--font-mono); font-size: 0.78rem; min-width: 3.2em; }

.mu-queue { border-top: 1px solid var(--color-border); padding-top: var(--space-3); }
.mu-queue__head { display: flex; align-items: center; justify-content: space-between; font-weight: 600; font-size: 0.9rem; margin-bottom: var(--space-2); }
.mu-queue__count { color: var(--color-text-soft); font-family: var(--font-mono); }
.mu-clear { font-size: 0.78rem; color: var(--color-text-soft); }
.mu-clear:hover:not(:disabled) { color: var(--color-danger); }
.mu-list { display: flex; flex-direction: column; gap: 2px; }
.mu-list__row { display: grid; grid-template-columns: 28px 1fr auto 28px; align-items: center; gap: var(--space-2); padding: 4px 6px; border-radius: var(--radius-sm); }
.mu-list__row:hover { background: var(--color-surface-2); }
.mu-list__idx { font-family: var(--font-mono); font-size: 0.78rem; color: var(--color-text-soft); }
.mu-list__title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mu-list__time { font-family: var(--font-mono); font-size: 0.76rem; color: var(--color-text-muted); }
.mu-list__del { color: var(--color-text-soft); }
.mu-list__del:hover:not(:disabled) { color: var(--color-danger); }

.mu-toggle { display: flex; align-items: center; gap: var(--space-3); cursor: pointer; margin-bottom: var(--space-4); }
.mu-toggle__label { display: block; font-weight: 600; font-size: 0.95rem; }
.mu-toggle__hint { display: block; font-size: 0.82rem; color: var(--color-text-muted); }
.form-row { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-4); }
.form-row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.form-row__hint { font-size: 0.82rem; color: var(--color-text-muted); }
.input { width: 100%; padding: 0.6rem 0.8rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-size: 0.92rem; }
.input--narrow { max-width: 110px; width: 110px; }
.mu-inline { display: flex; align-items: center; gap: 8px; }
.mu-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-4); }
.mu-sources { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.mu-source { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.config__footer { display: flex; justify-content: flex-end; padding-top: var(--space-2); }

@media (max-width: 640px) { .mu-grid { grid-template-columns: 1fr; } }
</style>
