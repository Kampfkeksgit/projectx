<template>
  <div class="config">
    <header class="config__head">
      <div class="config__head-text">
        <div class="config__eyebrow">{{ t('backup.eyebrow') }}</div>
        <h1 class="config__title">{{ t('backup.title') }}</h1>
        <p class="config__sub">{{ t('backup.sub') }}</p>
      </div>
      <div class="config__head-actions">
        <AppButton variant="ghost" :disabled="anyJobActive" @click="openTemplate">
          <template #icon-left>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </template>
          {{ t('backup.templateButton') }}
        </AppButton>
        <AppButton variant="gradient" :loading="creating" :disabled="snapshotJobActive" @click="createSnapshot">
          <template #icon-left>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          </template>
          {{ t('backup.createButton') }}
        </AppButton>
      </div>
    </header>

    <div class="config__form">
      <transition name="dirty-bar">
        <div v-if="activeJob" class="form-card job-banner">
          <span class="job-banner__spinner" aria-hidden="true"></span>
          <span class="job-banner__text">
            {{ activeJob.type === 'restore' ? t('backup.jobRunningRestore') : t('backup.jobRunningSnapshot') }}
          </span>
        </div>
      </transition>

      <div v-if="loading && snapshots.length === 0" class="form-card state">{{ t('common.loading') }}</div>
      <div v-else-if="!loading && snapshots.length === 0" class="form-card empty">
        <div class="empty__title">{{ t('backup.emptyTitle') }}</div>
        <div class="empty__body">{{ t('backup.emptyBody') }}</div>
      </div>

      <div v-for="snap in snapshots" :key="snap.id" class="form-card snap-row">
        <div class="snap-row__main">
          <div class="snap-row__icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
          </div>
          <div class="snap-row__text">
            <div class="snap-row__name">{{ snap.name || snap.guild_name || t('backup.title') }}</div>
            <div class="snap-row__meta">
              <span>{{ fmtDate(snap.created_at) }}</span>
              <span class="snap-row__dot">·</span>
              <span>{{ t('backup.channelsRoles', { channels: snap.channels_count, roles: snap.roles_count }) }}</span>
            </div>
          </div>
        </div>
        <div class="snap-row__actions">
          <AppButton variant="ghost" @click="openDetail(snap)">
            <template #icon-left>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg>
            </template>
            {{ t('backup.view') }}
          </AppButton>
          <AppButton variant="primary" :loading="restoringIds.has(snap.id)" :disabled="anyJobActive" @click="openRestore(snap)">
            {{ t('backup.restore') }}
          </AppButton>
          <AppButton v-if="auth.user?.is_owner" variant="ghost" @click="openPublish(snap)">
            <template #icon-left>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
            </template>
            {{ t('backup.publish') }}
          </AppButton>
          <AppButton variant="danger" :loading="deletingIds.has(snap.id)" :disabled="anyJobActive" @click="openDelete(snap)">
            {{ t('backup.delete') }}
          </AppButton>
        </div>
      </div>
    </div>

    <!-- Detail / preview modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="detailTarget" class="modal-overlay" @click.self="closeDetail">
          <div class="modal modal--wide">
            <h3 class="modal__title">{{ t('backup.detailsTitle') }}</h3>
            <p class="modal__body detail-name">{{ detailTarget.name || detailTarget.guild_name || t('backup.title') }} · {{ fmtDate(detailTarget.created_at) }}</p>

            <div v-if="detailLoading" class="detail-state">{{ t('common.loading') }}</div>
            <div v-else-if="detailError" class="detail-state detail-state--err">{{ t('backup.detailsError') }}</div>

            <div v-else-if="detailData" class="detail-body">
              <!-- Server -->
              <section class="detail-sec">
                <div class="detail-sec__head">{{ t('backup.detailsServer') }}</div>
                <div class="detail-server">
                  <img v-if="detailData.server && detailData.server.icon_url" :src="detailData.server.icon_url" class="detail-server__icon" alt="" />
                  <div v-else class="detail-server__icon detail-server__icon--ph">{{ serverInitials }}</div>
                  <div>
                    <div class="detail-server__name">{{ detailData.server?.name || detailTarget.guild_name || '—' }}</div>
                    <div class="detail-server__meta">{{ t('backup.detailsVerification') }}: {{ detailData.server?.verification_level ?? 0 }}</div>
                  </div>
                </div>
              </section>

              <!-- Channels -->
              <section class="detail-sec">
                <div class="detail-sec__head">{{ t('backup.detailsChannels') }} · {{ (detailData.channels || []).length }}</div>
                <div class="detail-tree">
                  <template v-for="cat in detailTree.categories" :key="cat.id">
                    <div class="detail-cat">{{ chanGlyph('category') }} {{ cat.name }}</div>
                    <div v-for="ch in cat.children" :key="ch.id" class="detail-chan detail-chan--nested">{{ chanGlyph(ch.type) }} {{ ch.name }}</div>
                  </template>
                  <div v-for="ch in detailTree.orphans" :key="ch.id" class="detail-chan">{{ chanGlyph(ch.type) }} {{ ch.name }}</div>
                </div>
              </section>

              <!-- Roles -->
              <section class="detail-sec">
                <div class="detail-sec__head">{{ t('backup.detailsRoles') }} · {{ (detailData.roles || []).length }}</div>
                <div class="detail-roles">
                  <span v-for="role in detailRoles" :key="role.id" class="detail-role">
                    <span class="detail-role__dot" :style="{ background: roleColor(role.color) }"></span>
                    {{ role.name }}
                  </span>
                </div>
              </section>
            </div>

            <div class="modal__actions">
              <AppButton variant="ghost" @click="closeDetail">{{ t('backup.close') }}</AppButton>
              <AppButton variant="primary" :disabled="anyJobActive || detailLoading" @click="restoreFromDetail">{{ t('backup.restore') }}</AppButton>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Restore modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="restoreTarget" class="modal-overlay" @click.self="restoreTarget = null">
          <div class="modal">
            <h3 class="modal__title">{{ t('backup.restoreTitle') }}</h3>
            <p class="modal__body">{{ t('backup.restoreWarn') }}</p>

            <div class="mode-cards">
              <button
                type="button"
                class="mode-card"
                :class="{ 'is-active': restoreMode === 'missing' }"
                @click="restoreMode = 'missing'"
              >
                <span class="mode-card__radio"></span>
                <span class="mode-card__text">
                  <span class="mode-card__title">{{ t('backup.modeMissing') }}</span>
                  <span class="mode-card__hint">{{ t('backup.modeMissingHint') }}</span>
                </span>
              </button>
              <button
                type="button"
                class="mode-card mode-card--danger"
                :class="{ 'is-active': restoreMode === 'mirror' }"
                @click="restoreMode = 'mirror'"
              >
                <span class="mode-card__radio"></span>
                <span class="mode-card__text">
                  <span class="mode-card__title">{{ t('backup.modeMirror') }}</span>
                  <span class="mode-card__hint">{{ t('backup.modeMirrorHint') }}</span>
                </span>
              </button>
            </div>

            <div class="parts-group">
              <div class="parts-group__label">{{ t('backup.partsLabel') }}</div>
              <label class="parts-check"><input type="checkbox" v-model="parts.roles" /><span>{{ t('backup.partRoles') }}</span></label>
              <label class="parts-check"><input type="checkbox" v-model="parts.channels" /><span>{{ t('backup.partChannels') }}</span></label>
              <label class="parts-check"><input type="checkbox" v-model="parts.server_icon" /><span>{{ t('backup.partIcon') }}</span></label>
              <label class="parts-check"><input type="checkbox" v-model="parts.server_name" /><span>{{ t('backup.partName') }}</span></label>
            </div>

            <div class="modal__actions">
              <AppButton variant="ghost" @click="restoreTarget = null">{{ t('backup.cancel') }}</AppButton>
              <AppButton :variant="restoreMode === 'mirror' ? 'danger' : 'primary'" :disabled="noPartsSelected" :loading="restoreSubmitting" @click="confirmRestore">
                {{ t('backup.restore') }}
              </AppButton>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Delete modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="deleteTarget" class="modal-overlay" @click.self="deleteTarget = null">
          <div class="modal">
            <h3 class="modal__title">{{ t('backup.delete') }}</h3>
            <p class="modal__body">{{ t('backup.deleteConfirm') }}</p>
            <div class="modal__actions">
              <AppButton variant="ghost" @click="deleteTarget = null">{{ t('backup.cancel') }}</AppButton>
              <AppButton variant="danger" :loading="deleteSubmitting" @click="confirmDelete">{{ t('backup.delete') }}</AppButton>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Publish to marketplace modal (owner only) -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="publishTarget" class="modal-overlay" @click.self="publishTarget = null">
          <div class="modal">
            <h3 class="modal__title">{{ t('backup.publishTitle') }}</h3>
            <p class="modal__body">{{ t('backup.publishIntro') }}</p>

            <div class="tmpl-body">
              <label class="tmpl-field">
                <span class="tmpl-field__label">{{ t('backup.publishName') }}</span>
                <input type="text" v-model="publishName" class="tmpl-input" />
              </label>
              <label class="tmpl-field">
                <span class="tmpl-field__label">{{ t('backup.publishDescription') }}</span>
                <textarea v-model="publishDescription" class="tmpl-textarea" rows="3"></textarea>
              </label>
              <label class="tmpl-field">
                <span class="tmpl-field__label">{{ t('backup.publishCategory') }}</span>
                <input type="text" v-model="publishCategory" class="tmpl-input" />
              </label>
            </div>

            <div class="modal__actions">
              <AppButton variant="ghost" @click="publishTarget = null">{{ t('backup.cancel') }}</AppButton>
              <AppButton variant="primary" :loading="publishSubmitting" @click="confirmPublish">{{ t('backup.publishSubmit') }}</AppButton>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Apply template (from another server) modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="templateOpen" class="modal-overlay" @click.self="closeTemplate">
          <div class="modal modal--wide">
            <h3 class="modal__title">{{ t('backup.templateTitle') }}</h3>
            <p class="modal__body">{{ t('backup.templateWarn') }}</p>

            <div class="tmpl-tabs" role="tablist">
              <button type="button" class="tmpl-tab" :class="{ 'is-active': templateTab === 'own' }" @click="templateTab = 'own'">{{ t('backup.ownServersTab') }}</button>
              <button type="button" class="tmpl-tab" :class="{ 'is-active': templateTab === 'market' }" @click="templateTab = 'market'">{{ t('backup.marketplaceTab') }}</button>
            </div>

            <!-- My servers tab -->
            <template v-if="templateTab === 'own'">
              <div v-if="templateLoading" class="detail-state">{{ t('common.loading') }}</div>
              <div v-else-if="templateSources.length === 0" class="detail-state">{{ t('backup.templateEmpty') }}</div>

              <div v-else class="tmpl-body">
                <label class="tmpl-field">
                  <span class="tmpl-field__label">{{ t('backup.templateSourceLabel') }}</span>
                  <select v-model="templateSourceId" class="tmpl-select" @change="templateBackupId = ''">
                    <option value="" disabled>{{ t('backup.templateChooseServer') }}</option>
                    <option v-for="s in templateSources" :key="s.guild_id" :value="s.guild_id">{{ s.guild_name || s.guild_id }}</option>
                  </select>
                </label>

                <label v-if="templateSourceId" class="tmpl-field">
                  <span class="tmpl-field__label">{{ t('backup.templateSnapshotLabel') }}</span>
                  <select v-model="templateBackupId" class="tmpl-select">
                    <option value="" disabled>{{ t('backup.templateChooseSnapshot') }}</option>
                    <option v-for="snap in templateSnapshots" :key="snap.id" :value="snap.id">
                      {{ snap.name || fmtDate(snap.created_at) }} — {{ t('backup.channelsRoles', { channels: snap.channels_count, roles: snap.roles_count }) }}
                    </option>
                  </select>
                </label>
              </div>
            </template>

            <!-- Marketplace tab -->
            <template v-else>
              <div v-if="marketplaceTemplates.length === 0" class="detail-state">{{ t('backup.marketplaceEmpty') }}</div>
              <div v-else class="tmpl-body">
                <label class="tmpl-field">
                  <span class="tmpl-field__label">{{ t('backup.marketplaceTab') }}</span>
                  <select v-model="marketplaceId" class="tmpl-select">
                    <option value="" disabled>{{ t('backup.marketplaceChoose') }}</option>
                    <option v-for="m in marketplaceTemplates" :key="m.id" :value="m.id">
                      {{ m.name }} — {{ t('backup.channelsRoles', { channels: m.channels_count, roles: m.roles_count }) }} · {{ t('backup.marketplaceUses', { count: m.uses }) }}
                    </option>
                  </select>
                </label>

                <div v-if="selectedMarketplace" class="tmpl-market-info">
                  <p v-if="selectedMarketplace.description" class="tmpl-market-desc">{{ selectedMarketplace.description }}</p>
                  <button v-if="auth.user?.is_owner" type="button" class="tmpl-remove" :disabled="removingTemplate" @click="removeMarketplaceTemplate">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    {{ t('backup.removeTemplate') }}
                  </button>
                </div>
              </div>
            </template>

            <!-- Shared mode + parts (both tabs) -->
            <div v-if="(templateTab === 'own' && templateBackupId) || (templateTab === 'market' && marketplaceId)" class="tmpl-shared">
              <div class="mode-cards">
                <button type="button" class="mode-card" :class="{ 'is-active': templateMode === 'missing' }" @click="templateMode = 'missing'">
                  <span class="mode-card__radio"></span>
                  <span class="mode-card__text">
                    <span class="mode-card__title">{{ t('backup.modeMissing') }}</span>
                    <span class="mode-card__hint">{{ t('backup.modeMissingHint') }}</span>
                  </span>
                </button>
                <button type="button" class="mode-card mode-card--danger" :class="{ 'is-active': templateMode === 'mirror' }" @click="templateMode = 'mirror'">
                  <span class="mode-card__radio"></span>
                  <span class="mode-card__text">
                    <span class="mode-card__title">{{ t('backup.modeMirror') }}</span>
                    <span class="mode-card__hint">{{ t('backup.modeMirrorHint') }}</span>
                  </span>
                </button>
              </div>

              <div class="parts-group">
                <div class="parts-group__label">{{ t('backup.partsLabel') }}</div>
                <label class="parts-check"><input type="checkbox" v-model="parts.roles" /><span>{{ t('backup.partRoles') }}</span></label>
                <label class="parts-check"><input type="checkbox" v-model="parts.channels" /><span>{{ t('backup.partChannels') }}</span></label>
                <label class="parts-check"><input type="checkbox" v-model="parts.server_icon" /><span>{{ t('backup.partIcon') }}</span></label>
                <label class="parts-check"><input type="checkbox" v-model="parts.server_name" /><span>{{ t('backup.partName') }}</span></label>
              </div>
            </div>

            <div class="modal__actions">
              <AppButton variant="ghost" @click="closeTemplate">{{ t('backup.cancel') }}</AppButton>
              <AppButton
                v-if="templateTab === 'own'"
                :variant="templateMode === 'mirror' ? 'danger' : 'primary'"
                :disabled="!templateBackupId || anyJobActive || noPartsSelected"
                :loading="templateSubmitting"
                @click="applyTemplate"
              >{{ t('backup.templateApply') }}</AppButton>
              <AppButton
                v-else
                :variant="templateMode === 'mirror' ? 'danger' : 'primary'"
                :disabled="!marketplaceId || anyJobActive || noPartsSelected"
                :loading="templateSubmitting"
                @click="applyMarketplace"
              >{{ t('backup.marketplaceApply') }}</AppButton>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { useAuth } from '../stores/auth.js'

