<template>
  <div class="config">
    <header class="config__head">
      <div>
        <div class="config__eyebrow">{{ t('moderation.eyebrow') }}</div>
        <h1 class="config__title">{{ t('moderation.title') }}</h1>
        <p class="config__sub">{{ t('moderation.sub') }}</p>
      </div>
    </header>

    <div class="config__grid config__grid--single">
      <section class="config__form">
        <div class="form-card">
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('moderation.toggleLabel') }}</div>
              <div class="form-row__hint">{{ t('moderation.toggleHint') }}</div>
            </div>
            <AppToggle v-model="form.enabled" />
          </div>
        </div>

        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('moderation.antiSpamLabel') }}</div>
              <div class="form-row__hint">{{ t('moderation.antiSpamHint') }}</div>
            </div>
            <AppToggle v-model="form.anti_spam_enabled" :disabled="!form.enabled" />
          </div>

          <div class="form-row" :class="{ 'is-disabled': !form.enabled || !form.anti_spam_enabled }">
            <label class="form-row__label" for="mod-max-messages">{{ t('moderation.maxMessagesLabel') }}</label>
            <div class="form-row__hint">{{ t('moderation.maxMessagesHint') }}</div>
            <input
              id="mod-max-messages"
              class="input input--narrow"
              type="number"
              min="1"
              max="100"
              step="1"
              :disabled="!form.enabled || !form.anti_spam_enabled"
              v-model.number="form.max_messages_per_10s"
            />
          </div>
        </div>

        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <label class="form-row__label">{{ t('moderation.bannedWordsLabel') }}</label>
            <div class="form-row__hint">{{ t('moderation.bannedWordsHint') }}</div>
            <ChipInput
              v-model="form.banned_words"
              :placeholder="t('moderation.bannedWordsPlaceholder')"
              :transform="lowerCase"
              :disabled="!form.enabled"
              :remove-label="t('moderation.removeWord')"
            />
          </div>

          <div class="form-row">
            <label class="form-row__label" for="mod-action">{{ t('moderation.actionLabel') }}</label>
            <div class="form-row__hint">{{ t('moderation.actionHint') }}</div>
            <select
              id="mod-action"
              class="input input--select"
              :disabled="!form.enabled"
              v-model="form.banned_word_action"
            >
              <option v-for="a in FILTER_ACTIONS" :key="a" :value="a">{{ t('moderation.action_' + a) }}</option>
            </select>
          </div>
        </div>

        <!-- Content filters -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-card__heading">{{ t('moderation.filtersHeading') }}</div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('moderation.antiInviteLabel') }}</div>
              <div class="form-row__hint">{{ t('moderation.antiInviteHint') }}</div>
            </div>
            <AppToggle v-model="form.anti_invite" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('moderation.antiLinkLabel') }}</div>
              <div class="form-row__hint">{{ t('moderation.antiLinkHint') }}</div>
            </div>
            <AppToggle v-model="form.anti_link" :disabled="!form.enabled" />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('moderation.antiMentionLabel') }}</div>
              <div class="form-row__hint">{{ t('moderation.antiMentionHint') }}</div>
            </div>
            <AppToggle v-model="form.anti_mention" :disabled="!form.enabled" />
          </div>
          <div class="form-row" :class="{ 'is-disabled': !form.enabled || !form.anti_mention }">
            <label class="form-row__label" for="mod-max-mentions">{{ t('moderation.maxMentionsLabel') }}</label>
            <input
              id="mod-max-mentions"
              class="input input--narrow"
              type="number" min="1" max="50" step="1"
              :disabled="!form.enabled || !form.anti_mention"
              v-model.number="form.max_mentions"
            />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('moderation.antiCapsLabel') }}</div>
              <div class="form-row__hint">{{ t('moderation.antiCapsHint') }}</div>
            </div>
            <AppToggle v-model="form.anti_caps" :disabled="!form.enabled" />
          </div>
          <div class="form-row" :class="{ 'is-disabled': !form.enabled || !form.anti_caps }">
            <label class="form-row__label" for="mod-caps-pct">{{ t('moderation.capsPercentageLabel') }}</label>
            <input
              id="mod-caps-pct"
              class="input input--narrow"
              type="number" min="50" max="100" step="1"
              :disabled="!form.enabled || !form.anti_caps"
              v-model.number="form.caps_percentage"
            />
          </div>

          <div class="form-row">
            <label class="form-row__label" for="mod-filter-action">{{ t('moderation.filterActionLabel') }}</label>
            <div class="form-row__hint">{{ t('moderation.filterActionHint') }}</div>
            <select
              id="mod-filter-action"
              class="input input--select"
              :disabled="!form.enabled"
              v-model="form.filter_action"
            >
              <option v-for="a in FILTER_ACTIONS" :key="a" :value="a">{{ t('moderation.action_' + a) }}</option>
            </select>
          </div>
        </div>

        <!-- Action settings: mute role / timeout duration (shown when needed) -->
        <div v-if="needsMuteRole || showTimeout" class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-card__heading">{{ t('moderation.actionSettingsHeading') }}</div>
          <div v-if="needsMuteRole" class="form-row">
            <div class="form-row__label">{{ t('moderation.muteRoleLabel') }}</div>
            <div class="form-row__hint">{{ t('resourceSelector.rolePickHint') }}</div>
            <RoleSelector
              v-model="form.mute_role_id"
              :guild-id="guildId"
              :multiple="false"
              :disabled="!form.enabled"
            />
          </div>
          <div v-if="showTimeout" class="form-row">
            <label class="form-row__label" for="mod-timeout">{{ t('moderation.timeoutDurationLabel') }}</label>
            <div class="form-row__hint">{{ t('moderation.timeoutDurationHint') }}</div>
            <input
              id="mod-timeout"
              class="input input--narrow"
              type="number" min="60" max="2419200" step="60"
              :disabled="!form.enabled"
              v-model.number="form.timeout_duration"
            />
          </div>
        </div>

        <!-- Warn escalation -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-card__heading">{{ t('moderation.warnHeading') }}</div>
          <div class="form-row">
            <label class="form-row__label" for="mod-warn-threshold">{{ t('moderation.warnThresholdLabel') }}</label>
            <div class="form-row__hint">{{ t('moderation.warnThresholdHint') }}</div>
            <input
              id="mod-warn-threshold"
              class="input input--narrow"
              type="number" min="0" max="20" step="1"
              :disabled="!form.enabled"
              v-model.number="form.warn_threshold"
            />
          </div>
          <div class="form-row" :class="{ 'is-disabled': !form.enabled || form.warn_threshold < 1 }">
            <label class="form-row__label" for="mod-escalation">{{ t('moderation.escalationActionLabel') }}</label>
            <select
              id="mod-escalation"
              class="input input--select"
              :disabled="!form.enabled || form.warn_threshold < 1"
              v-model="form.warn_escalation_action"
            >
              <option v-for="a in ESCALATION_ACTIONS" :key="a" :value="a">{{ t('moderation.action_' + a) }}</option>
            </select>
          </div>
        </div>

        <!-- Whitelist -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-card__heading">{{ t('moderation.whitelistHeading') }}</div>
          <div class="form-row">
            <div class="form-row__label">{{ t('moderation.exemptRolesLabel') }}</div>
            <div class="form-row__hint">{{ t('moderation.exemptRolesHint') }}</div>
            <RoleSelector
              v-model="form.exempt_role_ids"
              :guild-id="guildId"
              :multiple="true"
              :disabled="!form.enabled"
            />
          </div>

          <div class="form-row">
            <div class="form-row__label">{{ t('moderation.ignoredChannelsLabel') }}</div>
            <div class="form-row__hint">{{ t('moderation.ignoredChannelsHint') }}</div>
            <div class="ignored-row">
              <ChannelSelector
                v-model="ignoredPick"
                :guild-id="guildId"
                :types="['text', 'announcement']"
                :disabled="!form.enabled"
              />
              <AppButton
                variant="ghost"
                :disabled="!form.enabled || !ignoredPick || form.ignored_channel_ids.includes(ignoredPick)"
                @click="addIgnored"
              >{{ t('moderation.ignoredChannelsAdd') }}</AppButton>
            </div>
            <div v-if="form.ignored_channel_ids.length === 0" class="form-row__hint">{{ t('moderation.ignoredChannelsEmpty') }}</div>
            <ul v-else class="ignored-list">
              <li v-for="id in form.ignored_channel_ids" :key="id" class="ignored-chip">
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
import ChipInput from '../components/ChipInput.vue'
import RoleSelector from '../components/RoleSelector.vue'
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

