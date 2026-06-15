<template>
  <transition name="m-sheet">
    <div v-if="open" class="m-sheet" @click.self="$emit('close')">
      <div class="m-sheet__panel" role="dialog" aria-modal="true">
        <div class="m-sheet__grabber" aria-hidden="true"></div>

        <div v-if="auth.state.user" class="m-sheet__head">
          <img
            v-if="auth.state.user.avatar_url"
            :src="auth.state.user.avatar_url"
            :alt="auth.state.user.username"
            class="m-sheet__avatar"
          />
          <span v-else class="m-sheet__avatar m-sheet__avatar--fallback">{{ initials }}</span>
          <div class="m-sheet__id">
            <div class="m-sheet__name">{{ auth.state.user.username }}</div>
            <div v-if="auth.state.user.email" class="m-sheet__email">{{ auth.state.user.email }}</div>
          </div>
        </div>

        <div class="m-sheet__row">
          <span class="m-sheet__row-label">{{ t('mobile.language') }}</span>
          <LanguageSwitcher />
        </div>

        <nav class="m-sheet__actions">
          <router-link to="/dashboard" class="m-sheet__action" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
            {{ t('nav.yourServers') }}
          </router-link>
          <router-link
            v-if="auth.state.user?.is_owner"
            to="/admin"
            class="m-sheet__action"
            @click="$emit('close')"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            {{ t('nav.adminPanel') }}
          </router-link>
          <button class="m-sheet__action m-sheet__action--danger" @click="handleLogout">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            {{ t('nav.logout') }}
          </button>
        </nav>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth.js'
import { useI18n } from '../i18n/index.js'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'

const { t } = useI18n()
const router = useRouter()
const auth = useAuth()

const props = defineProps({
  open: { type: Boolean, default: false }
})

const emit = defineEmits(['close'])

const initials = computed(() => (auth.state.user?.username || '?').slice(0, 2).toUpperCase())

async function handleLogout() {
  emit('close')
  await auth.logout(router)
}

void props
</script>

<style scoped>
.m-sheet {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: flex-end;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
}

.m-sheet__panel {
  width: 100%;
  background: var(--color-surface);
  border-top-left-radius: var(--radius-2xl);
  border-top-right-radius: var(--radius-2xl);
  border-top: 1px solid var(--color-border-strong);
  box-shadow: var(--shadow-xl);
  padding: var(--space-3) var(--space-5)
    calc(env(safe-area-inset-bottom, 0px) + var(--space-6));
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.m-sheet__grabber {
  width: 40px;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--color-border-strong);
  margin: 0 auto var(--space-2);
}

.m-sheet__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.m-sheet__avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--gradient-brand);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.m-sheet__avatar--fallback {
  color: #fff;
  font-weight: 700;
}

.m-sheet__id {
  min-width: 0;
}
.m-sheet__name {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 1.05rem;
}
.m-sheet__email {
  color: var(--color-text-soft);
  font-size: 0.82rem;
  word-break: break-all;
}

.m-sheet__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.m-sheet__row-label {
  color: var(--color-text-muted);
  font-weight: 500;
}

.m-sheet__actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.m-sheet__action {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: 0.85rem var(--space-3);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 0.95rem;
  font-weight: 500;
  text-align: left;
}
.m-sheet__action:active {
  background: var(--color-surface-2);
}
.m-sheet__action--danger {
  color: var(--color-danger);
}

.m-sheet-enter-from,
.m-sheet-leave-to {
  opacity: 0;
}
.m-sheet-enter-from .m-sheet__panel,
.m-sheet-leave-to .m-sheet__panel {
  transform: translateY(100%);
}
.m-sheet-enter-active,
.m-sheet-leave-active {
  transition: opacity 240ms ease;
}
.m-sheet-enter-active .m-sheet__panel,
.m-sheet-leave-active .m-sheet__panel {
  transition: transform 280ms cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
