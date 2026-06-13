<template>
  <div class="config">
    <header class="config__head">
      <div class="config__head-text">
        <div class="config__eyebrow">{{ t('customCommands.eyebrow') }}</div>
        <h1 class="config__title">{{ t('customCommands.title') }}</h1>
        <p class="config__sub">{{ t('customCommands.sub') }}</p>
      </div>
    </header>

    <div class="config__grid config__grid--single">
      <!-- ===== Server prefix ===== -->
      <section class="form-card">
        <div class="cm-title">{{ t('commandManager.prefixTitle') }}</div>
        <div class="cm-hint">{{ t('commandManager.prefixHint') }}</div>
        <div class="prefix-row">
          <input v-model="prefixDraft" class="input prefix-input" type="text" maxlength="5" spellcheck="false" />
          <AppButton variant="gradient" :loading="prefixSaving" :disabled="prefixDraft.trim() === prefix || !prefixDraft.trim()" @click="savePrefix">{{ t('common.saveChanges') }}</AppButton>
        </div>
      </section>

      <!-- ===== Built-in command catalog ===== -->
      <section class="form-card">
        <div class="cm-title">{{ t('commandManager.catalogTitle') }}</div>
        <div class="cm-hint">{{ t('commandManager.catalogHint') }}</div>

        <div v-if="catalogLoading && !catalog.length" class="cm-state">{{ t('common.loading') }}</div>

        <div v-for="group in groups" :key="group.module" class="cm-group">
          <div class="cm-group__title">{{ moduleLabel(group.module) }}</div>
          <div v-for="cmd in group.commands" :key="cmd.key" class="cm-cmd" :class="{ 'is-off': !isEnabled(cmd.key) }">
            <div class="cm-cmd__info">
              <div class="cm-cmd__head">
                <code class="cm-cmd__name">{{ formatUsage(cmd) }}</code>
                <span class="cm-cmd__badge" :class="`cm-cmd__badge--${cmd.type}`">{{ cmd.type === 'slash' ? t('commandManager.badgeSlash') : t('commandManager.badgePrefix') }}</span>
              </div>
              <div class="cm-cmd__desc">{{ cmd.description }}</div>
            </div>
            <AppToggle :model-value="isEnabled(cmd.key)" @update:model-value="v => toggle(cmd.key, v)" />
          </div>
        </div>
      </section>

      <!-- ===== User-defined custom commands ===== -->
      <div class="cm-subhead">
        <div>
          <div class="cm-title">{{ t('commandManager.customTitle') }}</div>
          <div class="cm-hint">{{ t('commandManager.customHint') }}</div>
        </div>
        <AppButton variant="gradient" :disabled="!!draftRow" @click="addDraft">
          <template #icon-left>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </template>
          {{ t('customCommands.addButton') }}
        </AppButton>
      </div>

      <section class="config__form">
        <!-- Draft (new) row -->
        <transition name="dirty-bar">
          <CommandRow
            v-if="draftRow"
            :model-value="draftRow"
            :saving="draftSaving"
            is-draft
            :guild-id="guildId"
            :placeholders="PLACEHOLDERS"
            @save="saveDraft"
            @cancel="cancelDraft"
          />
        </transition>

        <div v-if="loading && commands.length === 0" class="form-card cc-state">{{ t('common.loading') }}</div>
        <div v-else-if="!loading && commands.length === 0 && !draftRow" class="form-card cc-empty">
          <div class="cc-empty__title">{{ t('customCommands.emptyTitle') }}</div>
          <div class="cc-empty__body">{{ t('customCommands.emptyBody') }}</div>
        </div>

        <CommandRow
          v-for="row in commands"
          :key="row.id"
          :model-value="row"
          :saving="savingIds.has(row.id)"
          :deleting="deletingIds.has(row.id)"
          :guild-id="guildId"
          :placeholders="PLACEHOLDERS"
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
import AppToggle from '../components/AppToggle.vue'
import CommandRow from '../components/CustomCommandRow.vue'
import { PLACEHOLDERS } from '../components/embedPlaceholders.js'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()

