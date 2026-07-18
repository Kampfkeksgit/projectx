<template>
  <div class="config">
    <header class="config__head">
      <div class="config__head-text">
        <div class="config__eyebrow">{{ t('reactionRoles.eyebrow') }}</div>
        <h1 class="config__title">{{ t('reactionRoles.title') }}</h1>
        <p class="config__sub">{{ t('reactionRoles.sub') }}</p>
      </div>
      <AppButton
        v-if="!editorOpen"
        variant="gradient"
        @click="openEditorForNew"
      >
        <template #icon-left>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </template>
        {{ t('reactionRoles.addButton') }}
      </AppButton>
    </header>

    <div class="config__grid config__grid--single">
      <section class="config__form">
        <!-- Editor (inline) -->
        <transition name="dirty-bar">
          <div v-if="editorOpen" class="form-card rr-editor">
            <div class="rr-editor__head">
              <div class="rr-editor__heading">{{ editingId ? t('reactionRoles.edit') : t('reactionRoles.addButton') }}</div>
              <button
                type="button"
                class="icon-btn"
                :aria-label="t('reactionRoles.cancel')"
                @click="closeEditor"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>

            <div class="form-row">
              <label class="form-row__label">{{ t('reactionRoles.modeLabel') }}</label>
              <div class="rr-mode">
                <button type="button" class="rr-mode__btn" :class="{ 'is-active': draft.auto_post }" @click="draft.auto_post = true">{{ t('reactionRoles.modeBotPost') }}</button>
                <button type="button" class="rr-mode__btn" :class="{ 'is-active': !draft.auto_post }" @click="draft.auto_post = false">{{ t('reactionRoles.modeExisting') }}</button>
              </div>
              <div class="form-row__hint">{{ t('reactionRoles.modeHint') }}</div>
            </div>

            <div class="form-row">
              <label class="form-row__label">{{ t('reactionRoles.channelLabel') }}</label>
              <ChannelSelector
                v-model="draft.channel_id"
                :guild-id="guildId"
                :types="['text', 'announcement']"
              />
              <div v-if="draft.auto_post" class="form-row__hint">{{ t('reactionRoles.channelPostHint') }}</div>
            </div>

            <!-- Legacy: attach to an existing message -->
            <div v-if="!draft.auto_post" class="form-row">
              <label class="form-row__label rr-label-row" for="rr-msg-id">
                {{ t('reactionRoles.messageIdLabel') }}
                <span class="rr-tooltip" :title="t('reactionRoles.messageIdHint')" aria-hidden="true">?</span>
              </label>
              <div class="form-row__hint">{{ t('reactionRoles.messageIdHint') }}</div>
              <input
                id="rr-msg-id"
                v-model.trim="draft.message_id"
                class="input input--mono"
                type="text"
                inputmode="numeric"
                maxlength="20"
                :placeholder="t('reactionRoles.messageIdPlaceholder')"
              />
            </div>

            <!-- Auto-post: the bot posts (and keeps updating) the message -->
            <template v-if="draft.auto_post">
              <div class="form-row">
                <label class="form-row__label" for="rr-content">{{ t('reactionRoles.contentLabel') }}</label>
                <div class="form-row__hint">{{ t('reactionRoles.contentHint') }}</div>
                <textarea
                  id="rr-content"
                  v-model="draft.content"
                  class="input rr-textarea"
                  rows="3"
                  maxlength="2000"
                  :placeholder="t('reactionRoles.contentPlaceholder')"
                ></textarea>
              </div>

              <div class="form-row">
                <label class="form-row__label">{{ t('reactionRoles.messageModeLabel') }}</label>
                <div class="rr-mode">
                  <button type="button" class="rr-mode__btn" :class="{ 'is-active': !draft.use_embed }" @click="draft.use_embed = false">{{ t('reactionRoles.messageModePlain') }}</button>
                  <button type="button" class="rr-mode__btn" :class="{ 'is-active': draft.use_embed }" @click="draft.use_embed = true">{{ t('reactionRoles.messageModeEmbed') }}</button>
                </div>
                <div class="form-row__hint">{{ t('reactionRoles.messageModeHint') }}</div>
              </div>

              <div v-if="draft.use_embed" class="form-row">
                <label class="form-row__label">{{ t('reactionRoles.embedLabel') }}</label>
                <div class="form-row__hint">{{ t('reactionRoles.embedHint') }}</div>
                <EmbedEditor v-model="draft.embed" />
              </div>

              <div class="form-row">
                <div class="rr-preview__label">{{ t('reactionRoles.livePreview') }}</div>
                <DiscordMessagePreview
                  :mode="draft.use_embed ? 'embed' : 'plain'"
                  :message="draft.content"
                  :embed="draft.embed"
                  :guild-name="guildName"
                  :channel-name="previewChannelName"
                >
                  <template #components>
                    <div v-if="previewMappings.length" class="rr-reactions">
                      <span v-for="(mp, i) in previewMappings" :key="i" class="rr-reaction">
                        <span class="rr-reaction__emoji">{{ mp.emoji }}</span>
                        <span class="rr-reaction__count">1</span>
                      </span>
                    </div>
                  </template>
                </DiscordMessagePreview>
                <div class="rr-status" :class="draft.posted ? 'is-posted' : 'is-pending'">
                  {{ draft.posted ? t('reactionRoles.statusPosted') : t('reactionRoles.statusPending') }}
                </div>
                <div class="form-row__hint">{{ t('reactionRoles.postHint') }}</div>
              </div>
            </template>

            <div class="form-row">
              <label class="form-row__label" for="rr-name">{{ t('reactionRoles.nameLabel') }}</label>
              <input
                id="rr-name"
                v-model="draft.name"
                class="input"
                type="text"
                maxlength="80"
                :placeholder="t('reactionRoles.namePlaceholder')"
              />
            </div>

            <div class="form-row form-row--toggle">
              <div>
                <div class="form-row__label">{{ t('reactionRoles.exclusiveLabel') }}</div>
                <div class="form-row__hint">{{ t('reactionRoles.exclusiveHint') }}</div>
              </div>
              <AppToggle v-model="draft.exclusive" />
            </div>

            <div class="form-row">
              <div class="form-row__label">{{ t('reactionRoles.mappingsLabel') }}</div>
              <div class="form-row__hint">{{ t('reactionRoles.mappingsHint') }}</div>

              <div class="rr-mappings">
                <div
                  v-for="(row, idx) in draft.mappings"
                  :key="idx"
                  class="rr-mapping"
                >
                  <div class="rr-mapping__col rr-mapping__col--emoji">
                    <label class="rr-mapping__label">{{ t('reactionRoles.emojiLabel') }}</label>
                    <input
                      v-model="row.emoji"
                      class="input input--emoji"
                      type="text"
                      :placeholder="t('reactionRoles.emojiPlaceholder')"
                    />
                  </div>
                  <div class="rr-mapping__col rr-mapping__col--role">
                    <label class="rr-mapping__label">{{ t('reactionRoles.roleLabel') }}</label>
                    <RoleSelector
                      v-model="row.role_id"
                      :guild-id="guildId"
                      :multiple="false"
                    />
                  </div>
                  <button
                    type="button"
                    class="rr-mapping__remove"
                    :aria-label="t('common.reset')"
                    @click="removeMapping(idx)"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  </button>
                </div>

                <AppButton
                  variant="ghost"
                  :disabled="draft.mappings.length >= 25"
                  @click="addMapping"
                >
                  <template #icon-left>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  </template>
                  {{ t('reactionRoles.addMapping') }}
                </AppButton>
              </div>
            </div>

            <div class="rr-editor__actions">
              <AppButton variant="ghost" :disabled="saving" @click="closeEditor">{{ t('reactionRoles.cancel') }}</AppButton>
              <AppButton variant="gradient" :loading="saving" @click="saveDraft">{{ t('reactionRoles.saveMessage') }}</AppButton>
            </div>
          </div>
        </transition>

        <!-- List -->
        <div v-if="loading && messages.length === 0" class="form-card rr-state">
          {{ t('common.loading') }}
        </div>
        <div v-else-if="!loading && messages.length === 0" class="form-card rr-empty">
          <div class="rr-empty__title">{{ t('reactionRoles.emptyTitle') }}</div>
          <div class="rr-empty__body">{{ t('reactionRoles.emptyBody') }}</div>
        </div>

        <article
          v-for="m in messages"
          :key="m.id"
          class="form-card rr-card"
        >
          <div class="rr-card__head">
            <div class="rr-card__title-wrap">
              <div class="rr-card__title">{{ m.name || t('reactionRoles.untitled', { id: m.id }) }}</div>
              <div class="rr-card__meta">
                <span class="rr-card__channel">#{{ resolveChannelName(m.channel_id) }}</span>
                <span
                  v-if="m.auto_post"
                  class="rr-card__mode"
                  :class="m.posted ? 'is-posted' : 'is-pending'"
                >{{ m.posted ? t('reactionRoles.statusPosted') : t('reactionRoles.statusPending') }}</span>
                <span v-else class="rr-card__msg" :title="m.message_id">ID {{ shortenId(m.message_id) }}</span>
                <span v-if="m.exclusive" class="rr-card__tag">{{ t('reactionRoles.exclusiveLabel') }}</span>
                <span class="rr-card__count">{{ m.mappings?.length || 0 }} × {{ t('reactionRoles.roleLabel') }}</span>
              </div>
            </div>
            <div class="rr-card__actions">
              <AppButton variant="ghost" @click="openEditorFor(m)">{{ t('reactionRoles.edit') }}</AppButton>
              <AppButton variant="danger" :loading="deletingId === m.id" @click="confirmDelete(m)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>
              </AppButton>
            </div>
          </div>

          <ul v-if="m.mappings && m.mappings.length" class="rr-card__mappings">
            <li v-for="(map, i) in m.mappings" :key="i" class="rr-card__mapping">
              <span class="rr-card__emoji">{{ map.emoji }}</span>
              <span class="rr-card__role">{{ resolveRoleName(map.role_id) }}</span>
            </li>
          </ul>
        </article>
      </section>
    </div>
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
import api from '../services/api.js'
import { useGuildResources } from '../composables/useGuildResources.js'
import { useGuildSettings } from '../stores/guildSettings.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { useAutoRefresh } from '../composables/useAutoRefresh.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const store = useGuildSettings()