const route = useRoute()
const toast = useToast()
const { t, locale } = useI18n()
const auth = useAuth().state
const guildId = computed(() => route.params.guild_id)

const snapshots = ref([])
const jobs = ref([])
const loading = ref(false)
const creating = ref(false)

const restoringIds = reactive(new Set())
const deletingIds = reactive(new Set())

const detailTarget = ref(null)
const detailData = ref(null)
const detailLoading = ref(false)
const detailError = ref(false)

const restoreTarget = ref(null)
const restoreMode = ref('missing')
const restoreSubmitting = ref(false)

// Which pieces to apply (shared by restore + apply-template; only one modal open
// at a time). All on by default = full restore.
const parts = reactive({ roles: true, channels: true, server_name: true, server_icon: true })
const noPartsSelected = computed(() => !parts.roles && !parts.channels && !parts.server_name && !parts.server_icon)
function resetParts() {
  parts.roles = true
  parts.channels = true
  parts.server_name = true
  parts.server_icon = true
}

const deleteTarget = ref(null)
const deleteSubmitting = ref(false)

const templateOpen = ref(false)
const templateLoading = ref(false)
const templateSources = ref([])
const templateSourceId = ref('')
const templateBackupId = ref('')
const templateMode = ref('missing')
const templateSubmitting = ref(false)