const guildId = computed(() => route.params.guild_id)

// ----- Command manager (prefix + built-in catalog) -----
const prefix = ref('!')
const prefixDraft = ref('!')
const prefixSaving = ref(false)
const catalog = ref([])
const cmdSettings = reactive({})
const catalogLoading = ref(false)

const MODULE_ORDER = ['utility', 'welcome', 'tickets', 'giveaways', 'suggestions', 'verification', 'birthday']

const groups = computed(() => {
  const byModule = {}
  for (const cmd of catalog.value) {
    (byModule[cmd.module] = byModule[cmd.module] || []).push(cmd)
  }
  const mods = Object.keys(byModule).sort((a, b) => {
    const ia = MODULE_ORDER.indexOf(a); const ib = MODULE_ORDER.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
  return mods.map(m => ({ module: m, commands: byModule[m] }))
})

function moduleLabel(m) {
  const key = `commandManager.modules.${m}`
  const label = t(key)
  return label === key ? m : label
}

function isEnabled(key) {
  return cmdSettings[key] !== false
}

function formatUsage(cmd) {
  return (cmd.usage || cmd.name).replace('{p}', prefix.value)
}

async function loadCatalog() {
  if (!guildId.value) return
  catalogLoading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/custom-commands/catalog`)
    if (data?.success) {
      catalog.value = Array.isArray(data.catalog) ? data.catalog : []
      prefix.value = data.prefix || '!'
      prefixDraft.value = prefix.value
      Object.keys(cmdSettings).forEach(k => delete cmdSettings[k])
      Object.assign(cmdSettings, data.settings || {})
    }
  } catch (err) {
    // Non-fatal — the catalog is supplementary to the custom-command list.
  } finally {
    catalogLoading.value = false
  }
}

async function savePrefix() {
  const value = prefixDraft.value.trim()
  if (!value) return
  prefixSaving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/custom-commands/prefix`, { prefix: value })
    prefix.value = data?.prefix || value
    prefixDraft.value = prefix.value
    toast.success(t('commandManager.prefixSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    prefixSaving.value = false
  }
}

async function toggle(key, value) {
  const prev = cmdSettings[key]
  cmdSettings[key] = value
  try {
    await api.put(`/guilds/${guildId.value}/custom-commands/toggle/${key}`, { enabled: value })
  } catch (err) {
    cmdSettings[key] = prev
    toast.error(err.response?.data?.error || t('commandManager.toggleFailed'))
  }
}

const commands = ref([])
const loading = ref(false)
const draftRow = ref(null)
const draftSaving = ref(false)
const savingIds = reactive(new Set())
const deletingIds = reactive(new Set())

function emptyDraft() {
  return {
    id: null,
    trigger: '',
    response: '',
    match_type: 'exact',
    enabled: true
  }
}

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/custom-commands`)
    if (data?.success) {
      commands.value = (Array.isArray(data.commands) ? data.commands : []).map(normalize)
    } else {
      commands.value = []
    }
  } catch (err) {
    commands.value = []
    toast.error(t('customCommands.loadError'))
  } finally {
    loading.value = false
  }
}

function normalize(c) {
  return {
    id: c.id,
    trigger: c.trigger || '',
    response: c.response || '',
    match_type: c.match_type || 'exact',
    enabled: !!c.enabled
  }
}

function loadAll() { load(); loadCatalog() }
onMounted(loadAll)
watch(() => guildId.value, loadAll)

function addDraft() {
  draftRow.value = emptyDraft()
}

function cancelDraft() {
  draftRow.value = null
}

async function saveDraft(payload) {
  if (!validate(payload)) return
  draftSaving.value = true
  try {
    const body = serialize(payload)
    const { data } = await api.post(`/guilds/${guildId.value}/custom-commands`, body)
    if (data?.success && data.command) {
      commands.value.unshift(normalize(data.command))
    }
    draftRow.value = null
    toast.success(t('customCommands.savedCreated'))
  } catch (err) {
    if (err.response?.status === 409) {
      toast.error(t('customCommands.duplicateError'))
    } else {
      toast.error(err.response?.data?.error || t('toast.failedToSave'))
    }
  } finally {
    draftSaving.value = false
  }
}

async function saveExisting(payload) {
  if (!payload?.id) return
  if (!validate(payload)) return
  savingIds.add(payload.id)
  try {
    const body = serialize(payload)
    const { data } = await api.put(`/guilds/${guildId.value}/custom-commands/${payload.id}`, body)
    if (data?.success && data.command) {
      const idx = commands.value.findIndex(c => c.id === payload.id)
      if (idx !== -1) commands.value.splice(idx, 1, normalize(data.command))
    }
    toast.success(t('customCommands.savedUpdated'))
  } catch (err) {
    if (err.response?.status === 409) {
      toast.error(t('customCommands.duplicateError'))
    } else {
      toast.error(err.response?.data?.error || t('toast.failedToSave'))
    }
  } finally {
    savingIds.delete(payload.id)
  }
}

async function confirmDelete(row) {
  if (!row?.id) return
  if (typeof window !== 'undefined' && !window.confirm(t('customCommands.deleteConfirm'))) return
  deletingIds.add(row.id)
  try {
    await api.delete(`/guilds/${guildId.value}/custom-commands/${row.id}`)
    commands.value = commands.value.filter(c => c.id !== row.id)
    toast.success(t('customCommands.deleted'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingIds.delete(row.id)
  }
}

function validate(p) {
  if (!p.trigger || !String(p.trigger).trim()) {
    toast.error(t('customCommands.triggerMissing'))
    return false
  }
  if (!p.response || !String(p.response).trim()) {
    toast.error(t('customCommands.responseMissing'))
    return false
  }
  return true
}

function serialize(p) {
  return {
    trigger: String(p.trigger).trim().toLowerCase().slice(0, 50),
    response: String(p.response).slice(0, 2000),
    match_type: ['exact', 'contains', 'starts_with'].includes(p.match_type) ? p.match_type : 'exact',
    enabled: !!p.enabled
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
  grid-template-columns: 1.15fr 1fr;
  gap: var(--space-5);
  align-items: flex-start;
}

.config__grid--single {
  grid-template-columns: minmax(0, 920px);
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
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  box-shadow: var(--shadow-inset);
}

.cc-state {
  color: var(--color-text-muted);
  text-align: center;
}

/* ----- Command manager ----- */
.cm-title { font-family: var(--font-display); font-size: 1.05rem; font-weight: 600; letter-spacing: -0.01em; }
.cm-hint { font-size: 0.85rem; color: var(--color-text-muted); line-height: 1.5; }
.cm-state { color: var(--color-text-muted); font-size: 0.9rem; }
.prefix-row { display: flex; align-items: center; gap: var(--space-3); }
.input { padding: 0.7rem 0.85rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-mono); font-size: 0.95rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.prefix-input { width: 110px; text-align: center; font-size: 1.1rem; }

.cm-group { display: flex; flex-direction: column; gap: var(--space-2); margin-top: var(--space-2); }
.cm-group__title { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; color: var(--color-text-soft); margin-top: var(--space-3); }
.cm-cmd { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); padding: 0.7rem 0.85rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-elevated); }
.cm-cmd.is-off { opacity: 0.55; }
.cm-cmd__info { min-width: 0; }
.cm-cmd__head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.cm-cmd__name { font-family: var(--font-mono); font-size: 0.9rem; color: var(--color-text); }
.cm-cmd__badge { font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; padding: 2px 7px; border-radius: var(--radius-sm); color: #fff; }
.cm-cmd__badge--slash { background: #5865f2; }
.cm-cmd__badge--prefix { background: #4e5058; }
.cm-cmd__desc { font-size: 0.82rem; color: var(--color-text-muted); margin-top: 3px; }

.cm-subhead { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; margin-top: var(--space-4); margin-bottom: var(--space-2); }

.cc-empty {
  text-align: center;
}

.cc-empty__title {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.cc-empty__body {
  color: var(--color-text-muted);
  font-size: 0.92rem;
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
