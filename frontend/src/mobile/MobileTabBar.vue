<template>
  <nav class="m-tabs" :aria-label="t('mobile.nav')">
    <template v-for="tab in tabs" :key="tab.key">
      <button
        v-if="tab.action"
        class="m-tab"
        :class="{ 'is-active': tab.active }"
        @click="$emit(tab.action)"
      >
        <span class="m-tab__icon" v-html="tab.icon"></span>
        <span class="m-tab__label">{{ tab.label }}</span>
      </button>
      <router-link
        v-else
        class="m-tab"
        :class="{ 'is-active': tab.active }"
        :to="tab.to"
      >
        <span class="m-tab__icon" v-html="tab.icon"></span>
        <span class="m-tab__label">{{ tab.label }}</span>
      </router-link>
    </template>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const route = useRoute()

defineEmits(['open-account'])

const ICONS = {
  home: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h14V10"/></svg>',
  servers: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><line x1="7" y1="7" x2="7" y2="7"/><line x1="7" y1="17" x2="7" y2="17"/></svg>',
  modules: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></svg>',
  premium: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15 8.5 22 9.3 17 14 18.2 21 12 17.5 5.8 21 7 14 2 9.3 9 8.5 12 2"/></svg>',
  account: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg>'
}

const guildId = computed(() => route.params.guild_id || null)

const tabs = computed(() => {
  const id = guildId.value
  const list = []
  if (id) {
    const base = `/dashboard/${id}`
    list.push({ key: 'servers', to: '/dashboard', icon: ICONS.servers, label: t('mobile.tabServers'), active: route.name === 'servers' })
    list.push({ key: 'modules', to: base, icon: ICONS.modules, label: t('mobile.tabModules'), active: route.name === 'overview' })
    list.push({ key: 'premium', to: `${base}/premium`, icon: ICONS.premium, label: t('sidebar.linkPremium'), active: route.name === 'premium' })
  } else {
    list.push({ key: 'home', to: '/', icon: ICONS.home, label: t('common.home'), active: route.name === 'landing' })
    list.push({ key: 'servers', to: '/dashboard', icon: ICONS.servers, label: t('mobile.tabServers'), active: route.name === 'servers' })
  }
  list.push({ key: 'account', action: 'open-account', icon: ICONS.account, label: t('mobile.tabAccount'), active: false })
  return list
})
</script>

<style scoped>
.m-tabs {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 60;
  height: calc(var(--mobile-tabbar-h, 64px) + env(safe-area-inset-bottom, 0px));
  padding-bottom: env(safe-area-inset-bottom, 0px);
  display: flex;
  align-items: stretch;
  background: rgba(13, 16, 23, 0.92);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  border-top: 1px solid var(--color-border);
}

.m-tab {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  color: var(--color-text-soft);
  font-size: 0.66rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition: color var(--transition-fast);
}
.m-tab:active {
  color: var(--color-text);
}
.m-tab.is-active {
  color: var(--color-primary-hover);
}

.m-tab__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.m-tab__label {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
