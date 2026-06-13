<template>
  <div class="config">
    <header class="config__head">
      <div>
        <div class="config__eyebrow">{{ t('tickets.eyebrow') }}</div>
        <h1 class="config__title">{{ t('tickets.title') }}</h1>
        <p class="config__sub">{{ t('tickets.sub') }}</p>
      </div>
    </header>

    <!-- ===== General ===== -->
    <section class="form-card">
      <div class="card-title">{{ t('tickets.sectionGeneral') }}</div>

      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('tickets.enableLabel') }}</div>
          <div class="row__hint">{{ t('tickets.enableHint') }}</div>
        </div>
        <AppToggle v-model="form.enabled" />
      </div>

      <div class="row">
        <label class="row__label">{{ t('tickets.panelChannelLabel') }}</label>
        <div class="row__hint">{{ t('tickets.panelChannelHint') }}</div>
        <ChannelSelector v-model="form.panel_channel_id" :guild-id="guildId" :types="['text', 'announcement']" />
      </div>

      <div class="row row--split">
        <div class="row">
          <label class="row__label">{{ t('tickets.categoryLabel') }}</label>
          <div class="row__hint">{{ t('tickets.categoryHint') }}</div>
          <ChannelSelector v-model="form.category_id" :guild-id="guildId" :types="['category']" :placeholder="t('tickets.categoryPlaceholder')" />
        </div>
        <div class="row">
          <label class="row__label">{{ t('tickets.supportRoleLabel') }}</label>
          <div class="row__hint">{{ t('tickets.supportRoleHint') }}</div>
          <RoleSelector v-model="form.support_role_id" :guild-id="guildId" :placeholder="t('tickets.supportRolePlaceholder')" />
        </div>
      </div>

      <div class="row row--split">
        <div class="row">
          <label class="row__label">{{ t('tickets.pingRoleLabel') }}</label>
          <div class="row__hint">{{ t('tickets.pingRoleHint') }}</div>
          <RoleSelector v-model="form.ping_role_id" :guild-id="guildId" :placeholder="t('tickets.catNonePlaceholder')" />
        </div>
        <div class="row">
          <label class="row__label" for="tk-naming">{{ t('tickets.namingLabel') }}</label>
          <div class="row__hint">{{ t('tickets.namingHint') }}</div>
          <input id="tk-naming" v-model="form.naming_template" class="input" type="text" maxlength="80" placeholder="ticket-{user}" />
        </div>
      </div>

      <div class="row row--split">
        <div class="row">
          <label class="row__label">{{ t('tickets.transcriptLabel') }}</label>
          <div class="row__hint">{{ t('tickets.transcriptHint') }}</div>
          <ChannelSelector v-model="form.transcript_channel_id" :guild-id="guildId" :types="['text', 'announcement']" :placeholder="t('tickets.transcriptPlaceholder')" />
        </div>
        <div class="row">
          <label class="row__label">{{ t('tickets.logChannelLabel') }}</label>
          <div class="row__hint">{{ t('tickets.logChannelHint') }}</div>
          <ChannelSelector v-model="form.log_channel_id" :guild-id="guildId" :types="['text', 'announcement']" :placeholder="t('tickets.logChannelPlaceholder')" />
        </div>
      </div>

      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('tickets.claimLabel') }}</div>
          <div class="row__hint">{{ t('tickets.claimHint') }}</div>
        </div>
        <AppToggle v-model="form.claim_enabled" />
      </div>

      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('tickets.closeConfirmLabel') }}</div>
          <div class="row__hint">{{ t('tickets.closeConfirmHint') }}</div>
        </div>
        <AppToggle v-model="form.close_confirm" />
      </div>
    </section>

    <!-- ===== Panel design ===== -->
    <section class="form-card">
      <div class="card-title">{{ t('tickets.sectionPanel') }}</div>

      <div class="row">
        <label class="row__label">{{ t('tickets.panelTypeLabel') }}</label>
        <div class="row__hint">{{ t('tickets.panelTypeHint') }}</div>
        <div class="segmented">
          <button type="button" class="segmented__btn" :class="{ 'is-active': form.panel_type === 'dropdown' }" @click="form.panel_type = 'dropdown'">{{ t('tickets.panelTypeDropdown') }}</button>
          <button type="button" class="segmented__btn" :class="{ 'is-active': form.panel_type === 'buttons' }" @click="form.panel_type = 'buttons'">{{ t('tickets.panelTypeButtons') }}</button>
        </div>
      </div>

      <div class="row">
        <label class="row__label">{{ t('tickets.panelEmbedLabel') }}</label>
        <div class="row__hint">{{ t('tickets.panelEmbedHint') }}</div>
        <EmbedEditor v-model="form.panel_embed" />
      </div>

      <div class="preview">
        <div class="preview__label">{{ t('tickets.livePreview') }}</div>
        <DiscordMessagePreview mode="embed" :embed="form.panel_embed" :guild-name="guildName" channel-name="tickets">
          <template #components>
            <div v-if="enabledCats.length && form.panel_type === 'dropdown'" class="dc-select">
              <span>{{ t('tickets.previewSelectPlaceholder') }}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <div v-else class="dc-row">
              <template v-if="enabledCats.length">
                <span v-for="c in enabledCats" :key="c.id" class="dc-btn" :class="`dc-btn--${c.button_style || 'primary'}`">
                  <span v-if="c.emoji" class="dc-btn__emoji">{{ c.emoji }}</span>{{ c.label || 'Ticket' }}
                </span>
              </template>
              <span v-else class="dc-btn dc-btn--primary"><span class="dc-btn__emoji">🎫</span>{{ form.button_label || 'Open Ticket' }}</span>
            </div>
          </template>
        </DiscordMessagePreview>
      </div>

      <details class="fallback">
        <summary>{{ t('tickets.fallbackTitle') }}</summary>
        <div class="fallback__body">
          <div class="row__hint">{{ t('tickets.fallbackHint') }}</div>
          <div class="row">
            <label class="row__label" for="tk-btn">{{ t('tickets.buttonLabel') }}</label>
            <input id="tk-btn" v-model="form.button_label" class="input input--narrow" type="text" maxlength="80" placeholder="Open Ticket" />
          </div>
          <div class="row">
            <label class="row__label" for="tk-msg">{{ t('tickets.messageLabel') }}</label>
            <textarea id="tk-msg" v-model="form.panel_message" class="input input--textarea" rows="2" maxlength="2000"></textarea>
          </div>
        </div>
      </details>
    </section>

    <!-- ===== Welcome message ===== -->
    <section class="form-card">
      <div class="card-title">{{ t('tickets.sectionWelcome') }}</div>
      <div class="row__hint">{{ t('tickets.welcomeHint') }}</div>
      <EmbedEditor v-model="form.welcome_embed" />

      <div class="preview">
        <div class="preview__label">{{ t('tickets.livePreview') }}</div>
        <DiscordMessagePreview mode="embed" :embed="form.welcome_embed" :guild-name="guildName" channel-name="ticket-alex" :ping-user="true">
          <template #components>
            <div class="dc-row">
              <span v-if="form.claim_enabled" class="dc-btn dc-btn--success"><span class="dc-btn__emoji">🙋</span>Claim</span>
              <span class="dc-btn dc-btn--secondary"><span class="dc-btn__emoji">➕</span>Add user</span>
              <span class="dc-btn dc-btn--secondary"><span class="dc-btn__emoji">➖</span>Remove user</span>
              <span class="dc-btn dc-btn--danger"><span class="dc-btn__emoji">🔒</span>Close</span>
            </div>
          </template>
        </DiscordMessagePreview>
      </div>
    </section>

    <!-- ===== Rating ===== -->
    <section class="form-card">
      <div class="card-title">{{ t('tickets.sectionRating') }}</div>

      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('tickets.ratingLabel') }}</div>
          <div class="row__hint">{{ t('tickets.ratingHint') }}</div>
        </div>
        <AppToggle v-model="form.rating_enabled" />
      </div>

      <div class="row" :class="{ 'is-disabled': !form.rating_enabled }">
        <label class="row__label">{{ t('tickets.ratingModeLabel') }}</label>
        <div class="row__hint">{{ t('tickets.ratingModeHint') }}</div>
        <div class="segmented">
          <button type="button" class="segmented__btn" :class="{ 'is-active': form.rating_mode === 'channel' }" :disabled="!form.rating_enabled" @click="form.rating_mode = 'channel'">{{ t('tickets.ratingModeChannel') }}</button>
          <button type="button" class="segmented__btn" :class="{ 'is-active': form.rating_mode === 'dm' }" :disabled="!form.rating_enabled" @click="form.rating_mode = 'dm'">{{ t('tickets.ratingModeDm') }}</button>
          <button type="button" class="segmented__btn" :class="{ 'is-active': form.rating_mode === 'both' }" :disabled="!form.rating_enabled" @click="form.rating_mode = 'both'">{{ t('tickets.ratingModeBoth') }}</button>
        </div>
      </div>
      <div class="row__hint">{{ t('tickets.ratingLogNote') }}</div>
    </section>

    <div class="form-card__note">{{ t('tickets.permNote') }}</div>
    <div class="form-card__note form-card__note--info">{{ t('tickets.usageNote') }}</div>

    <div class="settings-actions">
      <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.saveChanges') }}</AppButton>
    </div>

    <!-- ===== Categories ===== -->
    <section class="cats">
      <div class="cats__head">
        <div>
          <div class="card-title">{{ t('tickets.sectionCategories') }}</div>
          <div class="row__hint">{{ t('tickets.categoriesHint') }}</div>
        </div>
        <AppButton variant="gradient" :disabled="!!draftRow" @click="addDraft">
          <template #icon-left>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </template>
          {{ t('tickets.addCategory') }}
        </AppButton>
      </div>

      <div class="cats__list">
        <transition name="dirty-bar">
          <TicketCategoryRow v-if="draftRow" :model-value="draftRow" :saving="draftSaving" is-draft :guild-id="guildId" @save="saveDraft" @cancel="cancelDraft" />
        </transition>

        <div v-if="catsLoading && cats.length === 0" class="form-card state">{{ t('common.loading') }}</div>
        <div v-else-if="!catsLoading && cats.length === 0 && !draftRow" class="form-card empty">
          <div class="empty__title">{{ t('tickets.catsEmptyTitle') }}</div>
          <div class="empty__body">{{ t('tickets.catsEmptyBody') }}</div>
        </div>

        <TicketCategoryRow
          v-for="row in cats"
          :key="row.id"
          :model-value="row"
          :saving="savingIds.has(row.id)"
          :deleting="deletingIds.has(row.id)"
          :guild-id="guildId"
          @save="saveExisting"
          @delete="confirmDelete"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import AppToggle from '../components/AppToggle.vue'
