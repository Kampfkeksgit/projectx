<template>
  <div class="dashboard-layout">
    <div class="dashboard-layout__inner">
      <button class="mobile-trigger" @click="mobileOpen = !mobileOpen">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        Menu
      </button>

      <Sidebar
        v-show="!isMobile || mobileOpen"
        :guild-id="guildId"
        :guild-name="guildName"
        :guild-icon-url="guildIconUrl"
        :is-mobile-open="mobileOpen"
        @navigate="mobileOpen = false"
      />

      <main class="dashboard-layout__main">
        <div v-if="loading" class="loading-block">
          <LoadingPage :message="t('common.loading')" />
        </div>
        <div v-else-if="loadError" class="error-block">
          <div class="error-block__card">
            <h3>Could not load this server</h3>
            <p>{{ loadError }}</p>
            <AppButton variant="gradient" @click="reload">{{ t('common.retry') }}</AppButton>
          </div>
        </div>
        <PremiumLock v-else-if="lockedModule" :module="lockedModule" :guild-id="guildId" />
        <router-view v-else v-slot="{ Component, route: r }">
          <transition name="module-swap" mode="out-in">
            <component :is="Component" :key="r.path" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from '../components/Sidebar.vue'
import LoadingPage from '../components/LoadingPage.vue'
import AppButton from '../components/AppButton.vue'
import PremiumLock from '../components/PremiumLock.vue'
import { useGuildSettings } from '../stores/guildSettings.js'
import { usePremium } from '../stores/premium.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

const route = useRoute()
const settings = useGuildSettings()
const premium = usePremium()
const mobileOpen = ref(false)
const isMobile = ref(false)
const loadError = ref(null)

const guildId = computed(() => route.params.guild_id)
const loading = computed(() => settings.cache.loading && !settings.cache.settings)

// The current module's route segment (e.g. 'social', 'reaction-roles'). Empty on
// the overview. When the guild's tier doesn't unlock it, we render the lock in
// place of the page — one gate covers every premium module page. 'premium' is
// the upsell page itself, never locked.
const moduleKey = computed(() => {
  const base = `/dashboard/${guildId.value}`
  const rest = route.path.startsWith(base) ? route.path.slice(base.length).replace(/^\//, '') : ''
  return rest.split('/')[0] || ''
})
const lockedModule = computed(() => {
  const key = moduleKey.value
  if (!key || key === 'premium') return null
  if (!premium.cache.loaded) return null
  return premium.isUnlocked(key) ? null : key
})

const guildName = computed(() => {
  const g = settings.cache.guild
  if (g?.guild_name) return g.guild_name
  if (g?.name) return g.name
  return 'Server'
})

const guildIconUrl = computed(() => {
  const g = settings.cache.guild
  return g?.guild_icon_url || g?.icon_url || ''
})

async function load() {
  loadError.value = null
  // Premium status loads in parallel — its failure must not block the page.
  premium.load(guildId.value, { force: true })
  try {
    await settings.loadFull(guildId.value, { force: true })
  } catch (err) {
    loadError.value = err.response?.data?.error || err.message || 'Failed to load'
  }
}

function reload() {
  load()
}

function checkViewport() {
  isMobile.value = window.innerWidth <= 900
  if (!isMobile.value) mobileOpen.value = false
}

onMounted(() => {
  checkViewport()
  window.addEventListener('resize', checkViewport)
  load()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', checkViewport)
})

watch(() => route.params.guild_id, (n, o) => {
  if (n && n !== o) load()
})
</script>

<style scoped>
.dashboard-layout {
  padding: var(--space-6);
  /* keine max-width / margin auto: Sidebar soll an der linken Viewport-Kante kleben */
  min-height: calc(100vh - var(--nav-height));
}

.dashboard-layout__inner {
  display: flex;
  gap: var(--space-6);
  align-items: flex-start;
}

.dashboard-layout__main {
  flex: 1;
  min-width: 0;
  /* Inhalt zentriert + lesbare Maximalbreite, Sidebar bleibt trotzdem ganz links */
  max-width: var(--layout-max);
  margin: 0 auto;
  animation: fade-in 320ms var(--ease-out-expo) both;
}

.mobile-trigger {
  display: none;
  align-items: center;
  gap: var(--space-2);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  padding: 0.55rem 0.9rem;
  border-radius: var(--radius-md);
  font-weight: 500;
  font-size: 0.85rem;
  position: absolute;
  top: calc(var(--nav-height) + var(--space-3));
  right: var(--space-4);
  z-index: 5;
}

.loading-block,
.error-block {
  width: 100%;
}

.error-block__card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-8);
  text-align: center;
  max-width: 480px;
  margin: var(--space-12) auto;
}

.error-block__card h3 {
  margin-bottom: var(--space-2);
}
.error-block__card p {
  color: var(--color-text-muted);
  margin-bottom: var(--space-5);
}

@media (max-width: 900px) {
  .dashboard-layout__inner {
    flex-direction: column;
  }
  .mobile-trigger {
    display: inline-flex;
  }
}
</style>