const guildId = computed(() => route.params.guild_id)
const resources = computed(() => useGuildResources(guildId.value))
const guildName = computed(() => {
  const g = store.cache.guild
  return g?.guild_name || g?.name || 'Your Server'
})

const messages = ref([])
const loading = ref(false)
const saving = ref(false)
const deletingId = ref(null)

const editorOpen = ref(false)
const editingId = ref(null)

function defaultEmbed() {
  return { title: '', description: '', color: '#5865F2', thumbnail: '', image: '', footer: '', show_timestamp: false, author_name: '', author_icon_url: '', format: 'embed', accent_color: '#5865F2', blocks: [] }
}

// New entries default to the bot posting the message itself (auto_post).
function emptyDraft() {
  return {
    channel_id: '',
    message_id: '',
    name: '',
    exclusive: false,
    auto_post: true,
    content: '',
    use_embed: false,
    embed: defaultEmbed(),
    posted: false,
    mappings: [{ emoji: '', role_id: '' }]
  }
}

const draft = reactive(emptyDraft())

function resetDraft() {
  Object.assign(draft, emptyDraft())
}

/** True when the embed carries something worth posting (classic fields or a
 * Components-V2 block with content). Used to allow embed-only auto-post entries. */
function embedHasContent(e) {
  if (!e) return false
  if (e.format === 'components_v2') {
    return Array.isArray(e.blocks) && e.blocks.some(b =>
      (b.type === 'text' && (b.content || '').trim()) ||
      (b.type === 'section' && ((b.content || '').trim() || b.thumbnail)) ||
      (b.type === 'image' && b.url))
  }
  return !!(
    (e.title || '').trim() || (e.description || '').trim() || e.image ||
    e.thumbnail || (e.author_name || '').trim() || (e.footer || '').trim()
  )
}

