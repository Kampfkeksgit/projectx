<template>
  <div class="config">
    <header class="config__head">
      <div class="config__head-text">
        <div class="config__eyebrow">{{ t('stats.eyebrow') }}</div>
        <h1 class="config__title">{{ t('stats.title') }}</h1>
        <p class="config__sub">{{ t('stats.sub') }}</p>
      </div>
      <AppButton variant="gradient" :disabled="!!draftRow" @click="addDraft">
        <template #icon-left>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </template>
        {{ t('stats.addButton') }}
      </AppButton>
    </header>

    <div class="config__grid config__grid--single">
      <!-- Module settings -->
      <section class="form-card st-settings">
        <div class="st-settings__row">
          <div>
            <div class="st-settings__label">{{ t('stats.enableLabel') }}</div>
            <div class="st-settings__hint">{{ t('stats.enableHint') }}</div>
          </div>
          <AppToggle v-model="settings.enabled" />
        </div>

        <div class="st-settings__row">
          <div>
            <div class="st-settings__label">{{ t('stats.intervalLabel') }}</div>
            <div class="st-settings__hint">{{ t('stats.intervalHint') }}</div>
          </div>
          <select v-model.number="settings.update_interval" class="input input--narrow">
            <option v-for="opt in INTERVAL_OPTIONS" :key="opt" :value="opt">{{ t('stats.intervalMinutes', { n: opt }) }}</option>
          </select>
        </div>

        <div class="st-settings__category">
          <div class="st-settings__label">{{ t('stats.categoryLabel') }}</div>
          <div class="st-settings__hint">{{ t('stats.categoryHint') }}</div>
          <div class="st-mode">
            <button
              type="button"
              class="st-mode__btn"
              :class="{ 'is-active': !settings.auto_category }"
              @click="settings.auto_category = false"
            >{{ t('stats.categoryModeExisting') }}</button>
            <button
              type="button"
              class="st-mode__btn"
              :class="{ 'is-active': settings.auto_category }"
              @click="settings.auto_category = true"
            >{{ t('stats.categoryModeAuto') }}</button>
          </div>

          <div v-if="!settings.auto_category" class="st-settings__category-field">
            <ChannelSelector
              v-model="settings.category_id"
              :guild-id="guildId"
              :types="['category']"
              :placeholder="t('stats.categoryPlaceholder')"
            />
          </div>
          <div v-else class="st-settings__category-field">
            <input
              v-model="settings.category_name"
              class="input"
              type="text"
              maxlength="100"
              :placeholder="t('stats.categoryNamePlaceholder')"
            />
            <div class="st-settings__hint">{{ t('stats.categoryNameHint') }}</div>
          </div>
        </div>

        <div class="st-settings__note">{{ t('stats.presenceNote') }}</div>

        <div class="st-settings__actions">
          <AppButton variant="gradient" :loading="savingSettings" :disabled="!settingsDirty" @click="saveSettings">
            {{ t('common.saveChanges') }}
          </AppButton>
        </div>
      </section>

      <!-- Counters -->
      <section class="config__section">
        <h2 class="config__section-title">{{ t('stats.countersTitle') }}</h2>

        <div class="config__form">
          <transition name="dirty-bar">
            <StatsCounterRow
              v-if="draftRow"
              :model-value="draftRow"
              :saving="draftSaving"
              is-draft
              :guild-id="guildId"
              @save="saveDraft"
              @cancel="cancelDraft"
            />
          </transition>

          <div v-if="loading && counters.length === 0" class="form-card st-state">{{ t('common.loading') }}</div>
          <div v-else-if="!loading && counters.length === 0 && !draftRow" class="form-card st-empty">
            <div class="st-empty__title">{{ t('stats.emptyTitle') }}</div>
            <div class="st-empty__body">{{ t('stats.emptyBody') }}</div>
          </div>

          <StatsCounterRow
            v-for="(row, i) in counters"
            :key="row.id"
            :model-value="row"
            :saving="savingIds.has(row.id)"
            :deleting="deletingIds.has(row.id)"
            :guild-id="guildId"
            :index="i"
            :total="counters.length"
            @save="saveExisting"
            @delete="confirmDelete"
            @move-up="moveCounter($event, 'up')"
            @move-down="moveCounter($event, 'down')"
          />
        </div>
      </section>

      <!-- Graphs -->
      <section class="config__section">
        <div class="config__section-head">
          <h2 class="config__section-title">{{ t('stats.graphsTitle') }}</h2>
          <div class="st-range">
            <button
              v-for="opt in RANGE_OPTIONS"
              :key="opt"
              type="button"
              class="st-range__btn"
              :class="{ 'is-active': range === opt }"
              @click="setRange(opt)"
            >{{ t('stats.rangeDays', { n: opt }) }}</button>
          </div>
        </div>

        <div class="st-charts">
          <StatsChart
            :title="t('stats.chartMembership')"
            :points="snapshots"
            :lines="membershipLines"
            :empty-text="t('stats.graphsEmpty')"
          />
          <StatsChart
            :title="t('stats.chartBoosters')"
            :points="snapshots"
            :lines="boosterLines"
            :empty-text="t('stats.graphsEmpty')"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import AppToggle from '../components/AppToggle.vue'
