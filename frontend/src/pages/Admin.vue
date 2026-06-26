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
        <button v-for="tb in tabs" :key="tb" class="admin__tab" :class="{ 'is-active': tab === tb }" @click="switchTab(tb)">
          {{ t(`admin.tab${cap(tb)}`) }}
        </button>
      </div>

      <!-- toolbar: search (users/guilds/audit) + export (users/guilds) -->
      <div v-if="showToolbar" class="admin__toolbar">
        <div v-if="tab === 'audit'" class="filter">
          <select v-model="auditAction" class="filter__select" @change="load">
            <option value="">{{ t('admin.auditAllActions') }}</option>
            <option v-for="a in auditActions" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div v-if="tab === 'jobs'" class="filter">
          <select v-model="jobStatus" class="filter__select" @change="load">
            <option value="">{{ t('admin.jobsAllStatus') }}</option>
            <option v-for="s in JOB_STATUSES" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <template v-if="tab === 'errors'">
          <div class="filter">
            <select v-model="errSource" class="filter__select" @change="load">
              <option value="">{{ t('admin.errAllSources') }}</option>
              <option value="bot">bot</option>
              <option value="backend">backend</option>
            </select>
          </div>
          <div class="filter">
            <select v-model="errLevel" class="filter__select" @change="load">
              <option value="">{{ t('admin.errAllLevels') }}</option>
              <option value="error">error</option>
              <option value="warning">warning</option>
            </select>
          </div>
        </template>
        <div v-if="['users', 'guilds', 'audit'].includes(tab)" class="search">
          <svg class="search__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input v-model="search" class="search__input" :placeholder="searchPlaceholder" @input="onSearchInput" />
        </div>
        <AppButton v-if="tab === 'users' || tab === 'guilds'" variant="ghost" @click="exportCsv(tab)">
          {{ t('admin.exportBtn') }}
        </AppButton>
        <AppButton v-if="tab === 'errors' && errors.length" variant="danger" @click="clearErrors">
          {{ t('admin.errClear') }}
        </AppButton>
      </div>

      <LoadingPage v-if="loading" :message="t('common.loading')" />

      <!-- OVERVIEW -->
      <div v-else-if="tab === 'overview' && overview">
        <div class="cards">
          <div class="card">
            <div class="card__label">{{ t('admin.ovUsers') }}</div>
            <div class="card__value">{{ overview.users.total }}</div>
            <div class="card__meta">{{ t('admin.ovUsersBlocked', { n: overview.users.blocked }) }}</div>
          </div>
          <div class="card">
            <div class="card__label">{{ t('admin.ovServers') }}</div>
            <div class="card__value">{{ overview.guilds.total }}</div>
            <div class="card__meta">
              <span class="dot dot--on"></span> {{ overview.guilds.bot_present }}
              <span class="dot dot--off" style="margin-left:8px"></span> {{ overview.guilds.bot_absent }}
              <span v-if="overview.guilds.blocked"> · {{ t('admin.ovServersBlocked', { n: overview.guilds.blocked }) }}</span>
            </div>
          </div>
          <div class="card">
            <div class="card__label">{{ t('admin.ovPremium') }}</div>
            <div class="card__value">{{ overview.premium.basic + overview.premium.pro }}</div>
            <div class="card__meta">
              <span class="pill pill--basic">{{ t('premium.tiers.basic.name') }} {{ overview.premium.basic }}</span>
              <span class="pill pill--pro">{{ t('premium.tiers.pro.name') }} {{ overview.premium.pro }}</span>
            </div>
          </div>
          <div class="card">
            <div class="card__label">{{ t('admin.ovAuditDay') }}</div>
            <div class="card__value">{{ overview.audit_last_24h }}</div>
            <div class="card__meta">
              <button class="linkbtn" @click="switchTab('audit')">{{ t('admin.tabAudit') }} →</button>
            </div>
          </div>
        </div>

        <div class="panel">
          <h3 class="panel__title">{{ t('admin.ovExpiringTitle') }}</h3>
          <p v-if="!overview.premium_expiring.length" class="panel__empty">{{ t('admin.ovExpiringEmpty') }}</p>
          <ul v-else class="mini-rows">
            <li v-for="g in overview.premium_expiring" :key="g.id" class="mini-row">
              <GuildAvatar :name="g.guild_name" :icon-url="g.guild_icon_url" size="sm" />
              <span class="mini-row__name">{{ g.guild_name }}</span>
              <span class="pill" :class="`pill--${g.premium_tier}`">{{ t(`premium.tiers.${g.premium_tier}.name`) }}</span>
              <span class="mini-row__time">{{ t('admin.ovExpiresIn', { date: fmtDate(g.premium_until) }) }}</span>
            </li>
          </ul>
        </div>

        <div class="panel">
          <h3 class="panel__title">{{ t('admin.ovAdoptionTitle') }}</h3>
          <div class="adoption">
            <div v-for="m in adoptionList" :key="m.key" class="adoption__row">
              <span class="adoption__key">{{ prettyKey(m.key) }}</span>
              <div class="adoption__bar"><div class="adoption__fill" :style="{ width: barWidth(m.count) }"></div></div>
              <span class="adoption__count">{{ m.count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- USERS -->
      <div v-else-if="tab === 'users'">
        <div v-if="users.length === 0" class="empty"><p>{{ t('admin.emptyUsers') }}</p></div>
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
                <div v-if="u.blocked && u.blocked_until" class="row__until">{{ t('admin.blockedUntil', { date: fmtDate(u.blocked_until) }) }}</div>
                <div v-if="u.blocked && u.blocked_reason" class="row__reason">{{ t('admin.blockedReason', { reason: u.blocked_reason }) }}</div>
              </div>
            </div>
            <div class="row__right">
              <span class="status" :class="u.blocked ? 'status--blocked' : 'status--active'">
                {{ u.blocked ? t('admin.statusBlocked') : t('admin.statusActive') }}
              </span>
              <AppButton v-if="!isMe(u.discord_id)" :variant="u.blocked ? 'subtle' : 'danger'" :loading="busyId === u.discord_id" @click="u.blocked ? unblockUser(u) : askBlockUser(u)">
                {{ u.blocked ? t('admin.unblock') : t('admin.block') }}
              </AppButton>
            </div>
          </li>
        </ul>
        <div v-if="!loading && users.length < total" class="admin__more">
          <AppButton variant="ghost" :loading="loadingMore" @click="loadMore">{{ t('admin.loadMore') }}</AppButton>
        </div>
      </div>

      <!-- GUILDS -->
      <div v-else-if="tab === 'guilds'">
        <div v-if="guilds.length === 0" class="empty"><p>{{ t('admin.emptyGuilds') }}</p></div>
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
                <div v-if="g.premium_until" class="row__until">{{ t('admin.premiumUntil', { date: fmtDate(g.premium_until) }) }}</div>
                <div v-if="g.blocked && g.blocked_until" class="row__until">{{ t('admin.blockedUntil', { date: fmtDate(g.blocked_until) }) }}</div>
                <div v-if="g.blocked && g.blocked_reason" class="row__reason">{{ t('admin.blockedReason', { reason: g.blocked_reason }) }}</div>
              </div>
            </div>
            <div class="row__right">
              <AppButton variant="subtle" @click="inspectGuild(g)">{{ t('admin.inspectBtn') }}</AppButton>
              <select class="tier-select" :class="`tier-select--${g.premium_tier || 'free'}`" :value="g.premium_tier || 'free'" :disabled="busyId === g.id" :title="t('admin.tierTitle')" @change="setPremium(g, $event.target.value)">
                <option value="free">{{ t('premium.tiers.free.name') }}</option>
                <option value="basic">{{ t('premium.tiers.basic.name') }}</option>
                <option value="pro">{{ t('premium.tiers.pro.name') }}</option>
              </select>
              <span class="status" :class="g.blocked ? 'status--blocked' : 'status--active'">
                {{ g.blocked ? t('admin.statusBlocked') : t('admin.statusActive') }}
              </span>
              <AppButton :variant="g.blocked ? 'subtle' : 'danger'" :loading="busyId === g.id" @click="g.blocked ? unblockGuild(g) : askBlockGuild(g)">
                {{ g.blocked ? t('admin.unblock') : t('admin.block') }}
              </AppButton>
            </div>
          </li>
        </ul>
        <div v-if="!loading && guilds.length < total" class="admin__more">
          <AppButton variant="ghost" :loading="loadingMore" @click="loadMore">{{ t('admin.loadMore') }}</AppButton>
        </div>
      </div>

      <!-- AUDIT -->
      <div v-else-if="tab === 'audit'">
        <div v-if="audit.length === 0" class="empty"><p>{{ t('admin.auditEmpty') }}</p></div>
        <ul v-else class="rows">
          <li v-for="e in audit" :key="e.id" class="audit-row">
            <div class="audit-row__head">
              <span class="audit-row__action">{{ e.action }}</span>
              <span class="audit-row__time">{{ fmtDateTime(e.created_at) }}</span>
            </div>
            <div class="audit-row__meta">
              <span>{{ t('admin.auditActor') }}: {{ e.actor_username || (e.user_id || t('admin.auditSystem')) }}</span>
              <span v-if="e.guild_name || e.guild_id"> · {{ t('admin.colGuild') }}: {{ e.guild_name || e.guild_id }}</span>
            </div>
            <pre v-if="e.changes" class="audit-row__changes">{{ fmtChanges(e.changes) }}</pre>
          </li>
        </ul>
        <div v-if="!loading && audit.length < total" class="admin__more">
          <AppButton variant="ghost" :loading="loadingMore" @click="loadMore">{{ t('admin.loadMore') }}</AppButton>
        </div>
      </div>

      <!-- ANALYTICS (growth & adoption) -->
      <div v-else-if="tab === 'analytics'">
        <div class="charts-grid">
          <StatsChart :title="t('admin.anServers')" :points="metrics" :lines="serverLines" :empty-text="t('admin.anEmpty')" />
          <StatsChart :title="t('admin.anUsers')" :points="metrics" :lines="userLines" :empty-text="t('admin.anEmpty')" />
          <StatsChart :title="t('admin.anPremium')" :points="metrics" :lines="premiumLines" :empty-text="t('admin.anEmpty')" />
          <StatsChart :title="t('admin.anAdoption')" :points="adoptionPoints" :lines="adoptionLines" :empty-text="t('admin.anEmpty')" />
        </div>

        <div class="panel">
          <div class="panel__head-row">
            <h3 class="panel__title">{{ t('admin.anTopGuilds') }}</h3>
            <div class="seg">
              <button class="seg__btn" :class="{ 'is-active': topBy === 'modules' }" @click="setTopBy('modules')">{{ t('admin.anByModules') }}</button>
              <button class="seg__btn" :class="{ 'is-active': topBy === 'activity' }" @click="setTopBy('activity')">{{ t('admin.anByActivity') }}</button>
            </div>
          </div>
          <p v-if="!topGuilds.length" class="panel__empty">{{ t('admin.anTopEmpty') }}</p>
          <ul v-else class="mini-rows">
            <li v-for="(g, i) in topGuilds" :key="g.id" class="mini-row">
              <span class="mini-row__rank">{{ i + 1 }}</span>
              <GuildAvatar :name="g.guild_name || g.id" :icon-url="g.guild_icon_url" size="sm" />
              <span class="mini-row__name">{{ g.guild_name || g.id }}</span>
              <span class="pill">{{ topBy === 'activity' ? t('admin.anEvents', { n: g.score }) : t('admin.anModules', { n: g.score }) }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- HEALTH (bot monitoring) -->
      <div v-else-if="tab === 'health' && health">
        <div class="cards">
          <div class="card">
            <div class="card__label">{{ t('admin.healthBot') }}</div>
            <div class="card__value"><span class="dot" :class="health.bot.online ? 'dot--on' : 'dot--off'"></span> {{ health.bot.online ? t('admin.healthOnline') : t('admin.healthOffline') }}</div>
            <div class="card__meta">{{ health.bot.last_seen_seconds_ago != null ? t('admin.healthLastSeen', { ago: fmtDuration(health.bot.last_seen_seconds_ago) }) : t('admin.healthNeverSeen') }}</div>
          </div>
          <div class="card">
            <div class="card__label">{{ t('admin.healthLatency') }}</div>
            <div class="card__value">{{ health.bot.latency_ms != null ? health.bot.latency_ms + ' ms' : '—' }}</div>
          </div>
          <div class="card">
            <div class="card__label">{{ t('admin.healthUptime') }}</div>
            <div class="card__value">{{ health.bot.online ? fmtDuration(health.bot.uptime_seconds) : '—' }}</div>
          </div>
          <div class="card">
            <div class="card__label">{{ t('admin.healthServers') }}</div>
            <div class="card__value">{{ health.bot.guild_count }}</div>
            <div class="card__meta">{{ t('admin.healthUsers', { n: health.bot.user_count }) }}</div>
          </div>
          <div class="card">
            <div class="card__label">{{ t('admin.healthVersion') }}</div>
            <div class="card__value">{{ health.bot.version || '—' }}</div>
            <div class="card__meta">{{ t('admin.healthBackend', { v: health.backend.version || '—', node: health.backend.node }) }}</div>
          </div>
        </div>
        <div class="admin__more">
          <AppButton variant="ghost" @click="load">{{ t('common.refresh') }}</AppButton>
        </div>
      </div>

      <!-- JOBS (backup queue across all guilds) -->
      <div v-else-if="tab === 'jobs'">
        <div v-if="jobs.length === 0" class="empty"><p>{{ t('admin.jobsEmpty') }}</p></div>
        <ul v-else class="rows">
          <li v-for="j in jobs" :key="j.id" class="row">
            <div class="row__main">
              <GuildAvatar :name="j.guild_name || j.guild_id" :icon-url="j.guild_icon_url" size="sm" />
              <div class="row__text">
                <div class="row__name">{{ j.type }} <span class="job-status" :class="`job-status--${j.status}`">{{ j.status }}</span></div>
                <div class="row__sub">{{ j.guild_name || j.guild_id }} · {{ fmtDateTimeUnix(j.updated_at || j.created_at) }}</div>
                <div v-if="j.message" class="row__reason">{{ j.message }}</div>
              </div>
            </div>
            <div class="row__right">
              <AppButton v-if="j.status === 'failed'" variant="subtle" :loading="busyId === j.id" @click="retryJob(j)">{{ t('admin.jobsRetry') }}</AppButton>
            </div>
          </li>
        </ul>
        <div v-if="!loading && jobs.length < total" class="admin__more">
          <AppButton variant="ghost" :loading="loadingMore" @click="loadMore">{{ t('admin.loadMore') }}</AppButton>
        </div>
      </div>

      <!-- ERRORS (central error log) -->
      <div v-else-if="tab === 'errors'">
        <div v-if="errors.length === 0" class="empty"><p>{{ t('admin.errEmpty') }}</p></div>
        <ul v-else class="rows">
          <li v-for="e in errors" :key="e.id" class="audit-row">
            <div class="audit-row__head">
              <span class="audit-row__action">
                <span class="job-status" :class="e.level === 'warning' ? 'job-status--running' : 'job-status--failed'">{{ e.source }}/{{ e.level }}</span>
                {{ e.context }}
              </span>
              <span class="audit-row__time">{{ fmtDateTimeUnix(e.created_at) }}</span>
            </div>
            <div class="audit-row__meta">
              <span>{{ e.message }}</span>
              <span v-if="e.guild_id"> · {{ t('admin.colGuild') }}: {{ e.guild_id }}</span>
            </div>
            <pre v-if="e.stack" class="audit-row__changes">{{ e.stack }}</pre>
          </li>
        </ul>
        <div v-if="!loading && errors.length < total" class="admin__more">
          <AppButton variant="ghost" :loading="loadingMore" @click="loadMore">{{ t('admin.loadMore') }}</AppButton>
        </div>
      </div>

      <!-- SYSTEM (maintenance) -->
      <div v-else-if="tab === 'system'">
        <div class="panel panel--form">
          <h3 class="panel__title">{{ t('admin.sysTitle') }}</h3>
          <p class="panel__desc">{{ t('admin.sysDesc') }}</p>
          <label class="toggle-row">
            <AppToggle v-model="maintenance.enabled" />
            <span>{{ maintenance.enabled ? t('admin.maintenanceOn') : t('admin.maintenanceOff') }}</span>
          </label>
          <label class="modal__label">{{ t('admin.sysMessageLabel') }}</label>
          <input v-model="maintenance.message" class="modal__input" :placeholder="t('admin.sysMessagePlaceholder')" maxlength="500" />
          <div class="panel__actions">
            <AppButton variant="primary" :loading="savingMaintenance" @click="saveMaintenance">{{ t('admin.sysSave') }}</AppButton>
          </div>
        </div>
      </div>
    </div>

    <!-- Block confirm modal (with temp-ban duration) -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="confirmTarget" class="modal-overlay" @click.self="confirmTarget = null">
          <div class="modal">
            <h3 class="modal__title">{{ confirmTarget.kind === 'user' ? t('admin.blockUserTitle') : t('admin.blockGuildTitle') }}</h3>
            <p class="modal__body">
              {{ confirmTarget.kind === 'user' ? t('admin.blockUserBody', { name: confirmTarget.name }) : t('admin.blockGuildBody', { name: confirmTarget.name }) }}
            </p>
            <label class="modal__label">{{ t('admin.durationLabel') }}</label>
            <select v-model="banDuration" class="modal__input">
              <option v-for="d in DURATIONS" :key="d.key" :value="d.key">{{ t(`admin.dur${cap(d.key)}`) }}</option>
            </select>
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

    <!-- Guild inspector modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="inspect" class="modal-overlay" @click.self="inspect = null">
          <div class="modal modal--wide">
            <h3 class="modal__title">{{ t('admin.inspectTitle') }}</h3>
            <div class="insp-head">
              <GuildAvatar :name="inspect.guild_name" :icon-url="inspect.guild_icon_url" size="md" />
              <div>
                <div class="row__name">{{ inspect.guild_name }}</div>
                <div class="row__sub">{{ inspect.id }}</div>
              </div>
            </div>
            <div class="insp-facts">
              <span class="pill"><span class="dot" :class="inspect.bot_present ? 'dot--on' : 'dot--off'"></span> {{ inspect.bot_present ? t('admin.botPresent') : t('admin.botAbsent') }}</span>
              <span class="pill" :class="`pill--${inspect.premium_effective}`">{{ t(`premium.tiers.${inspect.premium_effective}.name`) }}<template v-if="inspect.premium_source"> · {{ inspect.premium_source }}</template></span>
              <span class="pill">{{ t('admin.inspectMembers', { n: inspect.dashboard_members }) }}</span>
            </div>

            <h4 class="insp-sub">{{ t('admin.inspectModules') }}</h4>
            <div class="insp-modules">
              <span v-for="m in inspect.modules" :key="m.key" class="insp-mod" :class="{ 'insp-mod--on': m.enabled }">
                <span class="insp-mod__dot"></span>{{ prettyKey(m.key) }}<template v-if="m.kind === 'count' && m.count"> ({{ m.count }})</template>
              </span>
            </div>

            <h4 class="insp-sub">{{ t('admin.inspectPremium') }}</h4>
            <div class="insp-premium">
              <select v-model="inspectTier" class="modal__input modal__input--inline">
                <option value="free">{{ t('premium.tiers.free.name') }}</option>
                <option value="basic">{{ t('premium.tiers.basic.name') }}</option>
                <option value="pro">{{ t('premium.tiers.pro.name') }}</option>
              </select>
              <select v-model="inspectDuration" class="modal__input modal__input--inline" :disabled="inspectTier === 'free'">
                <option v-for="d in PREMIUM_DURATIONS" :key="d.key" :value="d.key">{{ t(`admin.dur${cap(d.key)}`) }}</option>
              </select>
              <AppButton variant="primary" :loading="savingPremium" @click="applyInspectPremium">{{ t('admin.inspectApplyPremium') }}</AppButton>
            </div>

            <div class="modal__actions">
              <AppButton variant="ghost" @click="inspect = null">{{ t('admin.inspectClose') }}</AppButton>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api.js'
import AppButton from '../components/AppButton.vue'
import AppToggle from '../components/AppToggle.vue'
import GuildAvatar from '../components/GuildAvatar.vue'
import LoadingPage from '../components/LoadingPage.vue'
import StatsChart from '../components/StatsChart.vue'
import { useToast } from '../composables/useToast.js'
import { useAuth } from '../stores/auth.js'
import { useI18n } from '../i18n/index.js'

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const auth = useAuth()

const tabs = ['overview', 'analytics', 'health', 'users', 'guilds', 'audit', 'jobs', 'errors', 'system']
const tab = ref('overview')
const search = ref('')
const loading = ref(true)
const loadingMore = ref(false)
const busyId = ref(null)

const users = ref([])
const guilds = ref([])
const audit = ref([])
const auditActions = ref([])
const auditAction = ref('')
const overview = ref(null)
const total = ref(0)
const PAGE = 50

const confirmTarget = ref(null)
const reason = ref('')
const banDuration = ref('permanent')

const inspect = ref(null)
const inspectTier = ref('free')
const inspectDuration = ref('permanent')
const savingPremium = ref(false)

const maintenance = ref({ enabled: false, message: '' })
const savingMaintenance = ref(false)

// Analytics (Kat. 2)
const metrics = ref([])
const topGuilds = ref([])
const topBy = ref('modules')

// Monitoring (Kat. 1)
const health = ref(null)
const jobs = ref([])
const jobStatus = ref('')
const errors = ref([])
const errSource = ref('')
const errLevel = ref('')
const JOB_STATUSES = ['pending', 'running', 'done', 'failed']

const DURATIONS = [
  { key: 'permanent', sec: 0 },
  { key: '1h', sec: 3600 },
  { key: '24h', sec: 86400 },
  { key: '7d', sec: 604800 },
  { key: '30d', sec: 2592000 }
]
const PREMIUM_DURATIONS = [
  { key: 'permanent', sec: 0 },
  { key: '7d', sec: 604800 },
  { key: '30d', sec: 2592000 }
]

let searchTimer = null

const showToolbar = computed(() => ['users', 'guilds', 'audit', 'jobs', 'errors'].includes(tab.value))
const searchPlaceholder = computed(() => {
  if (tab.value === 'users') return t('admin.searchUsers')
  if (tab.value === 'guilds') return t('admin.searchGuilds')
  return t('admin.auditSearch')
})
const adoptionList = computed(() => {
  if (!overview.value) return []
  return Object.entries(overview.value.module_adoption)
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count)
})
const maxAdoption = computed(() => Math.max(1, ...adoptionList.value.map((m) => m.count)))

// --- Analytics chart data ---
const ADOPTION_COLORS = ['#5865f2', '#22d3ee', '#f472b6', '#facc15', '#34d399']
// Top 5 modules by the latest snapshot's adoption → trend lines.
const adoptionLines = computed(() => {
  const last = metrics.value[metrics.value.length - 1]
  if (!last || !last.adoption) return []
  return Object.entries(last.adoption)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([key], i) => ({ key, label: prettyKey(key), color: ADOPTION_COLORS[i % ADOPTION_COLORS.length] }))
})
// Flatten each snapshot's adoption map onto the point so StatsChart can read p[key].
const adoptionPoints = computed(() => metrics.value.map((m) => ({ ts: m.ts, ...(m.adoption || {}) })))
const serverLines = computed(() => [
  { key: 'guilds', label: t('admin.anLineGuilds'), color: '#5865f2' },
  { key: 'present', label: t('admin.anLinePresent'), color: '#22c55e' }
])
const userLines = computed(() => [{ key: 'users', label: t('admin.anLineUsers'), color: '#22d3ee' }])
const premiumLines = computed(() => [
  { key: 'basic', label: t('premium.tiers.basic.name'), color: '#a78bfa' },
  { key: 'pro', label: t('premium.tiers.pro.name'), color: '#ec4899' }
])

onMounted(() => load())

function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1) }
function isMe(id) { return auth.state.user?.id === id }
function initials(name) { return (name || '?').slice(0, 2).toUpperCase() }
function prettyKey(k) { return k.replace(/-/g, ' ') }
function barWidth(n) { return `${Math.round((n / maxAdoption.value) * 100)}%` }
function fmtDate(ts) { return ts ? new Date(ts * 1000).toLocaleDateString(locale.value) : '' }
function fmtDateTime(s) {
  if (!s) return ''
  // audit created_at is a UTC SQLite timestamp ("YYYY-MM-DD HH:MM:SS")
  const d = new Date(String(s).replace(' ', 'T') + 'Z')
  return isNaN(d.getTime()) ? String(s) : d.toLocaleString(locale.value)
}
function fmtChanges(c) {
  try { return typeof c === 'string' ? c : JSON.stringify(c) } catch { return '' }
}
function fmtDateTimeUnix(sec) {
  if (!sec) return ''
  const d = new Date(Number(sec) * 1000)
  return isNaN(d.getTime()) ? '' : d.toLocaleString(locale.value)
}
function fmtDuration(sec) {
  sec = Math.max(0, Math.floor(Number(sec) || 0))
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
  if (d) return `${d}d ${h}h`
  if (h) return `${h}h ${m}m`
  if (m) return `${m}m ${s}s`
  return `${s}s`
}
function durationToUntil(key, table) {
  const d = table.find((x) => x.key === key)
  return d && d.sec ? Math.floor(Date.now() / 1000) + d.sec : null
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
    if (tab.value === 'overview') {
      const { data } = await api.get('/admin/overview')
      overview.value = data.overview
    } else if (tab.value === 'users') {
      const { data } = await api.get('/admin/users', { params: { search: search.value, limit: PAGE, offset: 0 } })
      users.value = data.users || []
      total.value = data.total || 0
    } else if (tab.value === 'guilds') {
      const { data } = await api.get('/admin/guilds', { params: { search: search.value, limit: PAGE, offset: 0 } })
      guilds.value = data.guilds || []
      total.value = data.total || 0
    } else if (tab.value === 'audit') {
      if (!auditActions.value.length) {
        try { const { data } = await api.get('/admin/audit/actions'); auditActions.value = data.actions || [] } catch (e) { /* non-fatal */ }
      }
      const { data } = await api.get('/admin/audit', { params: { action: auditAction.value, target: search.value, limit: PAGE, offset: 0 } })
      audit.value = data.entries || []
      total.value = data.total || 0
    } else if (tab.value === 'analytics') {
      const [m, tg] = await Promise.all([
        api.get('/admin/metrics', { params: { days: 30 } }),
        api.get('/admin/top-guilds', { params: { by: topBy.value } })
      ])
      metrics.value = m.data.snapshots || []
      topGuilds.value = tg.data.guilds || []
    } else if (tab.value === 'health') {
      const { data } = await api.get('/admin/health')
      health.value = { bot: data.bot, backend: data.backend }
    } else if (tab.value === 'jobs') {
      const { data } = await api.get('/admin/jobs', { params: { status: jobStatus.value, limit: PAGE, offset: 0 } })
      jobs.value = data.jobs || []
      total.value = data.total || 0
    } else if (tab.value === 'errors') {
      const { data } = await api.get('/admin/errors', { params: { source: errSource.value, level: errLevel.value, limit: PAGE, offset: 0 } })
      errors.value = data.entries || []
      total.value = data.total || 0
    } else if (tab.value === 'system') {
      const { data } = await api.get('/admin/maintenance')
      maintenance.value = { enabled: !!data.enabled, message: data.message || '' }
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
    } else if (tab.value === 'guilds') {
      const { data } = await api.get('/admin/guilds', { params: { search: search.value, limit: PAGE, offset: guilds.value.length } })
      guilds.value = guilds.value.concat(data.guilds || [])
      total.value = data.total || total.value
    } else if (tab.value === 'audit') {
      const { data } = await api.get('/admin/audit', { params: { action: auditAction.value, target: search.value, limit: PAGE, offset: audit.value.length } })
      audit.value = audit.value.concat(data.entries || [])
      total.value = data.total || total.value
    } else if (tab.value === 'jobs') {
      const { data } = await api.get('/admin/jobs', { params: { status: jobStatus.value, limit: PAGE, offset: jobs.value.length } })
      jobs.value = jobs.value.concat(data.jobs || [])
      total.value = data.total || total.value
    } else if (tab.value === 'errors') {
      const { data } = await api.get('/admin/errors', { params: { source: errSource.value, level: errLevel.value, limit: PAGE, offset: errors.value.length } })
      errors.value = errors.value.concat(data.entries || [])
      total.value = data.total || total.value
    }
  } catch (err) {
    toast.error(t('admin.loadFailed'))
  } finally {
    loadingMore.value = false
  }
}

