<template>
  <div class="admin">
    <div class="admin__inner">
      <header class="admin__head">
        <div class="admin__head-action">
          <AppButton variant="ghost" @click="goBack">
            <template #icon-left>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
            </template>
            {{ t('nav.yourServers') }}
          </AppButton>
        </div>
        <div class="admin__heading">
          <div class="admin__eyebrow">{{ t('admin.eyebrow') }}</div>
          <h1 class="admin__title">{{ t('admin.title') }}</h1>
          <p class="admin__sub">{{ t('admin.sub') }}</p>
        </div>
      </header>

      <div class="admin__tabs">
        <button
          class="admin__tab"
          :class="{ 'is-active': tab === 'users' }"
          @click="switchTab('users')"
        >{{ t('admin.tabUsers') }}</button>
        <button
          class="admin__tab"
          :class="{ 'is-active': tab === 'guilds' }"
          @click="switchTab('guilds')"
        >{{ t('admin.tabGuilds') }}</button>
      </div>

      <div class="admin__toolbar">
        <div class="search">
          <svg class="search__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            v-model="search"
            class="search__input"
            :placeholder="tab === 'users' ? t('admin.searchUsers') : t('admin.searchGuilds')"
            @input="onSearchInput"
          />
        </div>
      </div>

      <LoadingPage v-if="loading" :message="t('common.loading')" />

      <!-- USERS -->
      <div v-else-if="tab === 'users'">
        <div v-if="users.length === 0" class="empty">
          <p>{{ t('admin.emptyUsers') }}</p>
        </div>
        <ul v-else class="rows">
          <li v-for="u in users" :key="u.discord_id" class="row" :class="{ 'is-blocked': u.blocked }">
            <div class="row__main">
              <img v-if="u.avatar_url" :src="u.avatar_url" :alt="u.username" class="row__avatar" />
              <span v-else class="row__avatar row__avatar--fallback">{{ initials(u.username) }}</span>
              <div class="row__text">
                <div class="row__name">
                  {{ u.username }}
                  <span v-if="isMe(u.discord_id)" class="row__tag">{{ t('admin.ownerBadge') }}</span>
                </div>
                <div class="row__sub">{{ u.discord_id }}</div>
                <div v-if="u.blocked && u.blocked_reason" class="row__reason">{{ t('admin.blockedReason', { reason: u.blocked_reason }) }}</div>
              </div>
            </div>
            <div class="row__right">
              <span class="status" :class="u.blocked ? 'status--blocked' : 'status--active'">
                {{ u.blocked ? t('admin.statusBlocked') : t('admin.statusActive') }}
              </span>
              <AppButton
                v-if="!isMe(u.discord_id)"
                :variant="u.blocked ? 'subtle' : 'danger'"
                :loading="busyId === u.discord_id"
                @click="u.blocked ? unblockUser(u) : askBlockUser(u)"
              >{{ u.blocked ? t('admin.unblock') : t('admin.block') }}</AppButton>
            </div>
          </li>
        </ul>
        <div v-if="!loading && users.length < total" class="admin__more">
          <AppButton variant="ghost" :loading="loadingMore" @click="loadMore">{{ t('admin.loadMore') }}</AppButton>
        </div>
      </div>

      <!-- GUILDS -->
      <div v-else>
        <div v-if="guilds.length === 0" class="empty">
          <p>{{ t('admin.emptyGuilds') }}</p>
        </div>
        <ul v-else class="rows">
          <li v-for="g in guilds" :key="g.id" class="row" :class="{ 'is-blocked': g.blocked }">
            <div class="row__main">
              <GuildAvatar :name="g.guild_name" :icon-url="g.guild_icon_url" size="md" />
              <div class="row__text">
                <div class="row__name">{{ g.guild_name }}</div>
                <div class="row__sub">
                  {{ g.id }}
                  <span class="dot" :class="g.bot_present ? 'dot--on' : 'dot--off'"></span>
                  {{ g.bot_present ? t('admin.botPresent') : t('admin.botAbsent') }}
                </div>
                <div v-if="g.blocked && g.blocked_reason" class="row__reason">{{ t('admin.blockedReason', { reason: g.blocked_reason }) }}</div>
              </div>
            </div>
            <div class="row__right">
              <select
                class="tier-select"
                :class="`tier-select--${g.premium_tier || 'free'}`"
                :value="g.premium_tier || 'free'"
                :disabled="busyId === g.id"
                :title="t('admin.tierTitle')"
                @change="setPremium(g, $event.target.value)"
              >
                <option value="free">{{ t('premium.tiers.free.name') }}</option>
                <option value="basic">{{ t('premium.tiers.basic.name') }}</option>
                <option value="pro">{{ t('premium.tiers.pro.name') }}</option>
              </select>
              <span class="status" :class="g.blocked ? 'status--blocked' : 'status--active'">
                {{ g.blocked ? t('admin.statusBlocked') : t('admin.statusActive') }}
              </span>
              <AppButton
                :variant="g.blocked ? 'subtle' : 'danger'"
                :loading="busyId === g.id"
                @click="g.blocked ? unblockGuild(g) : askBlockGuild(g)"
              >{{ g.blocked ? t('admin.unblock') : t('admin.block') }}</AppButton>
            </div>
          </li>
        </ul>
        <div v-if="!loading && guilds.length < total" class="admin__more">
          <AppButton variant="ghost" :loading="loadingMore" @click="loadMore">{{ t('admin.loadMore') }}</AppButton>
        </div>
      </div>
    </div>

    <!-- Block confirm modal — teleported to <body> so it's a true viewport
         overlay (the .admin container has a transform from its fade-in, which
         would otherwise make position:fixed relative to .admin, pushing the
         modal off-screen on tall pages). -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="confirmTarget" class="modal-overlay" @click.self="confirmTarget = null">
          <div class="modal">
            <h3 class="modal__title">{{ confirmTarget.kind === 'user' ? t('admin.blockUserTitle') : t('admin.blockGuildTitle') }}</h3>
            <p class="modal__body">
              {{ confirmTarget.kind === 'user'
                ? t('admin.blockUserBody', { name: confirmTarget.name })
                : t('admin.blockGuildBody', { name: confirmTarget.name }) }}
            </p>
            <label class="modal__label">{{ t('admin.reasonLabel') }}</label>
            <input v-model="reason" class="modal__input" :placeholder="t('admin.reasonPlaceholder')" maxlength="500" />
            <div class="modal__actions">
              <AppButton variant="ghost" @click="confirmTarget = null">{{ t('admin.cancel') }}</AppButton>
              <AppButton variant="danger" :loading="busyId === confirmTarget?.id" @click="confirmBlock">{{ t('admin.confirmBlock') }}</AppButton>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>
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
import { useAuth } from '../stores/auth.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const auth = useAuth()