import ChannelSelector from '../components/ChannelSelector.vue'
import StatsCounterRow from '../components/StatsCounterRow.vue'
import StatsChart from '../components/StatsChart.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()

const guildId = computed(() => route.params.guild_id)

const INTERVAL_OPTIONS = [5, 10, 15, 30, 60]
const RANGE_OPTIONS = [7, 30]

const settings = reactive({
  enabled: false,
  update_interval: 10,
  category_id: '',
  auto_category: false,
  category_name: '📊 Statistics'
})
function settingsSnapshot() {
  return JSON.stringify({
    enabled: settings.enabled,
    update_interval: settings.update_interval,
    category_id: settings.category_id,
    auto_category: settings.auto_category,
    category_name: settings.category_name
  })
}
let settingsInitial = settingsSnapshot()
const settingsDirty = computed(() => settingsSnapshot() !== settingsInitial)
const savingSettings = ref(false)

const counters = ref([])
const loading = ref(false)
const draftRow = ref(null)
const draftSaving = ref(false)
const savingIds = reactive(new Set())
const deletingIds = reactive(new Set())

const snapshots = ref([])
const range = ref(7)

const membershipLines = [
  { key: 'members', label: t('stats.type_members'), color: '#5865f2' },
  { key: 'online', label: t('stats.type_online'), color: '#22c55e' },
  { key: 'offline', label: t('stats.type_offline'), color: '#94a3b8' }
]
const boosterLines = [
  { key: 'boosters', label: t('stats.type_boosters'), color: '#f59e0b' }
]

function emptyCounter() {
  return {
    id: null,
    type: 'members',
    channel_id: '',
    channel_kind: 'voice',
    name_template: '',
    auto_create: true,
    position: counters.value.length,
    enabled: true
  }
}

function normalizeCounter(c) {
  return {
    id: c.id,
    type: c.type || 'members',
    channel_id: c.channel_id || '',
    channel_kind: c.channel_kind === 'text' ? 'text' : 'voice',
    name_template: c.name_template || '',
    auto_create: !!c.auto_create,
    position: Number.isFinite(c.position) ? c.position : 0,
    enabled: !!c.enabled
  }
}

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/stats`)
    if (data?.success) {
      settings.enabled = !!data.settings?.enabled
      settings.update_interval = data.settings?.update_interval || 10
      settings.category_id = data.settings?.category_id || ''
      settings.auto_category = !!data.settings?.auto_category
      settings.category_name = data.settings?.category_name || '📊 Statistics'
      settingsInitial = settingsSnapshot()
      counters.value = Array.isArray(data.counters) ? data.counters.map(normalizeCounter) : []
    }
  } catch (err) {
    counters.value = []
    toast.error(t('stats.loadError'))
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/stats/history`, { params: { days: range.value } })
    snapshots.value = (data?.success && Array.isArray(data.snapshots)) ? data.snapshots : []
  } catch (err) {
    snapshots.value = []
  }
}

onMounted(() => { load(); loadHistory() })
watch(() => guildId.value, () => { load(); loadHistory() })

function setRange(opt) {
  if (range.value === opt) return
  range.value = opt
  loadHistory()
}

async function saveSettings() {
  savingSettings.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/stats`, {
      enabled: !!settings.enabled,
      update_interval: settings.update_interval,
      category_id: settings.category_id || null,
      auto_category: !!settings.auto_category,
      category_name: settings.category_name || '📊 Statistics'
    })
    if (data?.success && data.settings) {
      settings.enabled = !!data.settings.enabled
      settings.update_interval = data.settings.update_interval
      settings.category_id = data.settings.category_id || ''
      settings.auto_category = !!data.settings.auto_category
      settings.category_name = data.settings.category_name || '📊 Statistics'
      settingsInitial = settingsSnapshot()
    }
    toast.success(t('stats.settingsSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    savingSettings.value = false
  }
}

function addDraft() {
  draftRow.value = emptyCounter()
}

function cancelDraft() {
  draftRow.value = null
}

function validate(p) {
  if (!p.auto_create && !p.channel_id) {
    toast.error(t('stats.channelMissing'))
    return false
  }
  return true
}

function serialize(p) {
  return {
    type: p.type,
    channel_id: p.channel_id || null,
    channel_kind: p.channel_kind,
    name_template: String(p.name_template || '').slice(0, 100),
    auto_create: !!p.auto_create,
    position: p.position,
    enabled: !!p.enabled
  }
}

async function saveDraft(payload) {
  if (!validate(payload)) return
  draftSaving.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/stats/counters`, serialize(payload))
    if (data?.success && data.counter) {
      counters.value.push(normalizeCounter(data.counter))
    }
    draftRow.value = null
    toast.success(t('stats.created'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    draftSaving.value = false
  }
}

