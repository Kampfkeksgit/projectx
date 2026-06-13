<template>
  <div class="form-card st-row" :class="{ 'is-draft': isDraft }">
    <div class="st-row__head">
      <div class="st-row__title">
        <span v-if="!isDraft" class="st-row__reorder">
          <button
            type="button"
            class="st-row__reorder-btn"
            :disabled="index === 0"
            :title="t('stats.moveUp')"
            :aria-label="t('stats.moveUp')"
            @click="$emit('move-up', local)"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>
          </button>
          <button
            type="button"
            class="st-row__reorder-btn"
            :disabled="index >= total - 1"
            :title="t('stats.moveDown')"
            :aria-label="t('stats.moveDown')"
            @click="$emit('move-down', local)"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          </button>
        </span>
        <span v-if="!isDraft" class="st-row__index">{{ index + 1 }}</span>
        <span v-if="dirty" class="st-row__dot" :title="t('stats.unsavedDot')" aria-hidden="true"></span>
        <span class="st-row__badge">{{ typeLabel }}</span>
        <span class="st-row__preview">{{ preview }}</span>
      </div>
      <div class="st-row__head-actions">
        <span class="st-row__enabled-label">{{ t('stats.enabledLabel') }}</span>
        <AppToggle v-model="local.enabled" />
      </div>
    </div>

    <div class="st-row__grid">
      <div class="form-row">
        <label class="form-row__label" :for="`type-${rowKey}`">{{ t('stats.typeLabel') }}</label>
        <select :id="`type-${rowKey}`" v-model="local.type" class="input">
          <option v-for="opt in TYPES" :key="opt" :value="opt">{{ t('stats.type_' + opt) }}</option>
        </select>
        <div class="form-row__hint">{{ typeHint }}</div>
      </div>

      <div class="form-row">
        <label class="form-row__label" :for="`tpl-${rowKey}`">{{ t('stats.templateLabel') }}</label>
        <input
          :id="`tpl-${rowKey}`"
          ref="tplRef"
          v-model="local.name_template"
          class="input input--mono"
          type="text"
          maxlength="100"
          :placeholder="defaultTemplate"
        />
        <div class="placeholder-bar">
          <button type="button" class="placeholder-bar__chip" @click="insertCount">{{ '{count}' }}</button>
          <span class="form-row__hint">{{ t('stats.templateHint') }}</span>
        </div>
      </div>
    </div>

    <div class="form-row">
      <label class="form-row__label">{{ t('stats.channelModeLabel') }}</label>
      <div class="st-row__mode">
        <button
          type="button"
          class="st-row__mode-btn"
          :class="{ 'is-active': !local.auto_create }"
          @click="local.auto_create = false"
        >{{ t('stats.modeExisting') }}</button>
        <button
          type="button"
          class="st-row__mode-btn"
          :class="{ 'is-active': local.auto_create }"
          @click="local.auto_create = true"
        >{{ t('stats.modeAuto') }}</button>
      </div>
    </div>

    <div v-if="!local.auto_create" class="form-row">
      <label class="form-row__label">{{ t('stats.channelLabel') }}</label>
      <ChannelSelector
        v-model="local.channel_id"
        :guild-id="guildId"
        :types="['voice', 'text', 'announcement']"
      />
      <div class="form-row__hint">{{ t('stats.channelHint') }}</div>
    </div>

    <div v-else class="form-row">
      <label class="form-row__label" :for="`kind-${rowKey}`">{{ t('stats.channelKindLabel') }}</label>
      <select :id="`kind-${rowKey}`" v-model="local.channel_kind" class="input input--narrow">
        <option value="voice">{{ t('stats.kindVoice') }}</option>
        <option value="text">{{ t('stats.kindText') }}</option>
      </select>
      <div class="form-row__hint">{{ t('stats.autoHint') }}</div>
    </div>

    <div class="st-row__actions">
      <AppButton v-if="!isDraft" variant="danger" :loading="deleting" @click="$emit('delete', local)">
        {{ t('stats.delete') }}
      </AppButton>
      <AppButton v-if="isDraft" variant="ghost" :disabled="saving" @click="$emit('cancel')">
        {{ t('stats.cancel') }}
      </AppButton>
      <AppButton variant="gradient" :loading="saving" :disabled="!isDraft && !dirty" @click="$emit('save', cloneLocal())">
        {{ t('stats.save') }}
      </AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import AppButton from './AppButton.vue'
