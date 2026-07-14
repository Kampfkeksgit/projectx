<template>
  <div class="config">
    <header class="config__head">
      <div class="config__head-text">
        <div class="config__eyebrow">{{ t('minecraft.eyebrow') }}</div>
        <h1 class="config__title">{{ t('minecraft.title') }}</h1>
        <p class="config__sub">{{ t('minecraft.sub') }}</p>
      </div>
      <AppButton variant="gradient" :disabled="!!draftRow" @click="addDraft">
        <template #icon-left>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </template>
        {{ t('minecraft.addServer') }}
      </AppButton>
    </header>

    <div class="config__grid config__grid--single">
      <section class="config__form">
        <transition name="dirty-bar">
          <MinecraftServerRow
            v-if="draftRow"
            :model-value="draftRow"
            :saving="draftSaving"
            is-draft
            :guild-id="guildId"
            @save="saveDraft"
            @cancel="cancelDraft"
          />
        </transition>

        <div v-if="loading && servers.length === 0" class="form-card mc-state">{{ t('common.loading') }}</div>
        <div v-else-if="!loading && servers.length === 0 && !draftRow" class="form-card mc-empty">
          <div class="mc-empty__title">{{ t('minecraft.emptyTitle') }}</div>
          <div class="mc-empty__body">{{ t('minecraft.emptyBody') }}</div>
        </div>

        <MinecraftServerRow
          v-for="row in servers"
          :key="row.id"
          :model-value="row"
          :saving="savingIds.has(row.id)"
          :deleting="deletingIds.has(row.id)"
          :guild-id="guildId"
          @save="saveExisting"
          @delete="confirmDelete"
        />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import MinecraftServerRow from '../components/MinecraftServerRow.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { useAutoRefresh } from '../composables/useAutoRefresh.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()

const guildId = computed(() => route.params.guild_id)

const servers = ref([])
const loading = ref(false)
const draftRow = ref(null)
const draftSaving = ref(false)
const savingIds = reactive(new Set())
const deletingIds = reactive(new Set())

function emptyDraft() {
  return {
    id: null,
    name: '',
    address: '',
    edition: 'java',
    channel_id: '',
    notify_mode: 'plain',
    message_template: '',
    embed: null,
    name_channel_id: '',
    name_template: '',
    enabled: true,
    status: 'unknown'
  }
}

function normalize(s) {
  return {
    id: s.id,
    name: s.name || '',
    address: s.address || '',
    edition: s.edition === 'bedrock' ? 'bedrock' : 'java',
    channel_id: s.channel_id || '',
    notify_mode: s.notify_mode === 'embed' ? 'embed' : 'plain',
    message_template: s.message_template || '',
    embed: s.embed && typeof s.embed === 'object' ? s.embed : null,
    name_channel_id: s.name_channel_id || '',
    name_template: s.name_template || '',
    enabled: !!s.enabled,
    status: s.status || 'unknown',
    ping_ms: s.ping_ms ?? -1
  }
}

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/minecraft`)
    servers.value = (data?.success && Array.isArray(data.servers))
      ? data.servers.map(normalize)
      : []
  } catch (err) {
    servers.value = []
    toast.error(t('minecraft.loadError'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => guildId.value, load)
// Keep the server list + live status fresh; skip while adding a new draft.
// Individual rows keep their own unsaved edits (no re-hydrate while dirty).
useAutoRefresh(load, { isDirty: () => !!draftRow.value })

function addDraft() {
  draftRow.value = emptyDraft()
}

function cancelDraft() {
  draftRow.value = null
}

function validate(p) {
  if (!p.address || !String(p.address).trim()) {
    toast.error(t('minecraft.addressHint'))
    return false
  }
  // A status message channel OR a status-as-name channel is required.
  if (!p.channel_id && !p.name_channel_id) {
    toast.error(t('minecraft.channelRequired'))
    return false
  }
  return true
}

function serialize(p) {
  return {
    name: String(p.name || '').slice(0, 100),
    address: String(p.address).trim().slice(0, 200),
    edition: p.edition === 'bedrock' ? 'bedrock' : 'java',
    channel_id: p.channel_id || null,
    notify_mode: p.notify_mode === 'embed' ? 'embed' : 'plain',
    message_template: String(p.message_template || '').slice(0, 1000),
    embed: p.embed || undefined,
    name_channel_id: p.name_channel_id || null,
    name_template: String(p.name_template || '').slice(0, 100),
    enabled: !!p.enabled
  }
}

function handleSaveError(err) {
  toast.error(err.response?.data?.error || t('toast.failedToSave'))
}

async function saveDraft(payload) {
  if (!validate(payload)) return
  draftSaving.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/minecraft`, serialize(payload))
    if (data?.success && data.server) {
      servers.value.push(normalize(data.server))
    }
    draftRow.value = null
    toast.success(t('minecraft.created'))
  } catch (err) {
    handleSaveError(err)
  } finally {
    draftSaving.value = false
  }
}

async function saveExisting(payload) {
  if (!payload?.id) return
  if (!validate(payload)) return
  savingIds.add(payload.id)
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/minecraft/${payload.id}`, serialize(payload))
    if (data?.success && data.server) {
      const idx = servers.value.findIndex(s => s.id === payload.id)
      if (idx !== -1) servers.value.splice(idx, 1, normalize(data.server))
    }
    toast.success(t('minecraft.save'))
  } catch (err) {
    handleSaveError(err)
  } finally {
    savingIds.delete(payload.id)
  }
}

async function confirmDelete(row) {
  if (!row?.id) return
  if (typeof window !== 'undefined' && !window.confirm(t('minecraft.deleteConfirm'))) return
  deletingIds.add(row.id)
  try {
    await api.delete(`/guilds/${guildId.value}/minecraft/${row.id}`)
    servers.value = servers.value.filter(s => s.id !== row.id)
    toast.success(t('minecraft.deleted'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingIds.delete(row.id)
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

.config__head-text { flex: 1; min-width: 0; }

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

.config__sub { color: var(--color-text-muted); }

.config__grid { display: grid; gap: var(--space-5); align-items: flex-start; }
.config__grid--single { grid-template-columns: minmax(0, 980px); }

.config__form { display: flex; flex-direction: column; gap: var(--space-4); }

.form-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5) var(--space-6);
  box-shadow: var(--shadow-inset);
}

.mc-state { color: var(--color-text-muted); text-align: center; }
.mc-empty { text-align: center; }
.mc-empty__title { font-family: var(--font-display); font-size: 1.05rem; font-weight: 600; margin-bottom: var(--space-2); }
.mc-empty__body { color: var(--color-text-muted); font-size: 0.92rem; }

.dirty-bar-enter-active,
.dirty-bar-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.dirty-bar-enter-from,
.dirty-bar-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