import ChannelSelector from '../components/ChannelSelector.vue'
import RoleSelector from '../components/RoleSelector.vue'
import EmbedEditor from '../components/EmbedEditor.vue'
import DiscordMessagePreview from '../components/DiscordMessagePreview.vue'
import TicketCategoryRow from '../components/TicketCategoryRow.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { useGuildSettings } from '../stores/guildSettings.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const store = useGuildSettings()
const guildId = computed(() => route.params.guild_id)
const guildName = computed(() => {
  const g = store.cache.guild
  return g?.guild_name || g?.name || 'Your Server'
})

function defaultEmbed() {
  return { title: '', description: '', color: '#5865F2', thumbnail: '', image: '', footer: '', show_timestamp: false, author_name: '', author_icon_url: '' }
}

function defaultForm() {
  return {
    enabled: false,
    panel_channel_id: '',
    category_id: '',
    support_role_id: '',
    ping_role_id: '',
    panel_message: 'Need help? Click below to open a ticket.',
    button_label: 'Open Ticket',
    transcript_channel_id: '',
    log_channel_id: '',
    panel_type: 'dropdown',
    panel_embed: defaultEmbed(),
    welcome_embed: defaultEmbed(),
    naming_template: 'ticket-{user}',
    claim_enabled: true,
    close_confirm: true,
    rating_enabled: false,
    rating_mode: 'channel'
  }
}