import AppToggle from './AppToggle.vue'
import ChannelSelector from './ChannelSelector.vue'
import { insertAtCaret } from './embedPlaceholders.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

const TYPES = ['members', 'humans', 'bots', 'online', 'offline', 'boosters', 'channels', 'roles']

const DEFAULT_TEMPLATES = {
  members: 'Members: {count}',
  humans: 'Humans: {count}',
  bots: 'Bots: {count}',
  online: 'Online: {count}',
  offline: 'Offline: {count}',
  boosters: 'Boosters: {count}',
  channels: 'Channels: {count}',
  roles: 'Roles: {count}'
}

const props = defineProps({
  modelValue: { type: Object, required: true },
  saving: { type: Boolean, default: false },
  deleting: { type: Boolean, default: false },
  isDraft: { type: Boolean, default: false },
  guildId: { type: String, default: '' },
  index: { type: Number, default: 0 },
  total: { type: Number, default: 1 }
})

defineEmits(['save', 'delete', 'cancel', 'move-up', 'move-down'])

function hydrate(src) {
  return {
    id: src.id ?? null,
    type: TYPES.includes(src.type) ? src.type : 'members',
    channel_id: src.channel_id || '',
    channel_kind: src.channel_kind === 'text' ? 'text' : 'voice',
    name_template: src.name_template || '',
    auto_create: !!src.auto_create,
    position: Number.isFinite(src.position) ? src.position : 0,
    enabled: src.enabled !== undefined ? !!src.enabled : true
  }
}

const local = reactive(hydrate(props.modelValue))

function cloneLocal() {
  return { ...local }
}

let initial = JSON.stringify(local)
const tplRef = ref(null)

const rowKey = computed(() => local.id || 'draft')
const dirty = computed(() => JSON.stringify(local) !== initial)
const typeLabel = computed(() => t('stats.type_' + local.type))
const defaultTemplate = computed(() => DEFAULT_TEMPLATES[local.type] || '{count}')
const typeHint = computed(() => {
  if (local.type === 'online' || local.type === 'offline') return t('stats.presenceHint')
  return t('stats.typeHint')
})

const preview = computed(() => {
  const tmpl = local.name_template || defaultTemplate.value
  const sample = '123'
  return tmpl.includes('{count}') ? tmpl.replace('{count}', sample) : `${tmpl} ${sample}`
})

watch(() => props.modelValue, (next) => {
  if (!next) return
  Object.assign(local, hydrate(next))
  initial = JSON.stringify(local)
}, { deep: true })

async function insertCount() {
  const el = tplRef.value
  const { value, caret } = insertAtCaret(el, local.name_template, '{count}')
  local.name_template = value
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

.st-row.is-draft {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-inset);
}

.st-row__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.st-row__title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex-wrap: wrap;
}

.st-row__reorder {
  display: inline-flex;
  flex-direction: column;
  gap: 1px;
}

.st-row__reorder-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 14px;
  color: var(--color-text-soft);
  border-radius: 3px;
  transition: color var(--transition), background var(--transition);
}

.st-row__reorder-btn:hover:not(:disabled) {
  color: var(--color-primary);
  background: var(--color-surface-2);
}

.st-row__reorder-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.st-row__index {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--color-text-soft);
  min-width: 1.2em;
  text-align: center;
}

.st-row__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

.st-row__badge {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
  color: #fff;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, #14b8a6, #22d3ee);
}

.st-row__preview {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 26ch;
}

.st-row__head-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
}

.st-row__enabled-label {
  font-size: 0.82rem;
  color: var(--color-text-muted);
}

.st-row__grid {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  gap: var(--space-4);
}

.st-row__mode {
  display: inline-flex;
  gap: 4px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  padding: 3px;
  width: fit-content;
}

.st-row__mode-btn {
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-sm);
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--color-text-muted);
  transition: background var(--transition), color var(--transition);
}

.st-row__mode-btn.is-active {
  background: var(--gradient-brand);
  color: #fff;
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

.input--narrow {
  max-width: 220px;
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
  align-items: center;
  gap: var(--space-2);
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

.st-row__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

@media (max-width: 720px) {
  .st-row__grid {
    grid-template-columns: 1fr;
  }
}
</style>