const tab = ref('users')
const search = ref('')
const loading = ref(true)
const loadingMore = ref(false)
const busyId = ref(null)

const users = ref([])
const guilds = ref([])
const total = ref(0)
const PAGE = 50

const confirmTarget = ref(null) // { kind: 'user'|'guild', id, name }
const reason = ref('')

let searchTimer = null

onMounted(() => {
  load()
})

function isMe(id) {
  return auth.state.user?.id === id
}

function initials(name) {
  return (name || '?').slice(0, 2).toUpperCase()
}

function switchTab(next) {
  if (tab.value === next) return
  tab.value = next
  search.value = ''
  load()
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => load(), 300)
}

async function load() {
  loading.value = true
  try {
    if (tab.value === 'users') {
      const { data } = await api.get('/admin/users', { params: { search: search.value, limit: PAGE, offset: 0 } })
      users.value = data.users || []
      total.value = data.total || 0
    } else {
      const { data } = await api.get('/admin/guilds', { params: { search: search.value, limit: PAGE, offset: 0 } })
      guilds.value = data.guilds || []
      total.value = data.total || 0
    }
  } catch (err) {
    toast.error(t('admin.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  loadingMore.value = true
  try {
    if (tab.value === 'users') {
      const { data } = await api.get('/admin/users', { params: { search: search.value, limit: PAGE, offset: users.value.length } })
      users.value = users.value.concat(data.users || [])
      total.value = data.total || total.value
    } else {
      const { data } = await api.get('/admin/guilds', { params: { search: search.value, limit: PAGE, offset: guilds.value.length } })
      guilds.value = guilds.value.concat(data.guilds || [])
      total.value = data.total || total.value
    }
  } catch (err) {
    toast.error(t('admin.loadFailed'))
  } finally {
    loadingMore.value = false
  }
}

function askBlockUser(u) {
  reason.value = ''
  confirmTarget.value = { kind: 'user', id: u.discord_id, name: u.username }
}

function askBlockGuild(g) {
  reason.value = ''
  confirmTarget.value = { kind: 'guild', id: g.id, name: g.guild_name }
}

async function confirmBlock() {
  const target = confirmTarget.value
  if (!target) return
  busyId.value = target.id
  try {
    if (target.kind === 'user') {
      await api.post(`/admin/users/${target.id}/block`, { blocked: true, reason: reason.value })
      const u = users.value.find((x) => x.discord_id === target.id)
      if (u) { u.blocked = true; u.blocked_reason = reason.value || null }
      toast.success(t('admin.userBlocked'))
    } else {
      await api.post(`/admin/guilds/${target.id}/block`, { blocked: true, reason: reason.value })
      const g = guilds.value.find((x) => x.id === target.id)
      if (g) { g.blocked = true; g.blocked_reason = reason.value || null }
      toast.success(t('admin.guildBlocked'))
    }
    confirmTarget.value = null
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally {
    busyId.value = null
  }
}

async function unblockUser(u) {
  busyId.value = u.discord_id
  try {
    await api.post(`/admin/users/${u.discord_id}/block`, { blocked: false })
    u.blocked = false
    u.blocked_reason = null
    toast.success(t('admin.userUnblocked'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally {
    busyId.value = null
  }
}

async function unblockGuild(g) {
  busyId.value = g.id
  try {
    await api.post(`/admin/guilds/${g.id}/block`, { blocked: false })
    g.blocked = false
    g.blocked_reason = null
    toast.success(t('admin.guildUnblocked'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally {
    busyId.value = null
  }
}

async function setPremium(g, tier) {
  const prev = g.premium_tier || 'free'
  if (tier === prev) return
  busyId.value = g.id
  try {
    await api.post(`/admin/guilds/${g.id}/premium`, { tier })
    g.premium_tier = tier
    g.premium_source = tier === 'free' ? null : 'manual'
    toast.success(t('admin.tierUpdated', { tier: t(`premium.tiers.${tier}.name`) }))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally {
    busyId.value = null
  }
}

function goBack() {
  router.push('/dashboard')
}
</script>

<style scoped>
.admin {
  padding: var(--space-10) var(--space-6) var(--space-16);
  min-height: calc(100vh - var(--nav-height));
  animation: fade-in 400ms var(--ease-out-expo) both;
}

.admin__inner {
  max-width: 880px;
  margin: 0 auto;
}

.admin__head {
  position: relative;
  margin-bottom: var(--space-8);
  min-height: 64px;
}

.admin__head-action {
  position: absolute;
  top: 0;
  left: 0;
}

.admin__heading {
  text-align: center;
  max-width: 640px;
  margin: 0 auto;
}

.admin__eyebrow {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin-bottom: var(--space-2);
}

.admin__title {
  font-size: clamp(1.8rem, 3vw, 2.4rem);
  letter-spacing: -0.025em;
  margin-bottom: var(--space-2);
}

.admin__sub {
  color: var(--color-text-muted);
  margin: 0 auto;
  max-width: 520px;
}

@media (max-width: 640px) {
  .admin__head {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
  }
  .admin__head-action {
    position: static;
  }
}

.admin__tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  margin-bottom: var(--space-5);
}

.admin__tab {
  padding: 0.5rem 1.2rem;
  border-radius: var(--radius-full);
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--color-text-soft);
  cursor: pointer;
  transition: background var(--transition), color var(--transition);
}

.admin__tab.is-active {
  background: var(--color-primary);
  color: #fff;
}

.admin__toolbar {
  margin-bottom: var(--space-5);
}

.search {
  position: relative;
  max-width: 360px;
}

.search__icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-soft);
}

.search__input {
  width: 100%;
  padding: 0.65rem 0.9rem 0.65rem 2.3rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 0.9rem;
}

.search__input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition: border-color var(--transition);
}

.row.is-blocked {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

.row__main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.row__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--gradient-brand);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.8rem;
}

.row__text {
  min-width: 0;
}

.row__name {
  font-weight: 600;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row__tag {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-full);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.row__sub {
  font-size: 0.78rem;
  color: var(--color-text-soft);
  font-family: var(--font-mono);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.row__reason {
  font-size: 0.78rem;
  color: var(--color-danger);
  margin-top: 3px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}
.dot--on { background: var(--color-success, #22c55e); }
.dot--off { background: var(--color-text-soft); }

.row__right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.status {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.25rem 0.6rem;
  border-radius: var(--radius-full);
}
.status--active {
  background: var(--color-surface-2);
  color: var(--color-text-soft);
}
.status--blocked {
  background: var(--color-danger);
  color: #fff;
}

.tier-select {
  padding: 0.4rem 0.6rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-elevated);
  color: var(--color-text);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
}
.tier-select:focus { outline: none; border-color: var(--color-primary); }
.tier-select--basic { border-color: rgba(99, 102, 241, 0.5); color: #a5b4fc; }
.tier-select--pro { border-color: rgba(167, 139, 250, 0.6); color: #c4b5fd; }

.admin__more {
  display: flex;
  justify-content: center;
  margin-top: var(--space-5);
}

.empty {
  text-align: center;
  padding: var(--space-12) var(--space-6);
  color: var(--color-text-muted);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 8000;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
}

.modal {
  width: 100%;
  max-width: 440px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  padding: var(--space-6);
}

.modal__title {
  font-size: 1.2rem;
  margin-bottom: var(--space-3);
}

.modal__body {
  color: var(--color-text-muted);
  line-height: 1.55;
  margin-bottom: var(--space-4);
}

.modal__label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-soft);
  margin-bottom: var(--space-2);
}

.modal__input {
  width: 100%;
  padding: 0.65rem 0.9rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 0.9rem;
  margin-bottom: var(--space-5);
}

.modal__input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-active, .modal-leave-active {
  transition: opacity var(--transition);
}
</style>
