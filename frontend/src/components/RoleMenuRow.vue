<template>
  <div class="form-card rm-row" :class="{ 'is-draft': isDraft }">
    <div class="rm-row__head">
      <div class="rm-row__title">
        <span v-if="dirty" class="rm-row__dot" :title="t('rolemenus.unsavedDot')" aria-hidden="true"></span>
        <span class="rm-row__badge">{{ local.menu_type === 'select' ? t('rolemenus.typeSelect') : t('rolemenus.typeButtons') }}</span>
        <span class="rm-row__name">{{ local.name || t('rolemenus.namePlaceholder') }}</span>
        <span v-if="local.message_id" class="rm-row__posted">{{ t('rolemenus.posted') }}</span>
      </div>
    </div>

    <div class="rm-row__grid">
      <div class="form-row">
        <label class="form-row__label" :for="`rm-name-${rowKey}`">{{ t('rolemenus.nameLabel') }}</label>
        <input :id="`rm-name-${rowKey}`" v-model="local.name" class="input" type="text" maxlength="100" :placeholder="t('rolemenus.namePlaceholder')" />
      </div>
      <div class="form-row">
        <label class="form-row__label">{{ t('rolemenus.typeLabel') }}</label>
        <div class="rm-row__mode">
          <button type="button" class="rm-row__mode-btn" :class="{ 'is-active': local.menu_type === 'buttons' }" @click="local.menu_type = 'buttons'">{{ t('rolemenus.typeButtons') }}</button>
          <button type="button" class="rm-row__mode-btn" :class="{ 'is-active': local.menu_type === 'select' }" @click="local.menu_type = 'select'">{{ t('rolemenus.typeSelect') }}</button>
        </div>
      </div>
    </div>

    <label v-if="local.menu_type === 'select'" class="rm-row__exclusive">
      <AppToggle v-model="local.exclusive" />
      <span>
        <span class="rm-row__exclusive-label">{{ t('rolemenus.exclusiveLabel') }}</span>
        <span class="rm-row__exclusive-hint">{{ t('rolemenus.exclusiveHint') }}</span>
      </span>
    </label>

    <div class="form-row">
      <label class="form-row__label">{{ t('rolemenus.channelLabel') }}</label>
      <ChannelSelector v-model="local.channel_id" :guild-id="guildId" :types="['text', 'announcement']" />
      <div class="form-row__hint">{{ t('rolemenus.channelHint') }}</div>
    </div>

    <div class="form-row">
      <label class="form-row__label">{{ t('rolemenus.optionsLabel') }}</label>
      <div v-for="(opt, i) in local.options" :key="i" class="rm-opt">
        <RoleSelector v-model="opt.role_id" :guild-id="guildId" :placeholder="t('rolemenus.rolePlaceholder')" />
        <input v-model="opt.label" class="input rm-opt__label" type="text" maxlength="80" :placeholder="t('rolemenus.optionLabelPlaceholder')" />
        <input v-model="opt.emoji" class="input rm-opt__emoji" type="text" maxlength="64" placeholder="😀" />
        <button type="button" class="rm-opt__del" :title="t('rolemenus.removeOption')" @click="removeOption(i)">✕</button>
      </div>
      <button v-if="local.options.length < 25" type="button" class="rm-opt__add" @click="addOption">+ {{ t('rolemenus.addOption') }}</button>
    </div>

    <div class="form-row">
      <label class="form-row__label">{{ t('rolemenus.messageLabel') }}</label>
      <div class="rm-row__mode">
        <button type="button" class="rm-row__mode-btn" :class="{ 'is-active': !local.use_embed }" @click="local.use_embed = false">{{ t('rolemenus.messageModeAuto') }}</button>
        <button type="button" class="rm-row__mode-btn" :class="{ 'is-active': local.use_embed }" @click="local.use_embed = true">{{ t('rolemenus.messageModeEmbed') }}</button>
      </div>
      <div class="form-row__hint">{{ t('rolemenus.messageModeHint') }}</div>
    </div>

    <div v-if="local.use_embed" class="form-row">
      <label class="form-row__label">{{ t('rolemenus.embedLabel') }}</label>
      <div class="form-row__hint">{{ t('rolemenus.embedHint') }}</div>
      <EmbedEditor v-model="local.embed" />
    </div>

    <div class="form-row">
      <div class="rm-preview__label">{{ t('rolemenus.livePreview') }}</div>
      <DiscordMessagePreview mode="embed" :embed="previewEmbed" :guild-name="guildName" channel-name="roles">
        <template #components>
          <div v-if="local.menu_type === 'select'" class="dc-select">
            <span>{{ local.exclusive ? t('rolemenus.previewSelectPlaceholderExclusive') : t('rolemenus.previewSelectPlaceholder') }}</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <div v-else class="dc-row">
            <span v-for="(opt, i) in previewOptions" :key="i" class="dc-btn dc-btn--secondary">
              <span v-if="opt.emoji" class="dc-btn__emoji">{{ opt.emoji }}</span>{{ opt.label || 'Role' }}
            </span>
          </div>
        </template>
      </DiscordMessagePreview>
    </div>

    <div class="rm-row__actions">
      <AppButton v-if="!isDraft" variant="danger" :loading="deleting" @click="$emit('delete', local)">{{ t('rolemenus.delete') }}</AppButton>
      <AppButton v-if="isDraft" variant="ghost" :disabled="saving" @click="$emit('cancel')">{{ t('rolemenus.cancel') }}</AppButton>
      <AppButton variant="gradient" :loading="saving" :disabled="!isDraft && !dirty" @click="$emit('save', cloneLocal())">{{ t('rolemenus.save') }}</AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import AppButton from './AppButton.vue'