async function saveExisting(payload) {
  if (!payload?.id) return
  if (!validate(payload)) return
  savingIds.add(payload.id)
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/stats/counters/${payload.id}`, serialize(payload))
    if (data?.success && data.counter) {
      const idx = counters.value.findIndex(c => c.id === payload.id)
      if (idx !== -1) counters.value.splice(idx, 1, normalizeCounter(data.counter))
    }
    toast.success(t('stats.saved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    savingIds.delete(payload.id)
  }
}

async function confirmDelete(row) {
  if (!row?.id) return
  if (typeof window !== 'undefined' && !window.confirm(t('stats.deleteConfirm'))) return
  deletingIds.add(row.id)
  try {
    await api.delete(`/guilds/${guildId.value}/stats/counters/${row.id}`)
    counters.value = counters.value.filter(c => c.id !== row.id)
    toast.success(t('stats.deleted'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingIds.delete(row.id)
  }
}

async function moveCounter(row, dir) {
  const idx = counters.value.findIndex(c => c.id === row.id)
  const swapIdx = dir === 'up' ? idx - 1 : idx + 1
  if (idx < 0 || swapIdx < 0 || swapIdx >= counters.value.length) return

  const arr = counters.value.slice()
  const tmp = arr[idx]
  arr[idx] = arr[swapIdx]
  arr[swapIdx] = tmp
  arr.forEach((c, i) => { c.position = i })
  counters.value = arr

  // Persist the new positions of the two affected rows (best-effort).
  const affected = [arr[idx], arr[swapIdx]]
  try {
    await Promise.all(affected.map(c =>
      api.put(`/guilds/${guildId.value}/stats/counters/${c.id}`, serialize(c))
    ))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  }
}
</script>

<style scoped>
.config__head {
  margin-bottom: var(--space-6);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.config__head-text {
  flex: 1;
  min-width: 0;
}

.config__eyebrow {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-soft);
  margin-bottom: var(--space-2);
}

.config__title {
  font-size: clamp(1.6rem, 2.5vw, 2rem);
  letter-spacing: -0.02em;
  margin-bottom: var(--space-2);
}

.config__sub {
  color: var(--color-text-muted);
}

.config__grid {
  display: grid;
  gap: var(--space-6);
  align-items: flex-start;
}

.config__grid--single {
  grid-template-columns: minmax(0, 920px);
}

.config__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.config__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.config__section-title {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 600;
}

.config__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5) var(--space-6);
  box-shadow: var(--shadow-inset);
}

.st-settings {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.st-settings__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.st-settings__label {
  font-weight: 600;
  font-size: 0.98rem;
}

.st-settings__hint {
  font-size: 0.84rem;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.st-settings__category {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.st-settings__category-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-width: 420px;
}

.st-mode {
  display: inline-flex;
  gap: 4px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  padding: 3px;
  width: fit-content;
}

.st-mode__btn {
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-sm);
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--color-text-muted);
  transition: background var(--transition), color var(--transition);
}

.st-mode__btn.is-active {
  background: var(--gradient-brand);
  color: #fff;
}

.st-settings__note {
  font-size: 0.82rem;
  color: var(--color-warning);
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  line-height: 1.5;
}

.st-settings__actions {
  display: flex;
  justify-content: flex-end;
}

.input {
  padding: 0.6rem 0.85rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.95rem;
}

.input--narrow {
  min-width: 160px;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6' fill='none' stroke='%2399a' stroke-width='2'%3E%3Cpolyline points='1 1 5 5 9 1'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.9rem center;
  padding-right: 2rem;
}

.st-state,
.st-empty {
  text-align: center;
  color: var(--color-text-muted);
}

.st-empty__title {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: var(--space-2);
  color: var(--color-text);
}

.st-empty__body {
  font-size: 0.92rem;
}

.st-range {
  display: inline-flex;
  gap: 4px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  padding: 3px;
}

.st-range__btn {
  padding: 0.4rem 0.85rem;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text-muted);
  transition: background var(--transition), color var(--transition);
}

.st-range__btn.is-active {
  background: var(--gradient-brand);
  color: #fff;
}

.st-charts {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.dirty-bar-enter-active,
.dirty-bar-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}
.dirty-bar-enter-from,
.dirty-bar-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
