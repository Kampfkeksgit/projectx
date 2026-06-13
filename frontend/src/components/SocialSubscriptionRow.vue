<template>
  <div class="form-card sn-row" :class="{ 'is-draft': isDraft }">
    <div class="sn-row__head">
      <div class="sn-row__title">
        <span v-if="dirty" class="sn-row__dot" :title="t('socialNotifications.unsavedDot')" aria-hidden="true"></span>
        <span class="sn-row__badge" :class="`sn-row__badge--${local.platform}`">{{ platformLabel }}</span>
        <span class="sn-row__account">
          {{ local.account || (isDraft ? t('socialNotifications.accountPlaceholder') : '—') }}
        </span>
        <span v-if="local.display_name && local.display_name !== local.account" class="sn-row__resolved">
          {{ t('socialNotifications.resolvedAs', { name: local.display_name }) }}
        </span>
      </div>
      <div class="sn-row__head-actions">
        <span class="sn-row__enabled-label">{{ t('socialNotifications.enabledLabel') }}</span>
        <AppToggle v-model="local.enabled" />
      </div>
    </div>

    <div class="sn-row__grid">
      <div class="form-row">
        <label class="form-row__label" :for="`platform-${rowKey}`">{{ t('socialNotifications.platformLabel') }}</label>
        <select :id="`platform-${rowKey}`" v-model="local.platform" class="input">
          <option value="youtube">{{ t('socialNotifications.platformYoutube') }}</option>
          <option value="twitch">{{ t('socialNotifications.platformTwitch') }}</option>
          <option value="kick">{{ t('socialNotifications.platformKick') }}</option>
          <option value="tiktok" disabled>{{ t('socialNotifications.platformTiktok') }} — {{ t('socialNotifications.comingSoon') }}</option>
          <option value="instagram" disabled>{{ t('socialNotifications.platformInstagram') }} — {{ t('socialNotifications.comingSoon') }}</option>
        </select>
      </div>

      <div class="form-row">
        <label class="form-row__label" :for="`account-${rowKey}`">{{ t('socialNotifications.accountLabel') }}</label>
        <input
          :id="`account-${rowKey}`"
          v-model="local.account"
          class="input input--mono"
          type="text"
          maxlength="100"
          :placeholder="t('socialNotifications.accountPlaceholder')"
        />
        <div class="form-row__hint">{{ accountHint }}</div>
      </div>
    </div>

    <div class="form-row">
      <label class="form-row__label">{{ t('socialNotifications.channelLabel') }}</label>
      <ChannelSelector
        v-model="local.channel_id"
        :guild-id="guildId"
        :types="['text', 'announcement']"
      />
      <div class="form-row__hint">{{ t('socialNotifications.channelHint') }}</div>
    </div>

    <div class="sn-row__toggles">
      <label class="sn-row__toggle">
        <AppToggle v-model="local.notify_live" />
        <span>{{ t('socialNotifications.notifyLive') }}</span>
      </label>
      <label class="sn-row__toggle">
        <AppToggle v-model="local.notify_upload" />
        <span>{{ t('socialNotifications.notifyUpload') }}</span>
      </label>
    </div>

    <div class="form-row">
      <label class="form-row__label">{{ t('socialNotifications.mentionRoleLabel') }}</label>
      <RoleSelector
        v-model="local.mention_role_id"
        :guild-id="guildId"
        :placeholder="t('socialNotifications.mentionRolePlaceholder')"
      />
      <div class="form-row__hint">{{ t('socialNotifications.mentionRoleHint') }}</div>
    </div>

    <div class="form-row">
      <label class="form-row__label" :for="`tpl-${rowKey}`">{{ t('socialNotifications.messageLabel') }}</label>
      <textarea
        :id="`tpl-${rowKey}`"
        ref="tplRef"
        v-model="local.message_template"
        class="input input--textarea"
        rows="3"
        maxlength="1000"
        :placeholder="t('socialNotifications.messagePlaceholder')"
      ></textarea>
      <div class="form-row__hint">{{ t('socialNotifications.messageHint') }}</div>
      <div class="placeholder-bar">
        <button
          v-for="token in SOCIAL_PLACEHOLDERS"
          :key="token"
          type="button"
          class="placeholder-bar__chip"
          @click="insertPlaceholder(token)"
        >{{ token }}</button>
      </div>
    </div>

    <div class="form-row">
      <label class="sn-row__toggle">
        <AppToggle v-model="local.use_embed" />
        <span>{{ t('socialNotifications.useEmbed') }}</span>
      </label>
      <transition name="dirty-bar">
        <EmbedEditor v-if="local.use_embed" v-model="local.embed" />
      </transition>
    </div>

    <div class="sn-row__actions">
      <AppButton v-if="!isDraft" variant="danger" :loading="deleting" @click="$emit('delete', local)">
        {{ t('socialNotifications.delete') }}
      </AppButton>
      <AppButton v-if="isDraft" variant="ghost" :disabled="saving" @click="$emit('cancel')">
        {{ t('socialNotifications.cancel') }}
      </AppButton>
      <AppButton variant="gradient" :loading="saving" :disabled="!isDraft && !dirty" @click="$emit('save', cloneLocal())">
        {{ t('socialNotifications.save') }}
      </AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import AppButton from './AppButton.vue'