import AppToggle from './AppToggle.vue'
import ChannelSelector from './ChannelSelector.vue'
import RoleSelector from './RoleSelector.vue'
import EmbedEditor from './EmbedEditor.vue'
import DiscordMessagePreview from './DiscordMessagePreview.vue'
import { useI18n } from '../i18n/index.js'
import { useGuildSettings } from '../stores/guildSettings.js'

const { t } = useI18n()
const store = useGuildSettings()
const guildName = computed(() => {
  const g = store.cache.guild
  return g?.guild_name || g?.name || 'Your Server'
})

const MENU_COLOR = '#A78BFA'

function defaultEmbed() {
  return { title: '', description: '', color: '#5865F2', thumbnail: '', image: '', footer: '', show_timestamp: false, author_name: '', author_icon_url: '' }
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
    name: src.name || '',
    channel_id: src.channel_id || '',
    menu_type: src.menu_type === 'select' ? 'select' : 'buttons',
    exclusive: !!src.exclusive,
    use_embed: !!src.use_embed,
    embed: { ...defaultEmbed(), ...(src.embed || {}) },
    message_id: src.message_id || null,
    options: Array.isArray(src.options) && src.options.length
      ? src.options.map(o => ({ role_id: o.role_id || '', label: o.label || '', emoji: o.emoji || '' }))
      : [{ role_id: '', label: '', emoji: '' }]
  }
}

const local = reactive(hydrate(props.modelValue))
let initial = JSON.stringify(local)
const rowKey = computed(() => local.id || 'draft')
const dirty = computed(() => JSON.stringify(local) !== initial)

const previewOptions = computed(() => local.options.filter(o => o.role_id || o.label))

// In auto-list mode the bot builds the embed from the menu name + role labels;
// mirror that here so the preview matches what gets posted.
const previewEmbed = computed(() => {
  if (local.use_embed) return local.embed
  const lines = local.options
    .map(o => `${o.emoji || ''} ${o.label || ''}`.trim())
    .filter(Boolean)
  return {
    ...defaultEmbed(),
    color: MENU_COLOR,
    title: local.name || 'Role Menu',
    description: lines.join('\n') || 'Pick a role below.'
  }
})

