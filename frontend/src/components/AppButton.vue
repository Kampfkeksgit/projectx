<template>
  <component
    :is="tag"
    :class="['app-button', `app-button--${variant}`, { 'is-loading': loading, 'is-block': block }]"
    :disabled="disabled || loading"
    :type="tag === 'button' ? type : undefined"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="spinner" aria-hidden="true"></span>
    <span class="app-button__content">
      <slot name="icon-left" />
      <slot />
      <slot name="icon-right" />
    </span>
  </component>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'primary' }, // primary | ghost | danger | subtle | gradient
  type: { type: String, default: 'button' },
  tag: { type: String, default: 'button' },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  block: { type: Boolean, default: false }
})

defineEmits(['click'])
</script>

<style scoped>
.app-button {
  --btn-bg: var(--color-primary);
  --btn-bg-hover: var(--color-primary-hover);
  --btn-color: #fff;
  --btn-border: transparent;

  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0.7rem 1.2rem;
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-weight: 600;
  font-size: 0.92rem;
  letter-spacing: -0.005em;
  line-height: 1;
  cursor: pointer;
  background: var(--btn-bg);
  color: var(--btn-color);
  border: 1px solid var(--btn-border);
  transition: transform var(--transition-fast), background var(--transition),
              box-shadow var(--transition), color var(--transition), opacity var(--transition);
  user-select: none;
  white-space: nowrap;
  text-decoration: none;
}

.app-button:hover:not(:disabled) {
  background: var(--btn-bg-hover);
  transform: translateY(-1px);
}

.app-button:active:not(:disabled) {
  transform: translateY(0);
}

.app-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.app-button.is-block {
  width: 100%;
}

.app-button__content {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

/* Variants */
.app-button--primary {
  --btn-bg: var(--color-primary);
  --btn-bg-hover: var(--color-primary-hover);
  box-shadow: 0 6px 18px -8px rgba(88, 101, 242, 0.7), var(--shadow-inset);
}

.app-button--gradient {
  --btn-bg: var(--gradient-brand);
  --btn-bg-hover: var(--gradient-brand);
  background: var(--gradient-brand);
  box-shadow: 0 10px 30px -10px rgba(88, 101, 242, 0.55), var(--shadow-inset);
}
.app-button--gradient:hover:not(:disabled) {
  filter: brightness(1.07);
}

.app-button--ghost {
  --btn-bg: transparent;
  --btn-bg-hover: var(--color-surface-2);
  --btn-color: var(--color-text);
  --btn-border: var(--color-border-strong);
}

.app-button--subtle {
  --btn-bg: var(--color-surface-2);
  --btn-bg-hover: var(--color-surface-3);
  --btn-color: var(--color-text);
}

.app-button--danger {
  --btn-bg: var(--color-danger);
  --btn-bg-hover: #dc2626;
  --btn-color: #fff;
}

.is-loading .app-button__content {
  opacity: 0;
}

.spinner {
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
</style>