const templateSnapshots = computed(() =>
  templateSources.value.find(s => s.guild_id === templateSourceId.value)?.snapshots || []
)

// Apply-template modal tabs: 'own' (other servers) | 'market' (public templates)
const templateTab = ref('own')
const marketplaceTemplates = ref([])
const marketplaceId = ref('')
const selectedMarketplace = computed(() =>
  marketplaceTemplates.value.find(m => String(m.id) === String(marketplaceId.value)) || null
)
const removingTemplate = ref(false)

// Publish-to-marketplace modal
const publishTarget = ref(null)
const publishName = ref('')
const publishDescription = ref('')
const publishCategory = ref('')
const publishSubmitting = ref(false)

let pollTimer = null

const ACTIVE = ['pending', 'running']

const activeJob = computed(() => jobs.value.find(j => ACTIVE.includes(j.status)) || null)
const anyJobActive = computed(() => !!activeJob.value)
const snapshotJobActive = computed(() => jobs.value.some(j => j.type === 'snapshot' && ACTIVE.includes(j.status)))

function fmtDate(ts) {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleString(locale.value)
}

// ---- Snapshot preview ----
const CHAN_GLYPHS = { category: '▸', text: '#', voice: '🔊', announcement: '📣', stage: '🎤', forum: '🗂', thread: '#' }
function chanGlyph(type) { return CHAN_GLYPHS[type] || '#' }