const FILTER_ACTIONS = ['delete', 'warn', 'mute', 'kick', 'timeout']
const ESCALATION_ACTIONS = ['mute', 'kick', 'ban', 'timeout']

function defaults() {
  return {
    enabled: false,
    anti_spam_enabled: false,
    max_messages_per_10s: 5,
    banned_words: [],
    banned_word_action: 'delete',
    mute_role_id: '',
    anti_invite: false,
    anti_link: false,
    filter_action: 'delete',
    anti_mention: false,
    max_mentions: 5,
    anti_caps: false,
    caps_percentage: 70,
    timeout_duration: 300,
    warn_threshold: 0,
    warn_escalation_action: 'mute',
    exempt_role_ids: [],
    ignored_channel_ids: []
  }
}

const form = reactive(defaults())
let initial = JSON.stringify(form)
const saving = ref(false)
const ignoredPick = ref('')

const dirty = computed(() => JSON.stringify(form) !== initial)

// Any action across filters/escalation that needs the mute role / a timeout.
const needsMuteRole = computed(() =>
  form.banned_word_action === 'mute' ||
  form.filter_action === 'mute' ||
  (form.warn_threshold >= 1 && form.warn_escalation_action === 'mute')
)
const showTimeout = computed(() =>
  form.banned_word_action === 'timeout' ||
  form.filter_action === 'timeout' ||
  (form.warn_threshold >= 1 && form.warn_escalation_action === 'timeout')
)

