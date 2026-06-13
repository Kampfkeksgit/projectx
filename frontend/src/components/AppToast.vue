<template>
  <Teleport to="body">
    <div class="toast-stack" aria-live="polite">
      <transition-group name="toast">
        <div
          v-for="t in toast.state.toasts"
          :key="t.id"
          :class="['toast', `toast--${t.type}`]"
          role="status"
          @click="toast.dismiss(t.id)"
        >
          <span class="toast__icon" aria-hidden="true">
            <svg v-if="t.type === 'success'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            <svg v-else-if="t.type === 'error'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>
            <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          </span>
          <span class="toast__message">{{ t.message }}</span>
        </div>
      </transition-group>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '../composables/useToast.js'

const toast = useToast()
</script>

<style scoped>
.toast-stack {
  position: fixed;
  bottom: var(--space-6);
  right: var(--space-6);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  pointer-events: none;
}

.toast {
  pointer-events: auto;
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 240px;
  max-width: 380px;
  padding: 0.85rem 1rem;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  color: var(--color-text);
  font-size: 0.9rem;
  cursor: pointer;
}

.toast__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.toast--success .toast__icon {
  background: var(--color-success-soft);
  color: var(--color-success);
}
.toast--error .toast__icon {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
.toast--info .toast__icon {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.toast__message {
  flex: 1;
  line-height: 1.4;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(20px) translateY(8px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--transition), transform var(--transition) var(--ease-out-expo);
}

@media (max-width: 640px) {
  .toast-stack {
    left: var(--space-4);
    right: var(--space-4);
    bottom: var(--space-4);
  }
  .toast {
    width: 100%;
    max-width: none;
  }
}
</style>