// Emoji reactions the bot will attach — mirrored below the live preview.
const previewMappings = computed(() => draft.mappings.filter(m => m.emoji && m.emoji.trim()))
const previewChannelName = computed(() => {
  if (!draft.channel_id) return ''
  const ch = resources.value.state.channels?.find(c => c.id === draft.channel_id)
  return ch?.name || 'channel'
})

function shortenId(id) {
  if (!id) return ''
  return id.length > 10 ? `…${id.slice(-6)}` : id
}

function resolveChannelName(id) {
  if (!id) return '—'
  const ch = resources.value.state.channels?.find(c => c.id === id)
  return ch?.name || id
}

function resolveRoleName(id) {
  if (!id) return '—'
  const r = resources.value.state.roles?.find(rr => rr.id === id)
  return r?.name || id
}

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/reaction-roles`)
    if (data?.success) {
      messages.value = Array.isArray(data.messages) ? data.messages : []
    } else {
      messages.value = []
    }
  } catch (err) {
    toast.error(t('reactionRoles.loadError'))
    messages.value = []
  } finally {
    loading.value = false
  }
  // Warm the resources cache so names resolve in the list view.
  resources.value.loadChannels()
  resources.value.loadRoles()
}

onMounted(load)
watch(() => guildId.value, load)
// Auto-refresh the list; skip while the inline editor is open so unsaved edits
// aren't clobbered. Individual rows re-render from the list state on refresh.
useAutoRefresh(load, { isDirty: () => editorOpen.value })

function openEditorForNew() {
  editingId.value = null
  resetDraft()
  editorOpen.value = true
}

function openEditorFor(m) {
  editingId.value = m.id
  draft.channel_id = m.channel_id || ''
  draft.message_id = m.message_id || ''
  draft.name = m.name || ''
  draft.exclusive = !!m.exclusive
  draft.auto_post = !!m.auto_post
  draft.content = m.content || ''
  draft.use_embed = !!m.use_embed
  draft.embed = { ...defaultEmbed(), ...(m.embed || {}) }
  draft.posted = !!m.posted
  draft.mappings = Array.isArray(m.mappings) && m.mappings.length
    ? m.mappings.map(x => ({ emoji: x.emoji || '', role_id: x.role_id || '' }))
    : [{ emoji: '', role_id: '' }]
  editorOpen.value = true
}

function closeEditor() {
  editorOpen.value = false
  editingId.value = null
  resetDraft()
}

function addMapping() {
  if (draft.mappings.length >= 25) return
  draft.mappings.push({ emoji: '', role_id: '' })
}

function removeMapping(idx) {
  draft.mappings.splice(idx, 1)
  if (draft.mappings.length === 0) {
    draft.mappings.push({ emoji: '', role_id: '' })
  }
}

function validateDraft() {
  if (!draft.channel_id) {
    toast.error(t('reactionRoles.channelMissing'))
    return false
  }
  // Legacy path attaches to an existing message → a message ID is required.
  if (!draft.auto_post && !/^\d{17,20}$/.test(draft.message_id)) {
    toast.error(t('reactionRoles.messageIdInvalid'))
    return false
  }
  if (!draft.name.trim()) {
    toast.error(t('reactionRoles.nameMissing'))
    return false
  }
  const cleaned = draft.mappings.filter(m => m.emoji.trim() || m.role_id)
  if (cleaned.length === 0) {
    toast.error(t('reactionRoles.mappingsMissing'))
    return false
  }
  for (const m of cleaned) {
    if (!m.emoji.trim()) {
      toast.error(t('reactionRoles.mappingsEmojiMissing'))
      return false
    }
    if (!m.role_id) {
      toast.error(t('reactionRoles.mappingsRoleMissing'))
      return false
    }
  }
  const seen = new Set()
  for (const m of cleaned) {
    const k = m.emoji.trim()
    if (seen.has(k)) {
      toast.error(t('reactionRoles.mappingsDuplicate'))
      return false
    }
    seen.add(k)
  }
  // Auto-post entries need something to post: message text and/or an embed.
  if (draft.auto_post) {
    const hasContent = (draft.content || '').trim().length > 0
    const hasEmbed = draft.use_embed && embedHasContent(draft.embed)
    if (!hasContent && !hasEmbed) {
      toast.error(t('reactionRoles.contentOrEmbedMissing'))
      return false
    }
  }
  return true
}

async function saveDraft() {
  if (!validateDraft()) return
  saving.value = true
  const body = {
    channel_id: draft.channel_id,
    name: draft.name.trim(),
    exclusive: !!draft.exclusive,
    auto_post: !!draft.auto_post,
    content: draft.content || '',
    use_embed: !!draft.use_embed,
    embed: draft.embed || defaultEmbed(),
    mappings: draft.mappings
      .filter(m => m.emoji.trim() && m.role_id)
      .map(m => ({ emoji: m.emoji.trim(), role_id: m.role_id }))
  }
  // Only the legacy (existing-message) path sends a message_id.
  if (!draft.auto_post) {
    body.message_id = draft.message_id.trim()
  }
  try {
    if (editingId.value) {
      const { data } = await api.put(`/guilds/${guildId.value}/reaction-roles/${editingId.value}`, body)
      if (data?.success && data.message) {
        const idx = messages.value.findIndex(m => m.id === editingId.value)
        if (idx !== -1) messages.value.splice(idx, 1, data.message)
      }
      toast.success(t('reactionRoles.savedUpdated'))
    } else {
      const { data } = await api.post(`/guilds/${guildId.value}/reaction-roles`, body)
      if (data?.success && data.message) {
        messages.value.push(data.message)
      }
      toast.success(t('reactionRoles.savedCreated'))
    }
    closeEditor()
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}

async function confirmDelete(m) {
  if (typeof window !== 'undefined' && !window.confirm(t('reactionRoles.deleteConfirm'))) return
  deletingId.value = m.id
  try {
    await api.delete(`/guilds/${guildId.value}/reaction-roles/${m.id}`)
    messages.value = messages.value.filter(x => x.id !== m.id)
    toast.success(t('reactionRoles.deleted'))
    if (editingId.value === m.id) closeEditor()
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingId.value = null
  }
}
</script>

<style scoped>
.config__head {
  margin-bottom: var(--space-6);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.config__head-text {
  flex: 1;
  min-width: 0;
}

.config__eyebrow {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-soft);
  margin-bottom: var(--space-2);
}

.config__title {
  font-size: clamp(1.6rem, 2.5vw, 2rem);
  letter-spacing: -0.02em;
  margin-bottom: var(--space-2);
}

.config__sub {
  color: var(--color-text-muted);
}

.config__grid {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: var(--space-5);
  align-items: flex-start;
}

.config__grid--single {
  grid-template-columns: minmax(0, 920px);
}

.config__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  box-shadow: var(--shadow-inset);
  transition: opacity var(--transition);
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-row--toggle {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.form-row__label {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--color-text);
}

.form-row__hint {
  font-size: 0.82rem;
  color: var(--color-text-muted);
  line-height: 1.55;
}

.input {
  width: 100%;
  padding: 0.7rem 0.85rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.95rem;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.input--mono {
  font-family: var(--font-mono);
  letter-spacing: 0.02em;
}

.input--emoji {
  font-family: var(--font-mono);
}

.rr-textarea {
  resize: vertical;
  min-height: 74px;
  line-height: 1.5;
}

/* Segmented mode switches (bot-post vs existing, plain vs embed) */
.rr-mode {
  display: inline-flex;
  gap: 4px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  padding: 3px;
  width: fit-content;
  max-width: 100%;
  flex-wrap: wrap;
}

.rr-mode__btn {
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-sm);
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--color-text-muted);
}

.rr-mode__btn.is-active {
  background: var(--gradient-brand);
  color: #fff;
}

/* Live preview */
.rr-preview__label {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-soft);
  margin-bottom: var(--space-2);
}

.rr-reactions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.rr-reaction {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 8px;
  border-radius: 8px;
  background: #3b3d44;
  border: 1px solid #232428;
  font-size: 0.82rem;
  color: #dbdee1;
}

.rr-reaction__emoji {
  font-family: var(--font-mono);
  line-height: 1;
}

.rr-reaction__count {
  font-weight: 600;
  color: #b5bac1;
}

.rr-status {
  margin-top: var(--space-2);
  display: inline-flex;
  align-items: center;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-sm);
}

.rr-status.is-posted {
  color: var(--color-success);
  background: rgba(34, 197, 94, 0.12);
}

.rr-status.is-pending {
  color: var(--color-warning);
  background: rgba(245, 158, 11, 0.14);
}

/* Editor */
.rr-editor__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.rr-editor__heading {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 600;
}

.rr-label-row {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.rr-tooltip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-surface-2);
  color: var(--color-text-soft);
  font-size: 0.7rem;
  font-weight: 700;
  cursor: help;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  color: var(--color-text-muted);
  background: transparent;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.icon-btn:hover {
  background: var(--color-surface-2);
  color: var(--color-text);
}

.rr-mappings {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.rr-mapping {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) auto;
  gap: var(--space-3);
  align-items: flex-end;
  padding: var(--space-3);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.rr-mapping__col {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.rr-mapping__label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-soft);
  font-weight: 600;
}

.rr-mapping__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  color: var(--color-text-muted);
  background: transparent;
  border: 1px solid transparent;
  transition: background var(--transition-fast), color var(--transition-fast);
  align-self: flex-end;
}

.rr-mapping__remove:hover {
  background: rgba(239, 68, 68, 0.18);
  color: var(--color-danger);
}

.rr-editor__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

/* List card */
.rr-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.rr-card__title-wrap {
  flex: 1;
  min-width: 0;
}

.rr-card__title {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 4px;
}

.rr-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  font-size: 0.82rem;
  color: var(--color-text-muted);
}

.rr-card__channel,
.rr-card__msg,
.rr-card__count {
  background: var(--color-surface-2);
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
}

.rr-card__msg {
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

.rr-card__mode {
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 0.78rem;
}

.rr-card__mode.is-posted {
  color: var(--color-success);
  background: rgba(34, 197, 94, 0.12);
}

.rr-card__mode.is-pending {
  color: var(--color-warning);
  background: rgba(245, 158, 11, 0.14);
}

.rr-card__tag {
  background: var(--color-primary-soft);
  color: #fff;
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.rr-card__actions {
  display: inline-flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.rr-card__mappings {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.rr-card__mapping {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.3rem 0.55rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
}

.rr-card__emoji {
  font-family: var(--font-mono);
}

.rr-card__role {
  color: var(--color-text-muted);
}

.rr-state {
  color: var(--color-text-muted);
  text-align: center;
}

.rr-empty {
  text-align: center;
}

.rr-empty__title {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.rr-empty__body {
  color: var(--color-text-muted);
  font-size: 0.92rem;
}

/* dirty-bar transition reused for editor reveal */
.dirty-bar-enter-active,
.dirty-bar-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.dirty-bar-enter-from,
.dirty-bar-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 720px) {
  .rr-mapping {
    grid-template-columns: 1fr;
  }
  .rr-mapping__remove {
    justify-self: flex-end;
  }
}
</style>