function roleColor(color) {
  const n = Number(color) || 0
  if (!n) return '#99aab5'
  return '#' + n.toString(16).padStart(6, '0')
}

const serverInitials = computed(() => {
  const name = detailData.value?.server?.name || detailTarget.value?.guild_name || ''
  return name.slice(0, 2).toUpperCase() || '··'
})

const detailRoles = computed(() => {
  const roles = detailData.value?.roles
  if (!Array.isArray(roles)) return []
  return [...roles].sort((a, b) => (b.position || 0) - (a.position || 0))
})

// Group channels into categories (sorted by position) with their children + uncategorized.
const detailTree = computed(() => {
  const chans = detailData.value?.channels
  if (!Array.isArray(chans)) return { categories: [], orphans: [] }
  const byPos = (a, b) => (a.position || 0) - (b.position || 0)
  const cats = chans.filter(c => c.type === 'category').sort(byPos)
  const catMap = new Map(cats.map(c => [String(c.id), { ...c, children: [] }]))
  const orphans = []
  for (const c of chans.filter(c => c.type !== 'category').sort(byPos)) {
    const pid = c.parent_id != null ? String(c.parent_id) : null
    if (pid && catMap.has(pid)) catMap.get(pid).children.push(c)
    else orphans.push(c)
  }
  return { categories: cats.map(c => catMap.get(String(c.id))), orphans }
})