function lowerCase(v) {
  return String(v).toLowerCase()
}

function clampInt(n, fallback, lo, hi) {
  const num = Number(n)
  if (!Number.isFinite(num)) return fallback
  return Math.min(hi, Math.max(lo, Math.round(num)))
}

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
  if (!id || form.ignored_channel_ids.includes(id)) return
  form.ignored_channel_ids = [...form.ignored_channel_ids, id]
  ignoredPick.value = ''
}

function removeIgnored(id) {
  form.ignored_channel_ids = form.ignored_channel_ids.filter(x => x !== id)
}

function hydrate(settings) {
  const d = defaults()
  const s = { ...d, ...(settings || {}) }
  form.enabled = !!s.enabled
  form.anti_spam_enabled = !!s.anti_spam_enabled
  form.max_messages_per_10s = clampInt(s.max_messages_per_10s, 5, 1, 100)
  form.banned_words = Array.isArray(s.banned_words) ? s.banned_words.slice() : []
  form.banned_word_action = FILTER_ACTIONS.includes(s.banned_word_action) ? s.banned_word_action : 'delete'
  form.mute_role_id = s.mute_role_id || ''
  form.anti_invite = !!s.anti_invite
  form.anti_link = !!s.anti_link
  form.filter_action = FILTER_ACTIONS.includes(s.filter_action) ? s.filter_action : 'delete'
  form.anti_mention = !!s.anti_mention
  form.max_mentions = clampInt(s.max_mentions, 5, 1, 50)
  form.anti_caps = !!s.anti_caps
  form.caps_percentage = clampInt(s.caps_percentage, 70, 50, 100)
  form.timeout_duration = clampInt(s.timeout_duration, 300, 60, 2419200)
  form.warn_threshold = clampInt(s.warn_threshold, 0, 0, 20)
  form.warn_escalation_action = ESCALATION_ACTIONS.includes(s.warn_escalation_action) ? s.warn_escalation_action : 'mute'
  form.exempt_role_ids = Array.isArray(s.exempt_role_ids) ? s.exempt_role_ids.slice() : []
  form.ignored_channel_ids = Array.isArray(s.ignored_channel_ids) ? s.ignored_channel_ids.slice() : []
  initial = JSON.stringify(form)
}

async function load() {
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/settings/moderation`)
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
      anti_spam_enabled: !!form.anti_spam_enabled,
      max_messages_per_10s: clampInt(form.max_messages_per_10s, 5, 1, 100),
      banned_words: form.banned_words.map(w => String(w).toLowerCase()),
      banned_word_action: FILTER_ACTIONS.includes(form.banned_word_action) ? form.banned_word_action : 'delete',
      mute_role_id: form.mute_role_id || '',
      anti_invite: !!form.anti_invite,
      anti_link: !!form.anti_link,
      filter_action: FILTER_ACTIONS.includes(form.filter_action) ? form.filter_action : 'delete',
      anti_mention: !!form.anti_mention,
      max_mentions: clampInt(form.max_mentions, 5, 1, 50),
      anti_caps: !!form.anti_caps,
      caps_percentage: clampInt(form.caps_percentage, 70, 50, 100),
      timeout_duration: clampInt(form.timeout_duration, 300, 60, 2419200),
      warn_threshold: clampInt(form.warn_threshold, 0, 0, 20),
      warn_escalation_action: ESCALATION_ACTIONS.includes(form.warn_escalation_action) ? form.warn_escalation_action : 'mute',
      exempt_role_ids: form.exempt_role_ids.slice(),
      ignored_channel_ids: form.ignored_channel_ids.slice()
    }
    const { data } = await api.put(`/guilds/${guildId.value}/settings/moderation`, body)
    if (data?.success) {
      hydrate(data.settings || body)
    } else {
      hydrate(body)
    }
    toast.success(t('moderation.saved'))
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

.form-card__heading {
  font-family: var(--font-display);
  font-size: 1.02rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--color-text);
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-row.is-disabled {
  opacity: 0.6;
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

.input--narrow {
  max-width: 140px;
}

.input--select {
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%239aa3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>");
  background-repeat: no-repeat;
  background-position: right 0.85rem center;
  padding-right: 2.4rem;
  cursor: pointer;
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