import AppToggle from './AppToggle.vue'
import ChannelSelector from './ChannelSelector.vue'
import RoleSelector from './RoleSelector.vue'
import EmbedEditor from './EmbedEditor.vue'
import { insertAtCaret } from './embedPlaceholders.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

// Social-specific placeholders — distinct from the welcome/leave member set.
const SOCIAL_PLACEHOLDERS = ['{creator}', '{platform}', '{url}', '{title}', '{type}']

const PLATFORM_LABELS = {
  youtube: 'YouTube',
  twitch: 'Twitch',
  kick: 'Kick',
  tiktok: 'TikTok',
  instagram: 'Instagram'
}

function defaultEmbed() {
  return {
    title: '',
    description: '',
    color: '#5865F2',
    thumbnail: '',
    image: '',
    footer: '',
    show_timestamp: false,
    author_name: '',
    author_icon_url: ''
  }
}

const props = defineProps({
  modelValue: { type: Object, required: true },
  saving: { type: Boolean, default: false },
  deleting: { type: Boolean, default: false },
  isDraft: { type: Boolean, default: false },
  guildId: { type: String, default: '' }
})

defineEmits(['save', 'delete', 'cancel'])

function hydrate(src) {
  return {
    id: src.id ?? null,
    platform: src.platform || 'youtube',
    account: src.account || '',
    account_id: src.account_id ?? null,
    display_name: src.display_name ?? null,
    channel_id: src.channel_id || '',
    notify_live: src.notify_live !== undefined ? !!src.notify_live : true,
    notify_upload: src.notify_upload !== undefined ? !!src.notify_upload : true,
    mention_role_id: src.mention_role_id || '',
    message_template: src.message_template || '',
    use_embed: !!src.use_embed,
    embed: { ...defaultEmbed(), ...(src.embed && typeof src.embed === 'object' ? src.embed : {}) },
    enabled: src.enabled !== undefined ? !!src.enabled : true
  }
}

const local = reactive(hydrate(props.modelValue))

function cloneLocal() {
  return { ...local, embed: { ...local.embed } }
}

let initial = JSON.stringify(local)
const tplRef = ref(null)

const rowKey = computed(() => local.id || 'draft')
const dirty = computed(() => JSON.stringify(local) !== initial)
const platformLabel = computed(() => PLATFORM_LABELS[local.platform] || local.platform)

const accountHint = computed(() => {
  if (local.platform === 'youtube') return t('socialNotifications.accountHintYoutube')
  if (local.platform === 'twitch') return t('socialNotifications.accountHintTwitch')
  if (local.platform === 'kick') return t('socialNotifications.accountHintKick')
  return t('socialNotifications.accountHintGeneric')
})

// Re-baseline when the parent swaps the row in (e.g. after a save).
watch(() => props.modelValue, (next) => {
  if (!next) return
  Object.assign(local, hydrate(next))
  initial = JSON.stringify(local)
}, { deep: true })

async function insertPlaceholder(token) {
  const el = tplRef.value
  const { value, caret } = insertAtCaret(el, local.message_template, token)
  local.message_template = value
  await nextTick()
  if (el) {
    el.focus()
    try { el.setSelectionRange(caret, caret) } catch { /* ignore */ }
  }
}
</script>

<style scoped>
.form-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  box-shadow: var(--shadow-inset);
}

.sn-row.is-draft {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-inset);
}

.sn-row__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.sn-row__title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex-wrap: wrap;
}

.sn-row__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

.sn-row__badge {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
  color: #fff;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--color-text-soft);
}
.sn-row__badge--youtube { background: linear-gradient(135deg, #ef4444, #f87171); }
.sn-row__badge--twitch { background: linear-gradient(135deg, #9146ff, #a78bfa); }
.sn-row__badge--kick { background: linear-gradient(135deg, #53fc18, #10b981); color: #06210a; }
.sn-row__badge--tiktok { background: linear-gradient(135deg, #ec4899, #22d3ee); }
.sn-row__badge--instagram { background: linear-gradient(135deg, #f472b6, #f59e0b); }

.sn-row__account {
  font-family: var(--font-mono);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 22ch;
}

.sn-row__resolved {
  font-size: 0.74rem;
  color: var(--color-text-soft);
}

.sn-row__head-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
}

.sn-row__enabled-label {
  font-size: 0.82rem;
  color: var(--color-text-muted);
}

.sn-row__grid {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  gap: var(--space-4);
}

.sn-row__toggles {
  display: flex;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.sn-row__toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  font-size: 0.92rem;
  color: var(--color-text);
  cursor: pointer;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
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

.input--mono {
  font-family: var(--font-mono);
  letter-spacing: 0.02em;
}

.input--textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.55;
}

select.input {
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6' fill='none' stroke='%2399a' stroke-width='2'%3E%3Cpolyline points='1 1 5 5 9 1'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.9rem center;
  padding-right: 2rem;
}

.placeholder-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.placeholder-bar__chip {
  padding: 0.3rem 0.55rem;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--color-accent);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
}

.placeholder-bar__chip:hover {
  border-color: var(--color-primary);
  background: var(--color-surface-3);
}

.sn-row__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
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

@media (max-width: 720px) {
  .sn-row__grid {
    grid-template-columns: 1fr;
  }
}
</style>
