<template>
  <div
    class="guild-avatar"
    :class="[`guild-avatar--${size}`, { 'has-image': !!iconUrl && !errored }]"
    :style="!iconUrl || errored ? { background: gradient } : null"
  >
    <img
      v-if="iconUrl && !errored"
      :src="iconUrl"
      :alt="name"
      @error="errored = true"
    />
    <span v-else class="guild-avatar__initials">{{ initials }}</span>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  name: { type: String, default: 'Server' },
  iconUrl: { type: String, default: '' },
  size: { type: String, default: 'md' } // sm | md | lg | xl
})

const errored = ref(false)
watch(() => props.iconUrl, () => { errored.value = false })

const initials = computed(() => {
  const n = (props.name || '?').trim()
  if (!n) return '?'
  const parts = n.split(/\s+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
})

// Deterministic gradient from name
const gradient = computed(() => {
  const palette = [
    ['#5865f2', '#a78bfa'],
    ['#a78bfa', '#22d3ee'],
    ['#22d3ee', '#5865f2'],
    ['#f472b6', '#a78bfa'],
    ['#10b981', '#22d3ee'],
    ['#f59e0b', '#f472b6'],
    ['#6366f1', '#06b6d4'],
    ['#8b5cf6', '#ec4899']
  ]
  let hash = 0
  const n = props.name || '?'
  for (let i = 0; i < n.length; i++) hash = (hash * 31 + n.charCodeAt(i)) | 0
  const [a, b] = palette[Math.abs(hash) % palette.length]
  return `linear-gradient(135deg, ${a} 0%, ${b} 100%)`
})
</script>

<style scoped>
.guild-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  overflow: hidden;
  flex-shrink: 0;
  color: #fff;
  font-weight: 700;
  font-family: var(--font-display);
  letter-spacing: -0.02em;
  box-shadow: var(--shadow-inset);
}

.guild-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.guild-avatar--sm {
  width: 36px;
  height: 36px;
  font-size: 0.85rem;
  border-radius: var(--radius-md);
}

.guild-avatar--md {
  width: 48px;
  height: 48px;
  font-size: 1rem;
  border-radius: var(--radius-md);
}

.guild-avatar--lg {
  width: 72px;
  height: 72px;
  font-size: 1.4rem;
}

.guild-avatar--xl {
  width: 96px;
  height: 96px;
  font-size: 1.9rem;
  border-radius: var(--radius-xl);
}
</style>
