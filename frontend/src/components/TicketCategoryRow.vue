<template>
  <div class="form-card tc-row" :class="{ 'is-draft': isDraft }">
    <div class="tc-row__head">
      <div class="tc-row__title">
        <span v-if="dirty" class="tc-row__dot" :title="t('tickets.unsavedDot')" aria-hidden="true"></span>
        <span class="tc-row__emoji">{{ local.emoji || '🎫' }}</span>
        <span class="tc-row__name">{{ local.label || t('tickets.catNamePlaceholder') }}</span>
        <span v-if="!local.enabled" class="tc-row__off">{{ t('tickets.catDisabled') }}</span>
      </div>
      <label class="tc-row__toggle">
        <AppToggle v-model="local.enabled" />
      </label>
    </div>

    <div class="tc-row__grid">
      <div class="form-row">
        <label class="form-row__label" :for="`tc-label-${rowKey}`">{{ t('tickets.catLabelLabel') }}</label>
        <input :id="`tc-label-${rowKey}`" v-model="local.label" class="input" type="text" maxlength="80" :placeholder="t('tickets.catNamePlaceholder')" />
      </div>
      <div class="form-row tc-row__emoji-field">
        <label class="form-row__label" :for="`tc-emoji-${rowKey}`">{{ t('tickets.catEmojiLabel') }}</label>
        <input :id="`tc-emoji-${rowKey}`" v-model="local.emoji" class="input" type="text" maxlength="32" placeholder="🎫" />
      </div>
    </div>

    <div class="form-row">
      <label class="form-row__label" :for="`tc-desc-${rowKey}`">{{ t('tickets.catDescLabel') }}</label>
      <input :id="`tc-desc-${rowKey}`" v-model="local.description" class="input" type="text" maxlength="100" :placeholder="t('tickets.catDescPlaceholder')" />
      <div class="form-row__hint">{{ t('tickets.catDescHint') }}</div>
    </div>

    <div class="tc-row__grid">
      <div class="form-row">
        <label class="form-row__label">{{ t('tickets.catCategoryLabel') }}</label>
        <ChannelSelector v-model="local.category_id" :guild-id="guildId" :types="['category']" :placeholder="t('tickets.catInheritPlaceholder')" />
      </div>
      <div class="form-row">
        <label class="form-row__label">{{ t('tickets.catSupportRoleLabel') }}</label>
        <RoleSelector v-model="local.support_role_id" :guild-id="guildId" :placeholder="t('tickets.catInheritPlaceholder')" />
      </div>
      <div class="form-row">
        <label class="form-row__label">{{ t('tickets.catPingRoleLabel') }}</label>
        <RoleSelector v-model="local.ping_role_id" :guild-id="guildId" :placeholder="t('tickets.catNonePlaceholder')" />
      </div>
      <div class="form-row">
        <label class="form-row__label">{{ t('tickets.catButtonStyleLabel') }}</label>
        <select v-model="local.button_style" class="input">
          <option value="primary">{{ t('tickets.stylePrimary') }}</option>
          <option value="secondary">{{ t('tickets.styleSecondary') }}</option>
          <option value="success">{{ t('tickets.styleSuccess') }}</option>
          <option value="danger">{{ t('tickets.styleDanger') }}</option>
        </select>
        <div class="form-row__hint">{{ t('tickets.catButtonStyleHint') }}</div>
      </div>
    </div>

    <div class="form-row">
      <label class="form-row__label" :for="`tc-welcome-${rowKey}`">{{ t('tickets.catWelcomeLabel') }}</label>
      <textarea :id="`tc-welcome-${rowKey}`" v-model="local.welcome_message" class="input input--textarea" rows="2" maxlength="1000" :placeholder="t('tickets.catWelcomePlaceholder')"></textarea>
      <div class="form-row__hint">{{ t('tickets.catWelcomeHint') }}</div>
    </div>

    <div class="tc-row__actions">
      <AppButton v-if="!isDraft" variant="danger" :loading="deleting" @click="$emit('delete', local)">{{ t('common.delete') }}</AppButton>
      <AppButton v-if="isDraft" variant="ghost" :disabled="saving" @click="$emit('cancel')">{{ t('common.cancel') }}</AppButton>
      <AppButton variant="gradient" :loading="saving" :disabled="!isDraft && !dirty" @click="$emit('save', cloneLocal())">{{ t('common.saveChanges') }}</AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import AppButton from './AppButton.vue'
import AppToggle from './AppToggle.vue'
import ChannelSelector from './ChannelSelector.vue'
import RoleSelector from './RoleSelector.vue'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

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
    label: src.label || '',
    emoji: src.emoji || '',
    description: src.description || '',
    category_id: src.category_id || '',
    support_role_id: src.support_role_id || '',
    ping_role_id: src.ping_role_id || '',
    welcome_message: src.welcome_message || '',
    button_style: ['primary', 'secondary', 'success', 'danger'].includes(src.button_style) ? src.button_style : 'primary',
    position: src.position ?? 0,
    enabled: src.enabled === false ? false : true
  }
}

const local = reactive(hydrate(props.modelValue))
let initial = JSON.stringify(local)
const rowKey = computed(() => local.id || 'draft')
const dirty = computed(() => JSON.stringify(local) !== initial)

function cloneLocal() { return { ...local } }

watch(() => props.modelValue, (next) => {
  if (!next) return
  Object.assign(local, hydrate(next))
  initial = JSON.stringify(local)
}, { deep: true })
</script>

<style scoped>
.form-card { background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5) var(--space-6); display: flex; flex-direction: column; gap: var(--space-4); box-shadow: var(--shadow-inset); }
.tc-row.is-draft { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-inset); }
.tc-row__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.tc-row__title { display: inline-flex; align-items: center; gap: var(--space-2); min-width: 0; flex-wrap: wrap; }
.tc-row__dot { width: 8px; height: 8px; border-radius: 50%; background: var(--color-warning); box-shadow: 0 0 0 3px rgba(245,158,11,0.18); }
.tc-row__emoji { font-size: 1.1rem; }
.tc-row__name { font-weight: 600; color: var(--color-text); }
.tc-row__off { font-size: 0.72rem; color: var(--color-text-soft); background: var(--color-bg-elevated); padding: 2px 8px; border-radius: var(--radius-sm); }

.tc-row__grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.tc-row__emoji-field { max-width: 160px; }

.form-row { display: flex; flex-direction: column; gap: var(--space-2); min-width: 0; }
.form-row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.form-row__hint { font-size: 0.82rem; color: var(--color-text-muted); }

.input { width: 100%; padding: 0.6rem 0.8rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.92rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--textarea { resize: vertical; min-height: 56px; line-height: 1.5; }
select.input { cursor: pointer; }

.tc-row__actions { display: flex; justify-content: flex-end; gap: var(--space-3); }

@media (max-width: 640px) { .tc-row__grid { grid-template-columns: 1fr; } .tc-row__emoji-field { max-width: none; } }
</style>