async function setTopBy(by) {
  if (topBy.value === by) return
  topBy.value = by
  try {
    const { data } = await api.get('/admin/top-guilds', { params: { by } })
    topGuilds.value = data.guilds || []
  } catch (err) {
    toast.error(t('admin.loadFailed'))
  }
}

async function retryJob(j) {
  busyId.value = j.id
  try {
    await api.post(`/admin/jobs/${j.id}/retry`)
    j.status = 'pending'
    j.message = null
    toast.success(t('admin.jobsRetried'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.loadFailed'))
  } finally {
    busyId.value = null
  }
}

async function clearErrors() {
  try {
    await api.delete('/admin/errors')
    errors.value = []
    total.value = 0
    toast.success(t('admin.errCleared'))
  } catch (err) {
    toast.error(t('admin.loadFailed'))
  }
}

function askBlockUser(u) { reason.value = ''; banDuration.value = 'permanent'; confirmTarget.value = { kind: 'user', id: u.discord_id, name: u.username } }
function askBlockGuild(g) { reason.value = ''; banDuration.value = 'permanent'; confirmTarget.value = { kind: 'guild', id: g.id, name: g.guild_name } }

async function confirmBlock() {
  const target = confirmTarget.value
  if (!target) return
  busyId.value = target.id
  const until = durationToUntil(banDuration.value, DURATIONS)
  try {
    if (target.kind === 'user') {
      await api.post(`/admin/users/${target.id}/block`, { blocked: true, reason: reason.value, until })
      const u = users.value.find((x) => x.discord_id === target.id)
      if (u) { u.blocked = true; u.blocked_reason = reason.value || null; u.blocked_until = until }
      toast.success(t('admin.userBlocked'))
    } else {
      await api.post(`/admin/guilds/${target.id}/block`, { blocked: true, reason: reason.value, until })
      const g = guilds.value.find((x) => x.id === target.id)
      if (g) { g.blocked = true; g.blocked_reason = reason.value || null; g.blocked_until = until }
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
    u.blocked = false; u.blocked_reason = null; u.blocked_until = null
    toast.success(t('admin.userUnblocked'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally { busyId.value = null }
}

async function unblockGuild(g) {
  busyId.value = g.id
  try {
    await api.post(`/admin/guilds/${g.id}/block`, { blocked: false })
    g.blocked = false; g.blocked_reason = null; g.blocked_until = null
    toast.success(t('admin.guildUnblocked'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally { busyId.value = null }
}

async function setPremium(g, tier) {
  const prev = g.premium_tier || 'free'
  if (tier === prev) return
  busyId.value = g.id
  try {
    await api.post(`/admin/guilds/${g.id}/premium`, { tier })
    g.premium_tier = tier
    g.premium_source = tier === 'free' ? null : 'manual'
    g.premium_until = null
    toast.success(t('admin.tierUpdated', { tier: t(`premium.tiers.${tier}.name`) }))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally { busyId.value = null }
}

async function inspectGuild(g) {
  inspect.value = null
  try {
    const { data } = await api.get(`/admin/guilds/${g.id}/inspect`)
    inspect.value = data.inspect
    inspectTier.value = data.inspect.premium_tier || 'free'
    inspectDuration.value = 'permanent'
  } catch (err) {
    toast.error(t('admin.loadFailed'))
  }
}

async function applyInspectPremium() {
  if (!inspect.value) return
  savingPremium.value = true
  const until = inspectTier.value === 'free' ? null : durationToUntil(inspectDuration.value, PREMIUM_DURATIONS)
  try {
    await api.post(`/admin/guilds/${inspect.value.id}/premium`, { tier: inspectTier.value, until })
    inspect.value.premium_tier = inspectTier.value
    inspect.value.premium_effective = inspectTier.value
    inspect.value.premium_source = inspectTier.value === 'free' ? null : 'manual'
    inspect.value.premium_until = until
    const g = guilds.value.find((x) => x.id === inspect.value.id)
    if (g) { g.premium_tier = inspectTier.value; g.premium_source = inspectTier.value === 'free' ? null : 'manual'; g.premium_until = until }
    toast.success(t('admin.premiumApplied'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally { savingPremium.value = false }
}

async function saveMaintenance() {
  savingMaintenance.value = true
  try {
    await api.put('/admin/maintenance', { enabled: maintenance.value.enabled, message: maintenance.value.message })
    toast.success(t('admin.sysSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('admin.actionFailed'))
  } finally { savingMaintenance.value = false }
}

async function exportCsv(kind) {
  try {
    const { data } = await api.get(`/admin/${kind}/export`, { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = `projectx-${kind}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    toast.error(t('admin.exportFailed'))
  }
}

function goBack() { router.push('/dashboard') }
</script>

<style scoped>
.admin {
  padding: var(--space-10) var(--space-6) var(--space-16);
  min-height: calc(100vh - var(--nav-height));
  animation: fade-in 400ms var(--ease-out-expo) both;
}
.admin__inner { max-width: 880px; margin: 0 auto; }
.admin__head { position: relative; margin-bottom: var(--space-8); min-height: 64px; }
.admin__head-action { position: absolute; top: 0; left: 0; }
.admin__heading { text-align: center; max-width: 640px; margin: 0 auto; }
.admin__eyebrow { font-size: 0.75rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-primary); margin-bottom: var(--space-2); }
.admin__title { font-size: clamp(1.8rem, 3vw, 2.4rem); letter-spacing: -0.025em; margin-bottom: var(--space-2); }
.admin__sub { color: var(--color-text-muted); margin: 0 auto; max-width: 520px; }

@media (max-width: 640px) {
  .admin__head { display: flex; flex-direction: column; align-items: center; gap: var(--space-4); }
  .admin__head-action { position: static; }
}

.admin__tabs { display: inline-flex; gap: 4px; padding: 4px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-full); margin-bottom: var(--space-5); flex-wrap: wrap; }
.admin__tab { padding: 0.5rem 1.1rem; border-radius: var(--radius-full); font-weight: 600; font-size: 0.88rem; color: var(--color-text-soft); cursor: pointer; transition: background var(--transition), color var(--transition); }
.admin__tab.is-active { background: var(--color-primary); color: #fff; }

.admin__toolbar { margin-bottom: var(--space-5); display: flex; gap: var(--space-3); align-items: center; flex-wrap: wrap; }
.search { position: relative; max-width: 360px; flex: 1; min-width: 200px; }
.search__icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--color-text-soft); }
.search__input { width: 100%; padding: 0.65rem 0.9rem 0.65rem 2.3rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); color: var(--color-text); font-size: 0.9rem; }
.search__input:focus { outline: none; border-color: var(--color-primary); }
.filter__select { padding: 0.65rem 0.9rem; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); color: var(--color-text); font-size: 0.85rem; }

/* Overview cards */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-5); }
.card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-4); }
.card__label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--color-text-soft); font-weight: 700; }
.card__value { font-size: 2rem; font-weight: 800; letter-spacing: -0.02em; margin: 4px 0; }
.card__meta { font-size: 0.78rem; color: var(--color-text-muted); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.linkbtn { color: var(--color-primary); font-weight: 600; cursor: pointer; }

.pill { font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.55rem; border-radius: var(--radius-full); background: var(--color-surface-2); color: var(--color-text-soft); display: inline-flex; align-items: center; gap: 4px; }
.pill--basic { background: rgba(99, 102, 241, 0.18); color: #a5b4fc; }
.pill--pro { background: rgba(167, 139, 250, 0.2); color: #c4b5fd; }

.panel { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-5); margin-bottom: var(--space-4); }
.panel--form { max-width: 560px; }
.panel__title { font-size: 1rem; margin-bottom: var(--space-3); }
.panel__desc { color: var(--color-text-muted); font-size: 0.85rem; margin-bottom: var(--space-4); line-height: 1.5; }
.panel__empty { color: var(--color-text-muted); font-size: 0.85rem; }
.panel__actions { margin-top: var(--space-4); display: flex; justify-content: flex-end; }

.mini-rows { display: flex; flex-direction: column; gap: var(--space-2); }
.mini-row { display: flex; align-items: center; gap: var(--space-3); }
.mini-row__name { font-weight: 600; font-size: 0.88rem; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mini-row__time { font-size: 0.76rem; color: var(--color-text-soft); }

.adoption { display: flex; flex-direction: column; gap: 6px; }
.adoption__row { display: flex; align-items: center; gap: var(--space-3); }
.adoption__key { width: 130px; font-size: 0.78rem; color: var(--color-text-soft); text-transform: capitalize; flex-shrink: 0; }
.adoption__bar { flex: 1; height: 8px; background: var(--color-surface-2); border-radius: var(--radius-full); overflow: hidden; }
.adoption__fill { height: 100%; background: var(--gradient-brand, var(--color-primary)); border-radius: var(--radius-full); }
.adoption__count { width: 36px; text-align: right; font-size: 0.78rem; font-weight: 700; }

.toggle-row { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4); font-weight: 600; font-size: 0.9rem; }

.rows { display: flex; flex-direction: column; gap: var(--space-2); }
.row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); padding: var(--space-4); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); transition: border-color var(--transition); }
.row.is-blocked { border-color: var(--color-danger); background: var(--color-danger-soft); }
.row__main { display: flex; align-items: center; gap: var(--space-3); min-width: 0; }
.row__avatar { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; flex-shrink: 0; background: var(--gradient-brand); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem; }
.row__text { min-width: 0; }
.row__name { font-weight: 600; font-size: 0.95rem; display: flex; align-items: center; gap: var(--space-2); }
.row__tag { font-size: 0.6rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; padding: 0.15rem 0.45rem; border-radius: var(--radius-full); background: var(--color-primary-soft); color: var(--color-primary); }
.row__sub { font-size: 0.78rem; color: var(--color-text-soft); font-family: var(--font-mono); display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.row__reason { font-size: 0.78rem; color: var(--color-danger); margin-top: 3px; }
.row__until { font-size: 0.76rem; color: var(--color-text-soft); margin-top: 3px; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot--on { background: var(--color-success, #22c55e); }
.dot--off { background: var(--color-text-soft); }
.row__right { display: flex; align-items: center; gap: var(--space-3); flex-shrink: 0; }
.status { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 0.25rem 0.6rem; border-radius: var(--radius-full); }
.status--active { background: var(--color-surface-2); color: var(--color-text-soft); }
.status--blocked { background: var(--color-danger); color: #fff; }
.job-status { font-size: 0.66rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; padding: 0.12rem 0.45rem; border-radius: var(--radius-full); }
.job-status--pending { background: var(--color-surface-2); color: var(--color-text-soft); }
.job-status--running { background: rgba(245, 158, 11, 0.18); color: #fbbf24; }
.job-status--done { background: rgba(34, 197, 94, 0.18); color: #4ade80; }
.job-status--failed { background: rgba(239, 68, 68, 0.18); color: #f87171; }
.charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: var(--space-4); margin-bottom: var(--space-5); }
.panel__head-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); flex-wrap: wrap; }
.seg { display: inline-flex; border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; }
.seg__btn { padding: 0.35rem 0.8rem; font-size: 0.8rem; font-weight: 600; color: var(--color-text-soft); background: var(--color-bg-elevated); }
.seg__btn.is-active { background: var(--color-primary-soft); color: var(--color-text); }
.mini-row__rank { width: 1.4rem; text-align: center; font-weight: 700; color: var(--color-text-soft); font-size: 0.85rem; flex-shrink: 0; }
.tier-select { padding: 0.4rem 0.6rem; border-radius: var(--radius-md); border: 1px solid var(--color-border); background: var(--color-bg-elevated); color: var(--color-text); font-size: 0.8rem; font-weight: 600; cursor: pointer; }
.tier-select:focus { outline: none; border-color: var(--color-primary); }
.tier-select--basic { border-color: rgba(99, 102, 241, 0.5); color: #a5b4fc; }
.tier-select--pro { border-color: rgba(167, 139, 250, 0.6); color: #c4b5fd; }

/* Audit */
.audit-row { padding: var(--space-3) var(--space-4); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.audit-row__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.audit-row__action { font-weight: 700; font-size: 0.85rem; font-family: var(--font-mono); color: var(--color-primary); }
.audit-row__time { font-size: 0.74rem; color: var(--color-text-soft); }
.audit-row__meta { font-size: 0.78rem; color: var(--color-text-muted); margin-top: 4px; }
.audit-row__changes { font-size: 0.72rem; font-family: var(--font-mono); color: var(--color-text-soft); background: var(--color-bg); border-radius: var(--radius-sm); padding: 6px 8px; margin-top: 6px; overflow-x: auto; white-space: pre-wrap; word-break: break-word; }

.admin__more { display: flex; justify-content: center; margin-top: var(--space-5); }
.empty { text-align: center; padding: var(--space-12) var(--space-6); color: var(--color-text-muted); }

/* Modal */
.modal-overlay { position: fixed; inset: 0; z-index: 8000; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: var(--space-4); }
.modal { width: 100%; max-width: 440px; background: var(--color-surface); border: 1px solid var(--color-border-strong); border-radius: var(--radius-xl); box-shadow: var(--shadow-xl); padding: var(--space-6); max-height: 90vh; overflow-y: auto; }
.modal--wide { max-width: 560px; }
.modal__title { font-size: 1.2rem; margin-bottom: var(--space-3); }
.modal__body { color: var(--color-text-muted); line-height: 1.55; margin-bottom: var(--space-4); }
.modal__label { display: block; font-size: 0.8rem; font-weight: 600; color: var(--color-text-soft); margin-bottom: var(--space-2); margin-top: var(--space-2); }
.modal__input { width: 100%; padding: 0.65rem 0.9rem; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-md); color: var(--color-text); font-size: 0.9rem; margin-bottom: var(--space-3); }
.modal__input--inline { width: auto; margin-bottom: 0; }
.modal__input:focus { outline: none; border-color: var(--color-primary); }
.modal__actions { display: flex; justify-content: flex-end; gap: var(--space-3); margin-top: var(--space-4); }

.insp-head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
.insp-facts { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-4); }
.insp-sub { font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-soft); margin: var(--space-3) 0 var(--space-2); }
.insp-modules { display: flex; flex-wrap: wrap; gap: 6px; }
.insp-mod { font-size: 0.74rem; padding: 0.2rem 0.55rem; border-radius: var(--radius-full); background: var(--color-surface-2); color: var(--color-text-soft); display: inline-flex; align-items: center; gap: 5px; text-transform: capitalize; }
.insp-mod__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-soft); }
.insp-mod--on { color: var(--color-text); }
.insp-mod--on .insp-mod__dot { background: var(--color-success, #22c55e); }
.insp-premium { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }

.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active, .modal-leave-active { transition: opacity var(--transition); }
</style>
