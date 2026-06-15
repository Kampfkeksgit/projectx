<template>
  <header class="m-top">
    <div class="m-top__left">
      <button v-if="showBack" class="m-top__btn" @click="goBack" :aria-label="t('mobile.back')">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>
      <router-link v-else to="/" class="m-top__brand" aria-label="ProjectX">
        <img src="/logo.svg" width="30" height="30" alt="" aria-hidden="true" class="m-top__logo" />
      </router-link>
    </div>

    <div class="m-top__title" :title="title">{{ title }}</div>

    <div class="m-top__right">
      <button
        v-if="authed && auth.state.user"
        class="m-top__avatar"
        @click="$emit('open-account')"
        :aria-label="t('mobile.tabAccount')"
      >
        <img v-if="auth.state.user.avatar_url" :src="auth.state.user.avatar_url" :alt="auth.state.user.username" />
        <span v-else class="m-top__avatar-fallback">{{ initials }}</span>
      </button>
      <button
        v-else-if="auth.state.status === 'guest'"
        class="m-top__login"
        @click="auth.loginWithDiscord"
      >
        {{ t('mobile.login') }}
      </button>
      <span v-else class="m-top__spacer" aria-hidden="true"></span>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../stores/auth.js'
import { useGuildSettings } from '../stores/guildSettings.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuth()
const settings = useGuildSettings()

defineEmits(['open-account'])

const initials = computed(() => (auth.state.user?.username || '?').slice(0, 2).toUpperCase())

// Route-Name → i18n-Titel-Key. Modul-Seiten nutzen die Sidebar-Labels.
const TITLE_KEYS = {
  servers: 'nav.yourServers',
  admin: 'nav.adminPanel',
  premium: 'sidebar.linkPremium',
  welcome: 'sidebar.linkWelcome',
  leave: 'sidebar.linkLeave',
  autorole: 'sidebar.linkAutoRole',
  logs: 'sidebar.linkLogs',
  moderation: 'sidebar.linkModeration',
  'reaction-roles': 'sidebar.linkReactionRoles',
  leveling: 'sidebar.linkLeveling',
  'custom-commands': 'sidebar.linkCustomCommands',
  social: 'sidebar.linkSocial',
  stats: 'sidebar.linkStats',
  tempvoice: 'sidebar.linkTempVoice',
  starboard: 'sidebar.linkStarboard',
  suggestions: 'sidebar.linkSuggestions',
  birthday: 'sidebar.linkBirthday',
  scheduled: 'sidebar.linkScheduled',
  antiraid: 'sidebar.linkAntiRaid',
  verification: 'sidebar.linkVerification',
  rolemenus: 'sidebar.linkRoleMenus',
  tickets: 'sidebar.linkTickets',
  giveaways: 'sidebar.linkGiveaways'
}

const guildName = computed(() => {
  const g = settings.cache.guild
  return g?.guild_name || g?.name || 'Server'
})

const title = computed(() => {
  const name = route.name
  if (name === 'landing') return 'ProjectX'
  if (name === 'overview') return guildName.value
  const key = TITLE_KEYS[name]
  return key ? t(key) : 'ProjectX'
})

// Zurück-Pfeil: auf Modul-Unterseiten + Admin + Premium, nicht auf den Roots.
const showBack = computed(() => {
  const name = route.name
  if (!name || name === 'landing' || name === 'servers' || name === 'overview') return false
  return true
})

function goBack() {
  // Modul-Seite → zurück zur Server-Übersicht (Hub). Sonst History.
  if (route.params.guild_id && route.name !== 'overview') {
    router.push(`/dashboard/${route.params.guild_id}`)
  } else if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/dashboard')
  }
}
</script>

<style scoped>
.m-top {
  position: sticky;
  top: 0;
  z-index: 50;
  height: var(--mobile-topbar-h, 56px);
  padding: 0 var(--space-2);
  padding-top: env(safe-area-inset-top, 0px);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: rgba(11, 13, 18, 0.82);
  backdrop-filter: blur(16px) saturate(160%);
  -webkit-backdrop-filter: blur(16px) saturate(160%);
  border-bottom: 1px solid var(--color-border-soft);
}

.m-top__left,
.m-top__right {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
}
.m-top__right {
  justify-content: flex-end;
  min-width: 44px;
}

.m-top__btn {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--color-text);
}
.m-top__btn:active {
  background: var(--color-surface-2);
}

.m-top__brand {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.m-top__logo {
  border-radius: 8px;
  box-shadow: 0 6px 18px -8px rgba(88, 101, 242, 0.6);
}

.m-top__title {
  flex: 1;
  min-width: 0;
  text-align: center;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 1rem;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.m-top__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  border: 1px solid var(--color-border);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--gradient-brand);
}
.m-top__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.m-top__avatar-fallback {
  color: #fff;
  font-weight: 700;
  font-size: 0.78rem;
}

.m-top__login {
  padding: 0.45rem 0.85rem;
  border-radius: var(--radius-full);
  background: var(--gradient-brand);
  color: #fff;
  font-weight: 600;
  font-size: 0.82rem;
}

.m-top__spacer {
  width: 40px;
  height: 40px;
}
</style>