async function openDetail(snap) {
  detailTarget.value = snap
  detailData.value = null
  detailError.value = false
  detailLoading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/backups/${snap.id}`)
    if (data?.success && data.snapshot) detailData.value = data.snapshot.data || {}
    else detailError.value = true
  } catch (err) {
    detailError.value = true
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailTarget.value = null
  detailData.value = null
}

function restoreFromDetail() {
  const snap = detailTarget.value
  closeDetail()
  if (snap) openRestore(snap)
}

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/backups`)
    snapshots.value = (data?.success && Array.isArray(data.snapshots)) ? data.snapshots : []
    jobs.value = (data?.success && Array.isArray(data.jobs)) ? data.jobs : []
    syncPolling()
  } catch (err) {
    snapshots.value = []
    jobs.value = []
    toast.error(err.response?.data?.error || t('backup.loadError'))
  } finally {
    loading.value = false
  }
}

// Compare two job snapshots to surface success/error toasts on completion.
function notifyFinished(prevJobs, nextJobs) {
  for (const job of nextJobs) {
    const prev = prevJobs.find(p => p.id === job.id)
    if (!prev) continue
    if (ACTIVE.includes(prev.status) && (job.status === 'done' || job.status === 'failed')) {
      const ok = job.status === 'done'
      const key = job.type === 'restore'
        ? (ok ? 'backup.restoreDone' : 'backup.restoreFailed')
        : (ok ? 'backup.snapshotCreated' : 'backup.snapshotFailed')
      const msg = job.message || t(key)
      if (ok) toast.success(msg)
      else toast.error(msg)
    }
  }
}

