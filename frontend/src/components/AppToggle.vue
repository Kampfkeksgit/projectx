<template>
  <label class="app-toggle" :class="{ 'is-on': modelValue, 'is-disabled': disabled }">
    <input
      type="checkbox"
      class="app-toggle__input"
      :checked="modelValue"
      :disabled="disabled"
      @change="$emit('update:modelValue', $event.target.checked)"
    />
    <span class="app-toggle__track">
      <span class="app-toggle__thumb"></span>
    </span>
    <span v-if="$slots.default" class="app-toggle__label"><slot /></span>
  </label>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
.app-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  cursor: pointer;
  user-select: none;
}

.app-toggle.is-disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.app-toggle__input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.app-toggle__track {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  border-radius: var(--radius-full);
  background: var(--color-surface-3);
  border: 1px solid var(--color-border-strong);
  transition: background var(--transition), border-color var(--transition);
}

.app-toggle__thumb {
  position: absolute;
  top: 50%;
  left: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #e2e6f3;
  transform: translateY(-50%);
  transition: left var(--transition) var(--ease-out-expo), background var(--transition);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
}

.app-toggle.is-on .app-toggle__track {
  background: var(--gradient-brand);
  border-color: transparent;
}
.app-toggle.is-on .app-toggle__thumb {
  left: calc(100% - 19px);
  background: #fff;
}

.app-toggle__label {
  font-size: 0.95rem;
  color: var(--color-text);
  font-weight: 500;
}
</style>
