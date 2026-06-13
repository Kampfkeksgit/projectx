<template>
  <div :class="['app-card', { 'app-card--interactive': interactive, 'app-card--glass': glass }]">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  interactive: { type: Boolean, default: false },
  glass: { type: Boolean, default: false }
})
</script>

<style scoped>
.app-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-md), var(--shadow-inset);
  transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
}

.app-card--glass {
  background: rgba(22, 26, 35, 0.55);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border-color: rgba(255, 255, 255, 0.06);
}

.app-card--interactive {
  cursor: pointer;
}

.app-card--interactive:hover {
  transform: translateY(-4px);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-lg), var(--shadow-inset);
}
</style>
