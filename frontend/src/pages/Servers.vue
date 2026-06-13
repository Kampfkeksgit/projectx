<template>
  <div class="servers">
    <div class="servers__inner">
      <header class="servers__head">
        <div class="servers__head-action servers__head-action--left">
          <AppButton variant="ghost" @click="goHome">
            <template #icon-left>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l9-9 9 9"/><path d="M5 10v10a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V10"/></svg>
            </template>
            {{ t('common.home') }}
          </AppButton>
        </div>

        <div class="servers__heading">
          <div class="servers__eyebrow">{{ t('servers.eyebrow') }}</div>
          <h1 class="servers__title">{{ t('servers.title') }}</h1>
          <p class="servers__sub">{{ t('servers.sub') }}</p>
        </div>

        <div class="servers__head-action servers__head-action--right">
          <AppButton variant="ghost" :loading="refreshing" @click="handleRefresh">
            <template #icon-left>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
            </template>
            {{ t('common.refresh') }}
          </AppButton>
        </div>
      </header>

      <LoadingPage v-if="loading" :message="t('servers.loading')" />

      <div v-else-if="error" class="empty">
        <div class="empty__icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        </div>
        <h3>{{ t('servers.errorTitle') }}</h3>
        <p>{{ error }}</p>
        <AppButton variant="gradient" @click="loadGuilds">{{ t('common.retry') }}</AppButton>
      </div>

      <div v-else-if="guilds.length === 0" class="empty">
        <div class="empty__icon empty__icon--soft">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
        </div>
        <h3>{{ t('servers.emptyTitle') }}</h3>
        <p>{{ t('servers.emptyBody') }}</p>
        <AppButton variant="gradient" :loading="refreshing" @click="handleRefresh">{{ t('servers.refreshButton') }}</AppButton>
      </div>

      <div v-else class="servers__grid">
        <button
          v-for="guild in guilds"
          :key="guild.id"
          class="guild-card"
          :class="{ 'guild-card--blocked': guild.blocked }"
          :aria-disabled="guild.blocked ? 'true' : 'false'"
          :title="guild.blocked ? t('servers.blockedHint') : guild.guild_name"
          @click="selectGuild(guild)"
        >
          <span
            v-if="guild.blocked"
            class="guild-card__badge guild-card__badge--blocked"
          >{{ t('servers.blockedBadge') }}</span>
          <span
            v-else-if="guild.owner"
            class="guild-card__badge guild-card__badge--owner"
          >{{ t('common.owner') }}</span>
          <span
            v-else-if="guild.admin"
            class="guild-card__badge guild-card__badge--admin"
          >{{ t('common.admin') }}</span>

          <div class="guild-card__avatar-wrap">
            <span class="guild-card__halo" aria-hidden="true"></span>
            <GuildAvatar :name="guild.guild_name" :icon-url="guild.guild_icon_url" size="xl" />
          </div>

          <div class="guild-card__name" :title="guild.guild_name">{{ guild.guild_name }}</div>

          <span v-if="guild.blocked" class="guild-card__cta guild-card__cta--blocked">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="5.6" y1="5.6" x2="18.4" y2="18.4"/></svg>
            {{ t('servers.blockedCta') }}
          </span>
          <span v-else class="guild-card__cta">
            {{ t('common.configure') }}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api.js'
import AppButton from '../components/AppButton.vue'
import GuildAvatar from '../components/GuildAvatar.vue'
import LoadingPage from '../components/LoadingPage.vue'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

const router = useRouter()
const toast = useToast()

const guilds = ref([])
const loading = ref(true)
const refreshing = ref(false)
const error = ref(null)

onMounted(() => {
  loadGuilds()
})

async function loadGuilds() {
  loading.value = true
  error.value = null
  try {
    const response = await api.get('/guilds')
    if (response.data?.success && Array.isArray(response.data.guilds)) {
      guilds.value = response.data.guilds
    } else if (Array.isArray(response.data)) {
      // tolerant fallback
      guilds.value = response.data
    } else {
      guilds.value = []
    }
  } catch (err) {
    console.error('Failed to fetch guilds:', err)
    error.value = err.response?.data?.error || t('servers.errorGeneric')
    guilds.value = []
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await api.post('/auth/refresh-guilds')
    await loadGuilds()
    toast.success(t('servers.listRefreshed'))
  } catch (err) {
    toast.error(t('servers.listRefreshFailed'))
  } finally {
    refreshing.value = false
  }
}

function selectGuild(guild) {
  if (guild.blocked) return
  router.push(`/dashboard/${guild.id}`)
}

function goHome() {
  router.push('/')
}
</script>

<style scoped>
.servers {
  padding: var(--space-10) var(--space-6) var(--space-16);
  min-height: calc(100vh - var(--nav-height));
  animation: fade-in 400ms var(--ease-out-expo) both;
}

.servers__inner {
  max-width: var(--layout-max);
  margin: 0 auto;
}

.servers__head {
  position: relative;
  margin-bottom: var(--space-8);
  min-height: 64px;
}

.servers__heading {
  text-align: center;
  max-width: 640px;
  margin: 0 auto;
}

.servers__head-action {
  position: absolute;
  top: 0;
}

.servers__head-action--left {
  left: 0;
}

.servers__head-action--right {
  right: 0;
}

.servers__eyebrow {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-soft);
  margin-bottom: var(--space-2);
}

.servers__title {
  font-size: clamp(1.8rem, 3vw, 2.4rem);
  letter-spacing: -0.025em;
  margin-bottom: var(--space-2);
}

.servers__sub {
  color: var(--color-text-muted);
  margin: 0 auto;
}

