<template>
  <div class="form-card cc-row" :class="{ 'is-draft': isDraft }">
    <div class="cc-row__head">
      <div class="cc-row__title">
        <span v-if="dirty" class="cc-row__dot" :title="t('customCommands.unsavedDot')" aria-hidden="true"></span>
        <span class="cc-row__trigger-preview">
          {{ local.trigger || (isDraft ? t('customCommands.triggerPlaceholder') : '—') }}
        </span>
        <span class="cc-row__match">{{ matchLabel }}</span>
      </div>
      <div class="cc-row__head-actions">
        <span class="cc-row__enabled-label">{{ t('customCommands.enabledLabel') }}</span>
        <AppToggle v-model="local.enabled" />
      </div>
    </div>

    <div class="cc-row__grid">
      <div class="form-row cc-row__trigger-col">
        <label class="form-row__label" :for="`trigger-${rowKey}`">{{ t('customCommands.triggerLabel') }}</label>
        <input
          :id="`trigger-${rowKey}`"
          v-model="local.trigger"
          class="input input--mono"
          type="text"
          maxlength="50"
          :placeholder="t('customCommands.triggerPlaceholder')"
          @blur="onTriggerBlur"
        />
        <div class="form-row__hint">{{ t('customCommands.triggerHint') }}</div>
      </div>

      <div class="form-row cc-row__match-col">
        <label class="form-row__label" :for="`match-${rowKey}`">{{ t('customCommands.matchTypeLabel') }}</label>
        <select
          :id="`match-${rowKey}`"
          v-model="local.match_type"
          class="input"
        >
          <option value="exact">{{ t('customCommands.matchExact') }}</option>
          <option value="contains">{{ t('customCommands.matchContains') }}</option>
          <option value="starts_with">{{ t('customCommands.matchStartsWith') }}</option>
        </select>
      </div>
    </div>

    <div class="form-row">
      <label class="form-row__label" :for="`response-${rowKey}`">{{ t('customCommands.responseLabel') }}</label>
      <textarea
        :id="`response-${rowKey}`"
        ref="responseRef"
        v-model="local.response"
        class="input input--textarea"
        rows="3"
        maxlength="2000"
        :placeholder="t('customCommands.responsePlaceholder')"
      ></textarea>
      <div class="form-row__hint">{{ t('customCommands.responseHint') }}</div>
      <div class="placeholder-bar">
        <button
          v-for="ph in placeholders"
          :key="ph.token"
          type="button"
          class="placeholder-bar__chip"
          @click="insertPlaceholder(ph.token)"
        >{{ ph.token }}</button>
      </div>
    </div>

    <div class="cc-row__actions">
      <AppButton v-if="!isDraft" variant="danger" :loading="deleting" @click="$emit('delete', local)">
        {{ t('customCommands.delete') }}
      </AppButton>
      <AppButton v-if="isDraft" variant="ghost" :disabled="saving" @click="$emit('cancel')">
        {{ t('reactionRoles.cancel') }}
      </AppButton>
      <AppButton variant="gradient" :loading="saving" :disabled="!isDraft && !dirty" @click="$emit('save', { ...local })">
        {{ t('customCommands.save') }}
      </AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import AppButton from './AppButton.vue'
import AppToggle from './AppToggle.vue'
import { insertAtCaret } from './embedPlaceholders.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: Object, required: true },
  saving: { type: Boolean, default: false },
  deleting: { type: Boolean, default: false },
  isDraft: { type: Boolean, default: false },
  guildId: { type: String, default: '' },
  placeholders: { type: Array, default: () => [] }
})

const emit = defineEmits(['save', 'delete', 'cancel'])

const local = reactive({
  id: props.modelValue.id,
  trigger: props.modelValue.trigger || '',
  response: props.modelValue.response || '',
  match_type: props.modelValue.match_type || 'exact',
  enabled: !!props.modelValue.enabled
})

let initial = JSON.stringify(local)
const responseRef = ref(null)

const rowKey = computed(() => local.id || 'draft')

const dirty = computed(() => JSON.stringify(local) !== initial)

const matchLabel = computed(() => {
  if (local.match_type === 'contains') return t('customCommands.matchContains')
  if (local.match_type === 'starts_with') return t('customCommands.matchStartsWith')
  return t('customCommands.matchExact')
})

// When the parent replaces the row (e.g. after save), re-baseline.
watch(() => props.modelValue, (next) => {
  if (!next) return
  local.id = next.id
  local.trigger = next.trigger || ''
  local.response = next.response || ''
  local.match_type = next.match_type || 'exact'
  local.enabled = !!next.enabled
  initial = JSON.stringify(local)
}, { deep: true })

function onTriggerBlur() {
  local.trigger = String(local.trigger || '').trim().toLowerCase()
}

async function insertPlaceholder(token) {
  const el = responseRef.value
  const { value, caret } = insertAtCaret(el, local.response, token)
  local.response = value
  await nextTick()
  if (el) {
    el.focus()
    try { el.setSelectionRange(caret, caret) } catch {
      // ignore unsupported
    }
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

.cc-row.is-draft {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-inset);
}

.cc-row__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.cc-row__title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.cc-row__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

.cc-row__trigger-preview {
  font-family: var(--font-mono);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 24ch;
}

.cc-row__match {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-soft);
  background: var(--color-surface-2);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-weight: 600;
}

.cc-row__head-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
}

.cc-row__enabled-label {
  font-size: 0.82rem;
  color: var(--color-text-muted);
}

.cc-row__grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: var(--space-4);
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
  min-height: 90px;
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

.cc-row__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

@media (max-width: 720px) {
  .cc-row__grid {
    grid-template-columns: 1fr;
  }
}
</style>