const form = reactive(defaultForm())
const saving = ref(false)
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

function applySettings(s) {
  const d = defaultForm()
  Object.assign(form, {
    enabled: !!s.enabled,
    panel_channel_id: s.panel_channel_id || '',
    category_id: s.category_id || '',
    support_role_id: s.support_role_id || '',
    ping_role_id: s.ping_role_id || '',
    panel_message: s.panel_message || d.panel_message,
    button_label: s.button_label || 'Open Ticket',
    transcript_channel_id: s.transcript_channel_id || '',
    log_channel_id: s.log_channel_id || '',
    panel_type: s.panel_type === 'buttons' ? 'buttons' : 'dropdown',
    panel_embed: { ...defaultEmbed(), ...(s.panel_embed || {}) },
    welcome_embed: { ...defaultEmbed(), ...(s.welcome_embed || {}) },
    naming_template: s.naming_template || 'ticket-{user}',
    claim_enabled: s.claim_enabled !== false,
    close_confirm: s.close_confirm !== false,
    rating_enabled: !!s.rating_enabled,
    rating_mode: ['channel', 'dm', 'both'].includes(s.rating_mode) ? s.rating_mode : 'channel'
  })
  initial = JSON.stringify(form)
}

async function loadSettings() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/tickets`)
    if (data?.success) applySettings(data.settings || {})
  } catch (err) {
    toast.error(t('tickets.loadError'))
  }
}

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/tickets`, { ...form })
    if (data?.success && data.settings) applySettings(data.settings)
    toast.success(t('common.allSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}

// ----- Categories -----
const cats = ref([])
const enabledCats = computed(() => cats.value.filter(c => c.enabled !== false))
const catsLoading = ref(false)
const draftRow = ref(null)
const draftSaving = ref(false)
const savingIds = reactive(new Set())
const deletingIds = reactive(new Set())

function emptyDraft() {
  return { id: null, label: '', emoji: '', description: '', category_id: '', support_role_id: '', ping_role_id: '', welcome_message: '', button_style: 'primary', position: cats.value.length, enabled: true }
}

async function loadCategories() {
  if (!guildId.value) return
  catsLoading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/tickets/categories`)
    cats.value = (data?.success && Array.isArray(data.categories)) ? data.categories : []
  } catch (err) {
    cats.value = []
  } finally {
    catsLoading.value = false
  }
}

function addDraft() { draftRow.value = emptyDraft() }
function cancelDraft() { draftRow.value = null }

function serialize(p) {
  return {
    label: p.label || 'Ticket',
    emoji: p.emoji || '',
    description: p.description || '',
    category_id: p.category_id || null,
    support_role_id: p.support_role_id || null,
    ping_role_id: p.ping_role_id || null,
    welcome_message: p.welcome_message || '',
    button_style: p.button_style || 'primary',
    position: p.position ?? 0,
    enabled: p.enabled !== false
  }
}

function validate(p) {
  if (!p.label || !p.label.trim()) { toast.error(t('tickets.catLabelMissing')); return false }
  return true
}

async function saveDraft(payload) {
  if (!validate(payload)) return
  draftSaving.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/tickets/categories`, serialize(payload))
    if (data?.success && data.category) cats.value.push(data.category)
    draftRow.value = null
    toast.success(t('tickets.catCreated'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    draftSaving.value = false
  }
}

async function saveExisting(payload) {
  if (!payload?.id) return
  if (!validate(payload)) return
  savingIds.add(payload.id)
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/tickets/categories/${payload.id}`, serialize(payload))
    if (data?.success && data.category) {
      const idx = cats.value.findIndex(r => r.id === payload.id)
      if (idx !== -1) cats.value.splice(idx, 1, data.category)
    }
    toast.success(t('common.allSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    savingIds.delete(payload.id)
  }
}

async function confirmDelete(row) {
  if (!row?.id) return
  if (typeof window !== 'undefined' && !window.confirm(t('tickets.catDeleteConfirm'))) return
  deletingIds.add(row.id)
  try {
    await api.delete(`/guilds/${guildId.value}/tickets/categories/${row.id}`)
    cats.value = cats.value.filter(r => r.id !== row.id)
    toast.success(t('tickets.catDeleted'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingIds.delete(row.id)
  }
}

function loadAll() { loadSettings(); loadCategories() }
onMounted(loadAll)
watch(guildId, loadAll)
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }

.form-card { max-width: 920px; background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-6); box-shadow: var(--shadow-inset); display: flex; flex-direction: column; gap: var(--space-5); margin-bottom: var(--space-4); }
.card-title { font-family: var(--font-display); font-size: 1.05rem; font-weight: 600; letter-spacing: -0.01em; }

.row { display: flex; flex-direction: column; gap: var(--space-2); min-width: 0; }
.row--toggle { flex-direction: row; align-items: center; justify-content: space-between; gap: var(--space-4); }
.row--split { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); align-items: start; }
.row.is-disabled { opacity: 0.5; pointer-events: none; }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }

.input { width: 100%; padding: 0.7rem 0.85rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.95rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--textarea { resize: vertical; min-height: 60px; line-height: 1.5; }
.input--narrow { max-width: 220px; }

.segmented { display: inline-flex; gap: 4px; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); padding: 3px; width: fit-content; }
.segmented__btn { padding: 0.5rem 1rem; border-radius: var(--radius-sm); font-size: 0.88rem; font-weight: 600; color: var(--color-text-muted); }
.segmented__btn.is-active { background: var(--gradient-brand); color: #fff; }
.segmented__btn:disabled { opacity: 0.5; cursor: not-allowed; }

.fallback { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); }
.fallback summary { cursor: pointer; font-weight: 600; font-size: 0.9rem; color: var(--color-text-muted); }
.fallback__body { display: flex; flex-direction: column; gap: var(--space-4); margin-top: var(--space-4); }

.preview { border-top: 1px solid var(--color-border); padding-top: var(--space-4); }
.preview__label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-3); }

/* Discord-style mock components rendered inside the preview bubble. */
.dc-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.dc-btn { display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 14px; border-radius: 3px; font-size: 0.86rem; font-weight: 500; color: #fff; line-height: 1; white-space: nowrap; }
.dc-btn__emoji { font-size: 0.95rem; }
.dc-btn--primary { background: #5865f2; }
.dc-btn--secondary { background: #4e5058; }
.dc-btn--success { background: #248046; }
.dc-btn--danger { background: #da373c; }
.dc-select { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px; max-width: 420px; padding: 0 12px; height: 40px; border-radius: 4px; background: #1e1f22; border: 1px solid #2b2d31; color: #949ba4; font-size: 0.88rem; }

.form-card__note { max-width: 920px; font-size: 0.82rem; border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); line-height: 1.5; color: var(--color-warning); background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.25); margin-bottom: var(--space-3); }
.form-card__note--info { color: var(--color-text-muted); background: var(--color-bg-elevated); border: 1px solid var(--color-border); }

.settings-actions { max-width: 920px; display: flex; justify-content: flex-end; margin-bottom: var(--space-8); }

.cats { max-width: 920px; }
.cats__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; margin-bottom: var(--space-4); }
.cats__list { display: flex; flex-direction: column; gap: var(--space-4); }
.state { color: var(--color-text-muted); text-align: center; }
.empty { text-align: center; }
.empty__title { font-family: var(--font-display); font-size: 1.05rem; font-weight: 600; margin-bottom: var(--space-2); }
.empty__body { color: var(--color-text-muted); font-size: 0.92rem; }
.dirty-bar-enter-active, .dirty-bar-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.dirty-bar-enter-from, .dirty-bar-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 640px) { .row--split { grid-template-columns: 1fr; } }
</style>
