<template>
  <div class="config">
    <header class="config__head">
      <div>
        <div class="config__eyebrow">{{ t('logs.eyebrow') }}</div>
        <h1 class="config__title">{{ t('logs.title') }}</h1>
        <p class="config__sub">{{ t('logs.sub') }}</p>
      </div>
    </header>

    <div class="config__grid config__grid--single">
      <section class="config__form">
        <div class="form-card">
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.toggleLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.toggleHint') }}</div>
            </div>
            <AppToggle v-model="form.enabled" />
          </div>
        </div>

        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('logs.channelLabel') }}</div>
            <div class="form-row__hint">{{ t('resourceSelector.channelPickHint') }}</div>
            <ChannelSelector
              v-model="form.log_channel_id"
              :guild-id="guildId"
              :types="['text', 'announcement']"
              :disabled="!form.enabled"
            />
          </div>
        </div>

        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-section-label">{{ t('logs.eventsSection') }}</div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.joinsLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.joinsHint') }}</div>
            </div>
            <AppToggle v-model="form.log_joins" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.leavesLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.leavesHint') }}</div>
            </div>
            <AppToggle v-model="form.log_leaves" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.editsLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.editsHint') }}</div>
            </div>
            <AppToggle v-model="form.log_message_edits" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.deletesLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.deletesHint') }}</div>
            </div>
            <AppToggle v-model="form.log_message_deletes" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.bansLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.bansHint') }}</div>
            </div>
            <AppToggle v-model="form.log_member_bans" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.unbansLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.unbansHint') }}</div>
            </div>
            <AppToggle v-model="form.log_member_unbans" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.memberUpdatesLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.memberUpdatesHint') }}</div>
            </div>
            <AppToggle v-model="form.log_member_updates" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.channelsLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.channelsHint') }}</div>
            </div>
            <AppToggle v-model="form.log_channels" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.rolesLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.rolesHint') }}</div>
            </div>
            <AppToggle v-model="form.log_roles" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('logs.voiceLabel') }}</div>
              <div class="form-row__hint">{{ t('logs.voiceHint') }}</div>
            </div>
            <AppToggle v-model="form.log_voice" :disabled="!form.enabled" />
          </div>
        </div>

        <!-- Ignored channels (message edit/delete logging only) -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('logs.ignoredChannelsLabel') }}</div>
            <div class="form-row__hint">{{ t('logs.ignoredChannelsHint') }}</div>
            <div class="ignored-row">
              <ChannelSelector
                v-model="ignoredPick"
                :guild-id="guildId"
                :types="['text', 'announcement']"
                :disabled="!form.enabled"
              />
              <AppButton
                variant="ghost"
                :disabled="!form.enabled || !ignoredPick || form.log_ignored_channel_ids.includes(ignoredPick)"
                @click="addIgnored"
              >{{ t('logs.ignoredChannelsAdd') }}</AppButton>
            </div>
            <div v-if="form.log_ignored_channel_ids.length === 0" class="form-row__hint">{{ t('logs.ignoredChannelsEmpty') }}</div>
            <ul v-else class="ignored-list">
              <li v-for="id in form.log_ignored_channel_ids" :key="id" class="ignored-chip">
                <span class="ignored-chip__name">#{{ resolveChannelName(id) }}</span>
                <span class="ignored-chip__id">{{ shortId(id) }}</span>
                <button
                  type="button"
                  class="ignored-chip__remove"
                  :disabled="!form.enabled"
                  @click="removeIgnored(id)"
                  :aria-label="t('common.reset')"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </div>

    <transition name="dirty-bar">
      <footer v-if="dirty" class="config__footer">
        <div class="config__footer-inner">
          <div class="config__footer-status">
            <span class="dot dot--warn"></span>
            {{ t('common.unsavedChanges') }}
          </div>
          <div class="config__footer-actions">
            <AppButton variant="ghost" :disabled="saving" @click="reset">{{ t('common.reset') }}</AppButton>
            <AppButton variant="gradient" :loading="saving" @click="save">{{ t('common.saveChanges') }}</AppButton>
          </div>
        </div>
      </footer>
    </transition>
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
import { useGuildResources } from '../composables/useGuildResources.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()

const guildId = computed(() => route.params.guild_id)
const resources = computed(() => useGuildResources(guildId.value))

function defaults() {
  return {
    enabled: false,
    log_channel_id: '',
    log_joins: true,
    log_leaves: true,
    log_message_edits: true,
    log_message_deletes: true,
    log_member_bans: true,
    log_member_updates: false,
    log_member_unbans: false,
    log_channels: false,
    log_roles: false,
    log_voice: false,
    log_ignored_channel_ids: []
  }
}

const form = reactive(defaults())
let initial = JSON.stringify(form)
const saving = ref(false)
const ignoredPick = ref('')

const dirty = computed(() => JSON.stringify(form) !== initial)