/* Buttons rücken unter den Titel, wenn der Header zu schmal wird */
@media (max-width: 640px) {
  .servers__head {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
  }
  .servers__head-action {
    position: static;
  }
}

.servers__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-5);
}

.guild-card {
  position: relative;
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6) var(--space-5) var(--space-5);
  min-height: 230px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-4);
  text-align: center;
  cursor: pointer;
  color: var(--color-text);
  overflow: hidden;
  transition:
    transform var(--transition),
    border-color var(--transition),
    box-shadow var(--transition);
}

/* gradient border on hover */
.guild-card::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  padding: 1px;
  background: var(--gradient-brand);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
          mask-composite: exclude;
  opacity: 0;
  transition: opacity var(--transition);
  pointer-events: none;
}

/* soft aurora wash from the top */
.guild-card::after {
  content: '';
  position: absolute;
  inset: -40% -10% auto -10%;
  height: 60%;
  background: radial-gradient(50% 70% at 50% 0%, rgba(88, 101, 242, 0.22) 0%, rgba(167, 139, 250, 0.10) 40%, transparent 75%);
  opacity: 0;
  transition: opacity var(--transition);
  pointer-events: none;
  z-index: 0;
}

.guild-card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-lg);
}

.guild-card:hover::before,
.guild-card:hover::after {
  opacity: 1;
}

/* avatar with halo */
.guild-card__avatar-wrap {
  position: relative;
  z-index: 1;
  margin-top: var(--space-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.guild-card__halo {
  position: absolute;
  inset: -22px;
  border-radius: 50%;
  background: radial-gradient(50% 50% at 50% 50%, rgba(88, 101, 242, 0.35) 0%, rgba(167, 139, 250, 0.18) 45%, transparent 75%);
  filter: blur(14px);
  opacity: 0;
  transform: scale(0.85);
  transition: opacity var(--transition), transform var(--transition);
  pointer-events: none;
}

.guild-card:hover .guild-card__halo {
  opacity: 1;
  transform: scale(1);
}

.guild-card :deep(.guild-avatar) {
  position: relative;
  z-index: 1;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.05),
    var(--shadow-lg);
  transition: transform var(--transition);
}

.guild-card:hover :deep(.guild-avatar) {
  transform: translateY(-2px) scale(1.03);
}

/* name */
.guild-card__name {
  position: relative;
  z-index: 1;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 1.04rem;
  letter-spacing: -0.015em;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 var(--space-2);
}

/* badge — pinned top-right */
.guild-card__badge {
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
  z-index: 2;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.28rem 0.6rem;
  border-radius: var(--radius-full);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  border: 1px solid transparent;
}

.guild-card__badge--owner {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.22), rgba(244, 114, 182, 0.18));
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.35);
  box-shadow: 0 0 18px rgba(245, 158, 11, 0.18);
}

.guild-card__badge--admin {
  background: rgba(88, 101, 242, 0.18);
  color: #c9cdfb;
  border-color: rgba(88, 101, 242, 0.4);
  box-shadow: 0 0 18px rgba(88, 101, 242, 0.16);
}

.guild-card__badge--blocked {
  background: var(--color-danger-soft);
  color: var(--color-danger);
  border-color: var(--color-danger);
  box-shadow: 0 0 18px rgba(239, 68, 68, 0.18);
}

/* Blocked guild — not configurable, red outline on hover */
.guild-card--blocked {
  cursor: not-allowed;
  opacity: 0.85;
}

/* recolor the gradient hover border to danger red */
.guild-card--blocked::before {
  background: var(--color-danger);
}

/* recolor the aurora wash to a red tint */
.guild-card--blocked::after {
  background: radial-gradient(50% 70% at 50% 0%, rgba(239, 68, 68, 0.22) 0%, rgba(239, 68, 68, 0.10) 40%, transparent 75%);
}

/* no lift on hover, but reveal the red border + dim avatar */
.guild-card--blocked:hover {
  transform: none;
  box-shadow: var(--shadow-lg);
  border-color: var(--color-danger);
}

.guild-card--blocked:hover .guild-card__halo {
  background: radial-gradient(50% 50% at 50% 50%, rgba(239, 68, 68, 0.30) 0%, rgba(239, 68, 68, 0.16) 45%, transparent 75%);
}

.guild-card--blocked:hover :deep(.guild-avatar) {
  transform: none;
}

.guild-card__cta--blocked {
  color: var(--color-danger);
}

.guild-card--blocked:hover .guild-card__cta--blocked {
  color: var(--color-danger);
}

/* configure hint — slides in on hover */
.guild-card__cta {
  position: relative;
  z-index: 1;
  margin-top: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--color-text-soft);
  opacity: 0;
  transform: translateY(4px);
  transition: opacity var(--transition), transform var(--transition), color var(--transition);
}

.guild-card__cta svg {
  transition: transform var(--transition);
}

.guild-card:hover .guild-card__cta {
  opacity: 1;
  transform: translateY(0);
  color: var(--color-text);
}

.guild-card:hover .guild-card__cta svg {
  transform: translateX(3px);
}

.guild-card:focus-visible {
  outline: none;
}

.guild-card:focus-visible::before {
  opacity: 1;
}

/* Empty state */
.empty {
  text-align: center;
  padding: var(--space-12) var(--space-6);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  max-width: 520px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
}

.empty__icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  background: var(--color-danger-soft);
  color: var(--color-danger);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.empty__icon--soft {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.empty h3 {
  font-size: 1.2rem;
}

.empty p {
  color: var(--color-text-muted);
  line-height: 1.55;
  max-width: 360px;
}
</style>