function cloneLocal() {
  return { ...local, embed: { ...local.embed }, options: local.options.map(o => ({ ...o })) }
}

watch(() => props.modelValue, (next) => {
  if (!next) return
  Object.assign(local, hydrate(next))
  initial = JSON.stringify(local)
}, { deep: true })

function addOption() { local.options.push({ role_id: '', label: '', emoji: '' }) }
function removeOption(i) { local.options.splice(i, 1); if (local.options.length === 0) addOption() }
</script>

<style scoped>
.form-card { background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5) var(--space-6); display: flex; flex-direction: column; gap: var(--space-4); box-shadow: var(--shadow-inset); }
.rm-row.is-draft { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-inset); }
.rm-row__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.rm-row__title { display: inline-flex; align-items: center; gap: var(--space-2); min-width: 0; flex-wrap: wrap; }
.rm-row__dot { width: 8px; height: 8px; border-radius: 50%; background: var(--color-warning); box-shadow: 0 0 0 3px rgba(245,158,11,0.18); }
.rm-row__badge { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; color: #fff; padding: 2px 8px; border-radius: var(--radius-sm); background: linear-gradient(135deg, #8b5cf6, #ec4899); }
.rm-row__name { font-weight: 600; color: var(--color-text); }
.rm-row__posted { font-size: 0.72rem; color: var(--color-success); background: rgba(34,197,94,0.12); padding: 2px 8px; border-radius: var(--radius-sm); }

.rm-row__grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.rm-row__mode { display: inline-flex; gap: 4px; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); padding: 3px; width: fit-content; }
.rm-row__mode-btn { padding: 0.45rem 0.9rem; border-radius: var(--radius-sm); font-size: 0.88rem; font-weight: 600; color: var(--color-text-muted); }
.rm-row__mode-btn.is-active { background: var(--gradient-brand); color: #fff; }

.rm-row__exclusive { display: flex; align-items: center; gap: var(--space-3); cursor: pointer; }
.rm-row__exclusive-label { display: block; font-weight: 600; font-size: 0.92rem; color: var(--color-text); }
.rm-row__exclusive-hint { display: block; font-size: 0.8rem; color: var(--color-text-muted); }

.form-row { display: flex; flex-direction: column; gap: var(--space-2); }
.form-row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.form-row__hint { font-size: 0.82rem; color: var(--color-text-muted); }

.input { width: 100%; padding: 0.6rem 0.8rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.92rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }

.rm-opt { display: grid; grid-template-columns: minmax(0,1.4fr) minmax(0,1fr) 70px 32px; gap: var(--space-2); align-items: center; margin-bottom: var(--space-2); }
.rm-opt__emoji { text-align: center; }
.rm-opt__del { color: var(--color-text-soft); padding: 0 6px; border-radius: 4px; }
.rm-opt__del:hover { color: var(--color-danger); background: var(--color-surface-2); }
.rm-opt__add { align-self: flex-start; font-size: 0.85rem; font-weight: 600; color: var(--color-accent); padding: 0.35rem 0.6rem; border-radius: var(--radius-sm); }
.rm-opt__add:hover { background: var(--color-surface-2); }

.rm-row__actions { display: flex; justify-content: flex-end; gap: var(--space-3); }

.rm-preview__label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }

/* Discord-style mock components rendered inside the preview bubble. */
.dc-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.dc-btn { display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 14px; border-radius: 3px; font-size: 0.86rem; font-weight: 500; color: #fff; line-height: 1; white-space: nowrap; }
.dc-btn__emoji { font-size: 0.95rem; }
.dc-btn--secondary { background: #4e5058; }
.dc-select { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px; max-width: 420px; padding: 0 12px; height: 40px; border-radius: 4px; background: #1e1f22; border: 1px solid #2b2d31; color: #949ba4; font-size: 0.88rem; }

@media (max-width: 640px) { .rm-row__grid { grid-template-columns: 1fr; } .rm-opt { grid-template-columns: 1fr; } }
</style>
