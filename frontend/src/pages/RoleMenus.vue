<template>
  <div class="config">
    <header class="config__head">
      <div class="config__head-text">
        <div class="config__eyebrow">{{ t('rolemenus.eyebrow') }}</div>
        <h1 class="config__title">{{ t('rolemenus.title') }}</h1>
        <p class="config__sub">{{ t('rolemenus.sub') }}</p>
      </div>
      <AppButton variant="gradient" :disabled="!!draftRow" @click="addDraft">
        <template #icon-left>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </template>
        {{ t('rolemenus.addButton') }}
      </AppButton>
    </header>

    <div class="config__form">
      <transition name="dirty-bar">
        <RoleMenuRow v-if="draftRow" :model-value="draftRow" :saving="draftSaving" is-draft :guild-id="guildId" @save="saveDraft" @cancel="cancelDraft" />
      </transition>

      <div v-if="loading && rows.length === 0" class="form-card state">{{ t('common.loading') }}</div>
      <div v-else-if="!loading && rows.length === 0 && !draftRow" class="form-card empty">
        <div class="empty__title">{{ t('rolemenus.emptyTitle') }}</div>
        <div class="empty__body">{{ t('rolemenus.emptyBody') }}</div>
      </div>

      <RoleMenuRow
        v-for="row in rows"
        :key="row.id"
        :model-value="row"
        :saving="savingIds.has(row.id)"
        :deleting="deletingIds.has(row.id)"
        :guild-id="guildId"
        @save="saveExisting"
        @delete="confirmDelete"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import RoleMenuRow from '../components/RoleMenuRow.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const rows = ref([])
const loading = ref(false)
const draftRow = ref(null)
const draftSaving = ref(false)
const savingIds = reactive(new Set())
const deletingIds = reactive(new Set())

function defaultEmbed() {
  return { title: '', description: '', color: '#5865F2', thumbnail: '', image: '', footer: '', show_timestamp: false, author_name: '', author_icon_url: '' }
}

function emptyDraft() {
  return { id: null, name: '', channel_id: '', menu_type: 'buttons', exclusive: false, use_embed: false, embed: defaultEmbed(), message_id: null, options: [{ role_id: '', label: '', emoji: '' }] }
}

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/rolemenus`)
    rows.value = (data?.success && Array.isArray(data.menus)) ? data.menus : []
  } catch (err) {
    rows.value = []
    toast.error(t('rolemenus.loadError'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(guildId, load)

function addDraft() { draftRow.value = emptyDraft() }
function cancelDraft() { draftRow.value = null }

function serialize(p) {
  const options = (p.options || []).filter(o => o.role_id).map(o => ({ role_id: o.role_id, label: o.label || '', emoji: o.emoji || '' }))
  return { name: p.name || 'Role Menu', channel_id: p.channel_id || null, menu_type: p.menu_type, exclusive: !!p.exclusive, use_embed: !!p.use_embed, embed: p.embed || defaultEmbed(), options }
}

function validate(p) {
  if (!p.channel_id) { toast.error(t('rolemenus.channelMissing')); return false }
  const opts = (p.options || []).filter(o => o.role_id)
  if (opts.length === 0) { toast.error(t('rolemenus.optionsMissing')); return false }
  return true
}

async function saveDraft(payload) {
  if (!validate(payload)) return
  draftSaving.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/rolemenus`, serialize(payload))
    if (data?.success && data.menu) rows.value.push(data.menu)
    draftRow.value = null
    toast.success(t('rolemenus.created'))
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
    const { data } = await api.put(`/guilds/${guildId.value}/rolemenus/${payload.id}`, serialize(payload))
    if (data?.success && data.menu) {
      const idx = rows.value.findIndex(r => r.id === payload.id)
      if (idx !== -1) rows.value.splice(idx, 1, data.menu)
    }
    toast.success(t('rolemenus.saved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    savingIds.delete(payload.id)
  }
}

async function confirmDelete(row) {
  if (!row?.id) return
  if (typeof window !== 'undefined' && !window.confirm(t('rolemenus.deleteConfirm'))) return
  deletingIds.add(row.id)
  try {
    await api.delete(`/guilds/${guildId.value}/rolemenus/${row.id}`)
    rows.value = rows.value.filter(r => r.id !== row.id)
    toast.success(t('rolemenus.deleted'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingIds.delete(row.id)
  }
}
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; }
.config__head-text { flex: 1; min-width: 0; }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }
.config__form { display: flex; flex-direction: column; gap: var(--space-4); max-width: 920px; }
.form-card { background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5) var(--space-6); box-shadow: var(--shadow-inset); }
.state { color: var(--color-text-muted); text-align: center; }
.empty { text-align: center; }
.empty__title { font-family: var(--font-display); font-size: 1.05rem; font-weight: 600; margin-bottom: var(--space-2); }
.empty__body { color: var(--color-text-muted); font-size: 0.92rem; }
.dirty-bar-enter-active, .dirty-bar-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.dirty-bar-enter-from, .dirty-bar-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