async function poll() {
  if (!guildId.value) return
  const prevJobs = jobs.value
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/backups`)
    if (data?.success) {
      const nextJobs = Array.isArray(data.jobs) ? data.jobs : []
      notifyFinished(prevJobs, nextJobs)
      snapshots.value = Array.isArray(data.snapshots) ? data.snapshots : []
      jobs.value = nextJobs
    }
  } catch (err) {
    // transient — keep polling
  } finally {
    syncPolling()
  }
}

function syncPolling() {
  if (anyJobActive.value) {
    if (!pollTimer) pollTimer = setInterval(poll, 4000)
  } else {
    stopPolling()
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(load)
watch(guildId, () => { stopPolling(); load() })
onBeforeUnmount(stopPolling)

async function createSnapshot() {
  if (!guildId.value || snapshotJobActive.value) return
  creating.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/backups`)
    if (data?.success && data.job) jobs.value = [data.job, ...jobs.value]
    toast.success(t('backup.created'))
    syncPolling()
  } catch (err) {
    toast.error(err.response?.data?.error || t('backup.loadError'))
  } finally {
    creating.value = false
  }
}

function openRestore(snap) {
  restoreMode.value = 'missing'
  resetParts()
  restoreTarget.value = snap
}

async function confirmRestore() {
  const snap = restoreTarget.value
  if (!snap || noPartsSelected.value) return
  restoreSubmitting.value = true
  restoringIds.add(snap.id)
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/backups/${snap.id}/restore`, { mode: restoreMode.value, parts: { ...parts } })
    if (data?.success && data.job) jobs.value = [data.job, ...jobs.value]
    restoreTarget.value = null
    toast.success(t('backup.restoreQueued'))
    syncPolling()
  } catch (err) {
    toast.error(err.response?.data?.error || t('backup.restoreError'))
  } finally {
    restoreSubmitting.value = false
    restoringIds.delete(snap.id)
  }
}

// ---- Apply template from another server ----
async function openTemplate() {
  templateOpen.value = true
  templateTab.value = 'own'
  templateSources.value = []
  templateSourceId.value = ''
  templateBackupId.value = ''
  templateMode.value = 'missing'
  marketplaceTemplates.value = []
  marketplaceId.value = ''
  resetParts()
  templateLoading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/backups/templates`)
    templateSources.value = (data?.success && Array.isArray(data.sources)) ? data.sources : []
  } catch (err) {
    templateSources.value = []
    toast.error(err.response?.data?.error || t('backup.templateError'))
  } finally {
    templateLoading.value = false
  }
  loadMarketplace()
}

function closeTemplate() {
  templateOpen.value = false
}

async function loadMarketplace() {
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/backups/marketplace`)
    marketplaceTemplates.value = (data?.success && Array.isArray(data.templates)) ? data.templates : []
  } catch (err) {
    marketplaceTemplates.value = []
  }
}

async function applyMarketplace() {
  if (!marketplaceId.value || noPartsSelected.value) return
  templateSubmitting.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/backups/apply-marketplace`, {
      template_id: marketplaceId.value,
      mode: templateMode.value,
      parts: { ...parts }
    })
    if (data?.success && data.job) jobs.value = [data.job, ...jobs.value]
    closeTemplate()
    toast.success(t('backup.templateQueued'))
    syncPolling()
  } catch (err) {
    toast.error(err.response?.data?.error || t('backup.templateError'))
  } finally {
    templateSubmitting.value = false
  }
}

