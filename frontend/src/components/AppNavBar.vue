<template>
  <header class="navbar">
    <div class="navbar__inner">
      <router-link to="/" class="brand">
        <img src="/logo.svg" class="brand__logo" width="36" height="36" alt="" aria-hidden="true" />
        <span class="brand__text">
          <span class="brand__name">ProjectX</span>
          <span class="brand__sub">{{ t('nav.brandSubtitle') }}</span>
        </span>
      </router-link>

      <div class="navbar__actions">
        <LanguageSwitcher />

        <template v-if="auth.state.status === 'authenticated' && auth.state.user">
          <div class="user" @click.stop="toggleMenu" :class="{ 'is-open': menuOpen }">
            <img
              v-if="auth.state.user.avatar_url"
              :src="auth.state.user.avatar_url"
              :alt="auth.state.user.username"
              class="user__avatar"
            />
            <span v-else class="user__avatar user__avatar--fallback">{{ initials }}</span>
            <span class="user__name">{{ auth.state.user.username }}</span>
            <svg class="user__chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>

            <transition name="menu">
              <div v-if="menuOpen" class="user-menu" @click.stop>
                <div class="user-menu__header">
                  <div class="user-menu__name">{{ auth.state.user.username }}</div>
                  <div v-if="auth.state.user.email" class="user-menu__email">{{ auth.state.user.email }}</div>
                </div>
                <router-link to="/dashboard" class="user-menu__item" @click="menuOpen = false">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
                  {{ t('nav.yourServers') }}
                </router-link>
                <router-link v-if="auth.state.user.is_owner" to="/admin" class="user-menu__item" @click="menuOpen = false">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                  {{ t('nav.adminPanel') }}
                </router-link>
                <button class="user-menu__item user-menu__item--danger" @click="handleLogout">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                  {{ t('nav.logout') }}
                </button>
              </div>
            </transition>
          </div>
        </template>

        <template v-else-if="auth.state.status === 'guest'">
          <AppButton variant="gradient" @click="auth.loginWithDiscord">
            <template #icon-left>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.32 4.37A19.79 19.79 0 0 0 16.43 3l-.2.35a14.7 14.7 0 0 1 4.13 1.65 14.42 14.42 0 0 0-12.72 0A14.7 14.7 0 0 1 11.77 3.35L11.57 3a19.79 19.79 0 0 0-3.89 1.37C5.31 7.97 4.55 11.49 4.78 14.94a19.95 19.95 0 0 0 5.99 3.06l.86-1.18a12.7 12.7 0 0 1-2.13-1.04c.18-.13.35-.27.52-.41a10.3 10.3 0 0 0 7.96 0c.17.14.34.28.52.41-.68.42-1.4.78-2.13 1.04l.86 1.18a19.95 19.95 0 0 0 5.99-3.06c.27-3.97-.62-7.47-2.9-10.57ZM9.55 13.36c-.95 0-1.72-.89-1.72-1.98 0-1.1.76-1.99 1.72-1.99.97 0 1.74.89 1.72 1.99 0 1.09-.75 1.98-1.72 1.98Zm4.9 0c-.95 0-1.72-.89-1.72-1.98 0-1.1.76-1.99 1.72-1.99.97 0 1.74.89 1.72 1.99 0 1.09-.75 1.98-1.72 1.98Z"/></svg>
            </template>
            {{ t('nav.loginWithDiscord') }}
          </AppButton>
        </template>

        <template v-else>
          <div class="navbar__placeholder" aria-hidden="true"></div>
        </template>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth.js'
import { useI18n } from '../i18n/index.js'
import AppButton from './AppButton.vue'
import LanguageSwitcher from './LanguageSwitcher.vue'

const { t } = useI18n()

const router = useRouter()
const auth = useAuth()
const menuOpen = ref(false)

const initials = computed(() => {
  const n = auth.state.user?.username || '?'
  return n.slice(0, 2).toUpperCase()
})

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

function onDocClick() {
  if (menuOpen.value) menuOpen.value = false
}

async function handleLogout() {
  menuOpen.value = false
  await auth.logout(router)
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.navbar {
  position: sticky;
  top: 0;
  z-index: 50;
  width: 100%;
  height: var(--nav-height);
  background: rgba(11, 13, 18, 0.7);
  backdrop-filter: blur(16px) saturate(160%);
  -webkit-backdrop-filter: blur(16px) saturate(160%);
  border-bottom: 1px solid var(--color-border-soft);
}

.navbar__inner {
  max-width: var(--layout-max);
  margin: 0 auto;
  padding: 0 var(--space-6);
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text);
}

.brand__logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: block;
  box-shadow: 0 8px 24px -8px rgba(88, 101, 242, 0.6);
}

.brand__text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}

.brand__name {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 1.05rem;
  letter-spacing: -0.02em;
}

.brand__sub {
  font-size: 0.7rem;
  color: var(--color-text-soft);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.navbar__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.user {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.35rem 0.7rem 0.35rem 0.35rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
}

.user:hover, .user.is-open {
  border-color: var(--color-border-strong);
  background: var(--color-surface-2);
}

.user__avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  object-fit: cover;
  background: var(--gradient-brand);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.75rem;
}

.user__name {
  font-weight: 600;
  font-size: 0.9rem;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user__chev {
  color: var(--color-text-soft);
  transition: transform var(--transition);
}
.user.is-open .user__chev {
  transform: rotate(180deg);
}

.user-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 240px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  padding: var(--space-2);
  z-index: 60;
}

.user-menu__header {
  padding: 0.6rem 0.8rem 0.8rem;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: var(--space-2);
}

.user-menu__name {
  font-weight: 600;
  font-size: 0.95rem;
}
.user-menu__email {
  color: var(--color-text-soft);
  font-size: 0.8rem;
  margin-top: 2px;
  word-break: break-all;
}

.user-menu__item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
  text-align: left;
}

.user-menu__item:hover {
  background: var(--color-surface-2);
}

.user-menu__item--danger {
  color: var(--color-danger);
}
.user-menu__item--danger:hover {
  background: var(--color-danger-soft);
}

.menu-enter-from, .menu-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.menu-enter-active, .menu-leave-active {
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.navbar__placeholder {
  width: 96px;
  height: 36px;
  background: var(--color-surface-2);
  border-radius: var(--radius-full);
  opacity: 0.4;
}

@media (max-width: 640px) {
  .brand__sub {
    display: none;
  }
  .user__name {
    display: none;
  }
  .navbar__inner {
    padding: 0 var(--space-4);
  }
}
</style>
