<template>
  <div class="chip-input" :class="{ 'is-disabled': disabled, 'is-focused': focused }" @click="focusInput">
    <span
      v-for="(chip, idx) in modelValue"
      :key="`${chip}-${idx}`"
      class="chip"
    >
      <span class="chip__label" :class="{ 'chip__label--mono': mono }">{{ chip }}</span>
      <button
        type="button"
        class="chip__remove"
        :disabled="disabled"
        :aria-label="removeLabel"
        @click.stop="removeAt(idx)"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </span>
    <input
      ref="inputEl"
      v-model="draft"
      class="chip-input__field"
      type="text"
      :placeholder="modelValue.length === 0 ? placeholder : ''"
      :disabled="disabled"
      @keydown="onKeydown"
      @blur="onBlur"
      @focus="focused = true"
      @paste="onPaste"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  placeholder: { type: String, default: '' },
  validator: { type: Function, default: null },
  transform: { type: Function, default: null },
  disabled: { type: Boolean, default: false },
  mono: { type: Boolean, default: false },
  removeLabel: { type: String, default: 'Remove' }
})

const emit = defineEmits(['update:modelValue'])

const draft = ref('')
const inputEl = ref(null)
const focused = ref(false)

function focusInput() {
  if (props.disabled) return
  inputEl.value?.focus()
}

function commit() {
  let raw = draft.value.trim()
  if (!raw) {
    draft.value = ''
    return
  }
  if (typeof props.transform === 'function') {
    raw = props.transform(raw)
  }
  if (!raw) {
    draft.value = ''
    return
  }
  if (typeof props.validator === 'function' && !props.validator(raw)) {
    return
  }
  if (props.modelValue.includes(raw)) {
    draft.value = ''
    return
  }
  emit('update:modelValue', [...props.modelValue, raw])
  draft.value = ''
}

function removeAt(idx) {
  if (props.disabled) return
  const next = props.modelValue.slice()
  next.splice(idx, 1)
  emit('update:modelValue', next)
}

function onKeydown(e) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    commit()
  } else if (e.key === 'Backspace' && draft.value === '' && props.modelValue.length > 0) {
    e.preventDefault()
    removeAt(props.modelValue.length - 1)
  }
}

function onBlur() {
  focused.value = false
  if (draft.value.trim()) {
    commit()
  }
}

function onPaste(e) {
  const text = (e.clipboardData || window.clipboardData)?.getData('text') || ''
  if (!text.includes(',') && !/\s/.test(text)) return
  e.preventDefault()
  const parts = text.split(/[,\s]+/).map(s => s.trim()).filter(Boolean)
  const next = props.modelValue.slice()
  for (let p of parts) {
    if (typeof props.transform === 'function') p = props.transform(p)
    if (!p) continue
    if (typeof props.validator === 'function' && !props.validator(p)) continue
    if (!next.includes(p)) next.push(p)
  }
  emit('update:modelValue', next)
  draft.value = ''
}
</script>

<style scoped>
.chip-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  min-height: 44px;
  padding: 0.45rem 0.55rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  cursor: text;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.chip-input.is-focused {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.chip-input.is-disabled {
  opacity: 0.7;
  cursor: not-allowed;
  background: var(--color-surface);
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.25rem 0.5rem 0.25rem 0.65rem;
  background: var(--color-primary-soft);
  border: 1px solid rgba(88, 101, 242, 0.35);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.85rem;
  line-height: 1.2;
  max-width: 100%;
}

.chip__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 22ch;
}

.chip__label--mono {
  font-family: var(--font-mono);
  letter-spacing: 0.02em;
  font-size: 0.82rem;
}

.chip__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  color: var(--color-text-muted);
  background: transparent;
  transition: background var(--transition-fast), color var(--transition-fast);
  flex-shrink: 0;
}

.chip__remove:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.18);
  color: var(--color-danger);
}

.chip__remove:disabled {
  cursor: not-allowed;
}

.chip-input__field {
  flex: 1;
  min-width: 120px;
  border: none;
  outline: none;
  background: transparent;
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.92rem;
  padding: 0.25rem 0.25rem;
}

.chip-input__field::placeholder {
  color: var(--color-text-soft);
}

.chip-input__field:disabled {
  cursor: not-allowed;
}
</style>