async function removeMarketplaceTemplate() {
  const tpl = selectedMarketplace.value
  if (!tpl) return
  removingTemplate.value = true
  try {
    await api.delete(`/admin/marketplace/${tpl.id}`)
    marketplaceId.value = ''
    await loadMarketplace()
    toast.success(t('backup.templateRemoved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('backup.removeError'))
  } finally {
    removingTemplate.value = false
  }
}

// ---- Publish a snapshot to the marketplace (owner only) ----
function openPublish(snap) {
  publishTarget.value = snap
  publishName.value = snap.name || snap.guild_name || ''
  publishDescription.value = ''
  publishCategory.value = ''
}

async function confirmPublish() {
  const snap = publishTarget.value
  if (!snap) return
  publishSubmitting.value = true
  try {
    await api.post('/admin/marketplace/publish', {
      source_guild_id: guildId.value,
      backup_id: snap.id,
      name: publishName.value,
      description: publishDescription.value,
      category: publishCategory.value
    })
    publishTarget.value = null
    toast.success(t('backup.published'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('backup.publishError'))
  } finally {
    publishSubmitting.value = false
  }
}

async function applyTemplate() {
  if (!templateSourceId.value || !templateBackupId.value || noPartsSelected.value) return
  templateSubmitting.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/backups/apply-template`, {
      source_guild_id: templateSourceId.value,
      backup_id: templateBackupId.value,
      mode: templateMode.value,
      parts: { ...parts }
    })
    if (data?.success && data.job) jobs.value = [data.job, ...jobs.value]
    closeTemplate()
    toast.success(t('backup.templateQueued'))
    syncPolling()
  } catch (err) {
    toast.error(err.response?.data?.error || t('backup.templateError'))
  } finally {
    templateSubmitting.value = false
  }
}

function openDelete(snap) {
  deleteTarget.value = snap
}

async function confirmDelete() {
  const snap = deleteTarget.value
  if (!snap) return
  deleteSubmitting.value = true
  deletingIds.add(snap.id)
  try {
    await api.delete(`/guilds/${guildId.value}/backups/${snap.id}`)
    snapshots.value = snapshots.value.filter(s => s.id !== snap.id)
    deleteTarget.value = null
    toast.success(t('backup.deleted'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('backup.deleteError'))
  } finally {
    deleteSubmitting.value = false
    deletingIds.delete(snap.id)
  }
}
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; }
.config__head-text { flex: 1; min-width: 0; }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }
.config__head-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.config__form { display: flex; flex-direction: column; gap: var(--space-4); max-width: 920px; }
.form-card { background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5) var(--space-6); box-shadow: var(--shadow-inset); }
.state { color: var(--color-text-muted); text-align: center; }
.empty { text-align: center; }
.empty__title { font-family: var(--font-display); font-size: 1.05rem; font-weight: 600; margin-bottom: var(--space-2); }
.empty__body { color: var(--color-text-muted); font-size: 0.92rem; }

.job-banner { display: flex; align-items: center; gap: var(--space-3); border-color: rgba(99, 102, 241, 0.4); background: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(88, 101, 242, 0.06)); }
.job-banner__text { font-weight: 600; font-size: 0.92rem; color: var(--color-text); }
.job-banner__spinner { width: 16px; height: 16px; flex-shrink: 0; border: 2px solid var(--color-primary); border-right-color: transparent; border-radius: 50%; animation: spin 0.7s linear infinite; }

.snap-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; }
.snap-row__main { display: flex; align-items: center; gap: var(--space-3); min-width: 0; }
.snap-row__icon { width: 40px; height: 40px; flex-shrink: 0; border-radius: var(--radius-md); display: inline-flex; align-items: center; justify-content: center; color: #fff; background: linear-gradient(135deg, #14b8a6, #22d3ee); }
.snap-row__text { min-width: 0; }
.snap-row__name { font-family: var(--font-display); font-weight: 600; font-size: 1rem; }
.snap-row__meta { display: flex; align-items: center; gap: var(--space-2); font-size: 0.8rem; color: var(--color-text-soft); margin-top: 2px; flex-wrap: wrap; }
.snap-row__dot { opacity: 0.6; }
.snap-row__actions { display: flex; gap: var(--space-2); flex-shrink: 0; }

.mode-cards { display: flex; flex-direction: column; gap: var(--space-3); margin-bottom: var(--space-2); }
.mode-card { display: flex; align-items: flex-start; gap: var(--space-3); text-align: left; padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg); cursor: pointer; transition: border-color var(--transition), background var(--transition); }
.mode-card:hover { border-color: var(--color-border-strong); }
.mode-card.is-active { border-color: var(--color-primary); background: var(--color-primary-soft); }
.mode-card--danger.is-active { border-color: var(--color-danger); background: var(--color-danger-soft); }
.mode-card__radio { width: 18px; height: 18px; flex-shrink: 0; margin-top: 2px; border-radius: 50%; border: 2px solid var(--color-border-strong); position: relative; transition: border-color var(--transition); }
.mode-card.is-active .mode-card__radio { border-color: var(--color-primary); }
.mode-card--danger.is-active .mode-card__radio { border-color: var(--color-danger); }
.mode-card.is-active .mode-card__radio::after { content: ''; position: absolute; inset: 3px; border-radius: 50%; background: var(--color-primary); }
.mode-card--danger.is-active .mode-card__radio::after { background: var(--color-danger); }
.mode-card__text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.mode-card__title { font-weight: 600; font-size: 0.92rem; }
.mode-card__hint { font-size: 0.8rem; color: var(--color-text-muted); line-height: 1.45; }

.parts-group { display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: center; margin-top: var(--space-4); padding: var(--space-3) var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg); }
.parts-group__label { flex-basis: 100%; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-soft); }
.parts-check { display: inline-flex; align-items: center; gap: 6px; font-size: 0.88rem; cursor: pointer; }
.parts-check input { width: 16px; height: 16px; accent-color: var(--color-primary); cursor: pointer; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; z-index: 8000; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; padding: var(--space-4); }
.modal { width: 100%; max-width: 480px; background: var(--color-surface); border: 1px solid var(--color-border-strong); border-radius: var(--radius-xl); box-shadow: var(--shadow-xl); padding: var(--space-6); max-height: 90vh; overflow-y: auto; }
.modal__title { font-size: 1.2rem; margin-bottom: var(--space-3); }
.modal__body { color: var(--color-text-muted); line-height: 1.55; margin-bottom: var(--space-4); }
.modal--wide { max-width: 620px; }
.modal__actions { display: flex; justify-content: flex-end; gap: var(--space-3); margin-top: var(--space-4); }

.detail-name { margin-bottom: var(--space-4); font-size: 0.85rem; }
.detail-state { text-align: center; color: var(--color-text-muted); padding: var(--space-5) 0; }
.detail-state--err { color: var(--color-danger); }
.detail-body { display: flex; flex-direction: column; gap: var(--space-5); }
.detail-sec__head { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }

.detail-server { display: flex; align-items: center; gap: var(--space-3); }
.detail-server__icon { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.detail-server__icon--ph { display: inline-flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.9rem; color: #fff; background: linear-gradient(135deg, #14b8a6, #22d3ee); }
.detail-server__name { font-family: var(--font-display); font-weight: 600; }
.detail-server__meta { font-size: 0.8rem; color: var(--color-text-soft); margin-top: 2px; }

.detail-tree { display: flex; flex-direction: column; gap: 2px; max-height: 240px; overflow-y: auto; padding: var(--space-3); background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-lg); font-size: 0.88rem; }
.detail-cat { font-weight: 700; color: var(--color-text); margin-top: var(--space-2); }
.detail-cat:first-child { margin-top: 0; }
.detail-chan { color: var(--color-text-muted); }
.detail-chan--nested { padding-left: var(--space-4); }

.tmpl-body { display: flex; flex-direction: column; gap: var(--space-4); }
.tmpl-field { display: flex; flex-direction: column; gap: var(--space-2); }
.tmpl-field__label { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-soft); }
.tmpl-select { width: 100%; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg); color: var(--color-text); font-size: 0.92rem; }
.tmpl-select:focus { outline: none; border-color: var(--color-primary); }
.tmpl-input, .tmpl-textarea { width: 100%; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg); color: var(--color-text); font-size: 0.92rem; font-family: inherit; }
.tmpl-input:focus, .tmpl-textarea:focus { outline: none; border-color: var(--color-primary); }
.tmpl-textarea { resize: vertical; min-height: 72px; line-height: 1.5; }

.tmpl-tabs { display: inline-flex; gap: 2px; padding: 3px; margin-bottom: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg); }
.tmpl-tab { padding: 6px 16px; border: none; border-radius: calc(var(--radius-lg) - 3px); background: transparent; color: var(--color-text-muted); font-size: 0.88rem; font-weight: 600; cursor: pointer; transition: background var(--transition), color var(--transition); }
.tmpl-tab:hover { color: var(--color-text); }
.tmpl-tab.is-active { background: var(--color-surface); color: var(--color-text); box-shadow: var(--shadow-inset); }

.tmpl-shared { display: flex; flex-direction: column; gap: 0; }
.tmpl-shared .mode-cards { margin-top: var(--space-4); }
.tmpl-market-info { display: flex; flex-direction: column; gap: var(--space-2); }
.tmpl-market-desc { color: var(--color-text-muted); font-size: 0.86rem; line-height: 1.5; margin: 0; }
.tmpl-remove { align-self: flex-start; display: inline-flex; align-items: center; gap: 6px; padding: 0; border: none; background: transparent; color: var(--color-danger); font-size: 0.82rem; font-weight: 600; cursor: pointer; }
.tmpl-remove:disabled { opacity: 0.5; cursor: default; }

.detail-roles { display: flex; flex-wrap: wrap; gap: var(--space-2); max-height: 200px; overflow-y: auto; }
.detail-role { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border: 1px solid var(--color-border); border-radius: 999px; font-size: 0.82rem; }
.detail-role__dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active, .modal-leave-active { transition: opacity var(--transition); }

.dirty-bar-enter-active, .dirty-bar-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.dirty-bar-enter-from, .dirty-bar-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
