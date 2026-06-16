<template>
  <div v-if="state.enabled" class="maint" role="status">
    <svg class="maint__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
    <span class="maint__text">{{ state.message || t('maintenance.bannerDefault') }}</span>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive } from 'vue'
import api from '../services/api.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const state = reactive({ enabled: false, message: '' })
let timer = null

async function poll() {
  try {
    const { data } = await api.get('/public/maintenance')
    state.enabled = !!data?.enabled
    state.message = typeof data?.message === 'string' ? data.message : ''
  } catch {
    // Never let a maintenance-poll failure surface to the user.
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
.maint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0.55rem var(--space-4);
  background: var(--color-warning, #f59e0b);
  color: #1a1205;
  font-size: 0.85rem;
  font-weight: 600;
  text-align: center;
  line-height: 1.35;
}

.maint__icon {
  flex-shrink: 0;
}

.maint__text {
  min-width: 0;
}
</style>