function shortId(id) {
  if (!id) return ''
  return id.length > 10 ? `…${id.slice(-4)}` : id
}

function resolveChannelName(id) {
  if (!id) return id
  const ch = resources.value.state.channels?.find(c => c.id === id)
  return ch?.name || id
}

function addIgnored() {
  const id = ignoredPick.value
  if (!id || form.log_ignored_channel_ids.includes(id)) return
  form.log_ignored_channel_ids = [...form.log_ignored_channel_ids, id]
  ignoredPick.value = ''
}

function removeIgnored(id) {
  form.log_ignored_channel_ids = form.log_ignored_channel_ids.filter(x => x !== id)
}

function hydrate(settings) {
  const d = defaults()
  const s = { ...d, ...(settings || {}) }
  form.enabled = !!s.enabled
  form.log_channel_id = s.log_channel_id || ''
  form.log_joins = !!s.log_joins
  form.log_leaves = !!s.log_leaves
  form.log_message_edits = !!s.log_message_edits
  form.log_message_deletes = !!s.log_message_deletes
  form.log_member_bans = !!s.log_member_bans
  form.log_member_updates = !!s.log_member_updates
  form.log_member_unbans = !!s.log_member_unbans
  form.log_channels = !!s.log_channels
  form.log_roles = !!s.log_roles
  form.log_voice = !!s.log_voice
  form.log_ignored_channel_ids = Array.isArray(s.log_ignored_channel_ids) ? s.log_ignored_channel_ids.slice() : []
  initial = JSON.stringify(form)
}

async function load() {
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/settings/logs`)
    if (data?.success) {
      hydrate(data.settings || defaults())
    } else {
      hydrate(defaults())
    }
  } catch (err) {
    hydrate(defaults())
    toast.error(t('toast.couldNotLoadSettings'))
  }
}

onMounted(load)
watch(() => guildId.value, load)

function reset() {
  hydrate(JSON.parse(initial))
  toast.info(t('toast.revertedChanges'))
}

async function save() {
  saving.value = true
  try {
    const body = {
      enabled: !!form.enabled,
      log_channel_id: form.log_channel_id || '',
      log_joins: !!form.log_joins,
      log_leaves: !!form.log_leaves,
      log_message_edits: !!form.log_message_edits,
      log_message_deletes: !!form.log_message_deletes,
      log_member_bans: !!form.log_member_bans,
      log_member_updates: !!form.log_member_updates,
      log_member_unbans: !!form.log_member_unbans,
      log_channels: !!form.log_channels,
      log_roles: !!form.log_roles,
      log_voice: !!form.log_voice,
      log_ignored_channel_ids: form.log_ignored_channel_ids.slice()
    }
    const { data } = await api.put(`/guilds/${guildId.value}/settings/logs`, body)
    if (data?.success) {
      hydrate(data.settings || body)
    } else {
      hydrate(body)
    }
    toast.success(t('logs.saved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.config__head {
  margin-bottom: var(--space-6);
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
  grid-template-columns: minmax(0, 720px);
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
  transition: opacity var(--transition);
}

.form-card.is-disabled {
  opacity: 0.65;
}

.form-section-label {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-soft);
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-row--toggle {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.form-row__label {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--color-text);
}

.form-row__hint {
  font-size: 0.82rem;
  color: var(--color-text-muted);
  line-height: 1.55;
}

.ignored-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-3);
  align-items: center;
}

.ignored-list {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.ignored-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.3rem 0.6rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
}

.ignored-chip__name { color: var(--color-text); }

.ignored-chip__id {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--color-text-soft);
}

.ignored-chip__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--color-text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.ignored-chip__remove:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.18);
  color: var(--color-danger);
}

.input {
  width: 100%;
  padding: 0.7rem 0.85rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.95rem;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.input:disabled {
  background: var(--color-surface);
  cursor: not-allowed;
  opacity: 0.7;
}

.input--mono {
  font-family: var(--font-mono);
  letter-spacing: 0.02em;
}

.config__footer {
  position: sticky;
  bottom: var(--space-4);
  margin-top: var(--space-6);
  z-index: 10;
}

.config__footer-inner {
  background: rgba(22, 26, 35, 0.85);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-xl);
  padding: var(--space-3) var(--space-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  box-shadow: var(--shadow-lg);
}

.config__footer-status {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-muted);
  font-size: 0.88rem;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot--ok {
  background: var(--color-success);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}
.dot--warn {
  background: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

.config__footer-actions {
  display: flex;
  gap: var(--space-3);
}

@media (max-width: 1100px) {
  .config__grid,
  .config__grid--single {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .config__footer-inner {
    flex-direction: column;
    align-items: stretch;
  }
  .config__footer-actions {
    justify-content: stretch;
  }
  .config__footer-actions > * {
    flex: 1;
  }
}
</style>
