<template>
  <div v-if="state.enabled && state.message" class="ann" :class="`ann--${state.level}`" role="status">
    <svg class="ann__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/></svg>
    <span class="ann__text">{{ state.message }}</span>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive } from 'vue'
import api from '../services/api.js'

const state = reactive({ enabled: false, message: '', level: 'info' })
let timer = null

async function poll() {
  try {
    const { data } = await api.get('/public/announcement')
    state.enabled = !!data?.enabled
    state.message = typeof data?.message === 'string' ? data.message : ''
    state.level = data?.level === 'warning' ? 'warning' : 'info'
  } catch {
    // Never surface a poll failure to the user.
  }
}

onMounted(() => {
  poll()
  timer = setInterval(poll, 60000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.ann {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0.55rem var(--space-4);
  font-size: 0.85rem;
  font-weight: 600;
  text-align: center;
  line-height: 1.35;
}
.ann--info { background: var(--color-primary, #5865f2); color: #fff; }
.ann--warning { background: var(--color-warning, #f59e0b); color: #1a1205; }
.ann__icon { flex-shrink: 0; }
.ann__text { min-width: 0; }
</style>
