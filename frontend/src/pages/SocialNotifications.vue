<template>
  <div class="config">
    <header class="config__head">
      <div class="config__head-text">
        <div class="config__eyebrow">{{ t('socialNotifications.eyebrow') }}</div>
        <h1 class="config__title">{{ t('socialNotifications.title') }}</h1>
        <p class="config__sub">{{ t('socialNotifications.sub') }}</p>
      </div>
      <AppButton variant="gradient" :disabled="!!draftRow" @click="addDraft">
        <template #icon-left>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </template>
        {{ t('socialNotifications.addButton') }}
      </AppButton>
    </header>

    <div class="config__grid config__grid--single">
      <section class="config__form">
        <transition name="dirty-bar">
          <SocialSubscriptionRow
            v-if="draftRow"
            :model-value="draftRow"
            :saving="draftSaving"
            is-draft
            :guild-id="guildId"
            @save="saveDraft"
            @cancel="cancelDraft"
          />
        </transition>

        <div v-if="loading && subs.length === 0" class="form-card sn-state">{{ t('common.loading') }}</div>
        <div v-else-if="!loading && subs.length === 0 && !draftRow" class="form-card sn-empty">
          <div class="sn-empty__title">{{ t('socialNotifications.emptyTitle') }}</div>
          <div class="sn-empty__body">{{ t('socialNotifications.emptyBody') }}</div>
        </div>

        <SocialSubscriptionRow
          v-for="row in subs"
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
import SocialSubscriptionRow from '../components/SocialSubscriptionRow.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()

const guildId = computed(() => route.params.guild_id)

const subs = ref([])
const loading = ref(false)
const draftRow = ref(null)
const draftSaving = ref(false)
const savingIds = reactive(new Set())
const deletingIds = reactive(new Set())

function emptyDraft() {
  return {
    id: null,
    platform: 'youtube',
    account: '',
    account_id: null,
    display_name: null,
    channel_id: '',
    notify_live: true,
    notify_upload: true,
    mention_role_id: '',
    message_template: '',
    use_embed: false,
    embed: null,
    enabled: true
  }
}

function normalize(s) {
  return {
    id: s.id,
    platform: s.platform || 'youtube',
    account: s.account || '',
    account_id: s.account_id ?? null,
    display_name: s.display_name ?? null,
    channel_id: s.channel_id || '',
    notify_live: !!s.notify_live,
    notify_upload: !!s.notify_upload,
    mention_role_id: s.mention_role_id || '',
    message_template: s.message_template || '',
    use_embed: !!s.use_embed,
    embed: s.embed && typeof s.embed === 'object' ? s.embed : null,
    enabled: !!s.enabled
  }
}

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/social`)
    subs.value = (data?.success && Array.isArray(data.subscriptions))
      ? data.subscriptions.map(normalize)
      : []
  } catch (err) {
    subs.value = []
    toast.error(t('socialNotifications.loadError'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => guildId.value, load)

function addDraft() {
  draftRow.value = emptyDraft()
}

function cancelDraft() {
  draftRow.value = null
}

function validate(p) {
  if (!p.account || !String(p.account).trim()) {
    toast.error(t('socialNotifications.accountMissing'))
    return false
  }
  if (!p.channel_id) {
    toast.error(t('socialNotifications.channelMissing'))
    return false
  }
  return true
}

function serialize(p) {
  return {
    platform: p.platform,
    account: String(p.account).trim(),
    channel_id: p.channel_id,
    notify_live: !!p.notify_live,
    notify_upload: !!p.notify_upload,
    mention_role_id: p.mention_role_id || null,
    message_template: String(p.message_template || '').slice(0, 1000),
    use_embed: !!p.use_embed,
    embed: p.embed || undefined,
    enabled: !!p.enabled
  }
}

function handleSaveError(err) {
  if (err.response?.status === 409) {
    toast.error(t('socialNotifications.duplicateError'))
  } else {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  }
}

async function saveDraft(payload) {
  if (!validate(payload)) return
  draftSaving.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/social`, serialize(payload))
    if (data?.success && data.subscription) {
      subs.value.push(normalize(data.subscription))
    }
    draftRow.value = null
    toast.success(t('socialNotifications.created'))
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
    const { data } = await api.put(`/guilds/${guildId.value}/social/${payload.id}`, serialize(payload))
    if (data?.success && data.subscription) {
      const idx = subs.value.findIndex(s => s.id === payload.id)
      if (idx !== -1) subs.value.splice(idx, 1, normalize(data.subscription))
    }
    toast.success(t('socialNotifications.saved'))
  } catch (err) {
    handleSaveError(err)
  } finally {
    savingIds.delete(payload.id)
  }
}

async function confirmDelete(row) {
  if (!row?.id) return
  if (typeof window !== 'undefined' && !window.confirm(t('socialNotifications.deleteConfirm'))) return
  deletingIds.add(row.id)
  try {
    await api.delete(`/guilds/${guildId.value}/social/${row.id}`)
    subs.value = subs.value.filter(s => s.id !== row.id)
    toast.success(t('socialNotifications.deleted'))
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
  box-shadow: var(--shadow-inset);
}

.sn-state {
  color: var(--color-text-muted);
  text-align: center;
}

.sn-empty {
  text-align: center;
}

.sn-empty__title {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.sn-empty__body {
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
