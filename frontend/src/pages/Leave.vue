<template>
  <div class="config">
    <header class="config__head">
      <div>
        <div class="config__eyebrow">{{ t('leave.eyebrow') }}</div>
        <h1 class="config__title">{{ t('leave.title') }}</h1>
        <p class="config__sub">{{ t('leave.sub') }}</p>
      </div>
    </header>

    <div class="config__grid">
      <section class="config__form">
        <!-- 1. Master enable -->
        <div class="form-card">
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('leave.toggleLabel') }}</div>
              <div class="form-row__hint">{{ t('leave.toggleHint') }}</div>
            </div>
            <AppToggle v-model="form.leave_enabled" />
          </div>
        </div>

        <!-- 2. Channel -->
        <div class="form-card" :class="{ 'is-disabled': !form.leave_enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('leave.channelLabel') }}</div>
            <div class="form-row__hint">{{ t('resourceSelector.channelPickHint') }}</div>
            <ChannelSelector
              v-model="form.leave_channel_id"
              :guild-id="guildId"
              :types="['text', 'announcement']"
              :disabled="!form.leave_enabled"
            />
          </div>
        </div>

        <!-- 3. Message mode -->
        <div class="form-card" :class="{ 'is-disabled': !form.leave_enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('leave.modeLabel') }}</div>
            <div class="segmented">
              <AppButton
                :variant="!form.leave_use_embed ? 'gradient' : 'subtle'"
                :disabled="!form.leave_enabled"
                @click="form.leave_use_embed = false"
              >{{ t('leave.modePlain') }}</AppButton>
              <AppButton
                :variant="form.leave_use_embed ? 'gradient' : 'subtle'"
                :disabled="!form.leave_enabled"
                @click="form.leave_use_embed = true"
              >{{ t('leave.modeEmbed') }}</AppButton>
            </div>
          </div>
        </div>

        <!-- 4. Plain message -->
        <div v-if="!form.leave_use_embed" class="form-card" :class="{ 'is-disabled': !form.leave_enabled }">
          <div class="form-row">
            <label class="form-row__label" for="leave-message">{{ t('leave.messageLabel') }}</label>
            <div class="form-row__hint" v-html="t('leave.messageHintHtml')"></div>
            <textarea
              id="leave-message"
              ref="messageRef"
              class="input input--textarea"
              :disabled="!form.leave_enabled"
              v-model="form.leave_message"
              rows="5"
              :placeholder="t('leave.messagePlaceholder')"
            ></textarea>
            <div class="placeholder-bar">
              <button
                v-for="ph in PLACEHOLDERS"
                :key="ph.token"
                type="button"
                class="placeholder-bar__chip"
                :disabled="!form.leave_enabled"
                :title="t(`embedEditor.${ph.labelKey}`)"
                @click="insertIntoMessage(ph.token)"
              >{{ ph.token }}</button>
            </div>
          </div>
        </div>

        <!-- 5. Embed -->
        <div v-else class="form-card" :class="{ 'is-disabled': !form.leave_enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('embedEditor.sectionTitle') }}</div>
          </div>
          <EmbedEditor v-model="form.leave_embed" :disabled="!form.leave_enabled" />
        </div>

        <!-- 6. Auto-delete -->
        <div class="form-card" :class="{ 'is-disabled': !form.leave_enabled }">
          <div class="form-row">
            <label class="form-row__label" for="leave-delete-after">{{ t('leave.deleteAfterLabel') }}</label>
            <div class="form-row__hint">{{ t('leave.deleteAfterHint') }}</div>
            <div class="delete-after-row">
              <input
                id="leave-delete-after"
                class="input input--num"
                type="number"
                min="0"
                max="600"
                step="1"
                :disabled="!form.leave_enabled"
                v-model.number="form.leave_delete_after"
              />
              <input
                class="slider"
                type="range"
                min="0"
                max="600"
                step="5"
                :disabled="!form.leave_enabled"
                v-model.number="form.leave_delete_after"
              />
              <span class="delete-after-suffix">
                {{ form.leave_delete_after > 0
                  ? t('leave.deleteAfterSecondsSuffix')
                  : t('leave.deleteAfterOffSuffix') }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <aside class="config__preview">
        <div class="config__preview-label">{{ t('leave.livePreview') }}</div>
        <DiscordMessagePreview
          channel-name="goodbye"
          :message="form.leave_message"
          :guild-name="guildName"
          :mode="form.leave_use_embed ? 'embed' : 'plain'"
          :embed="form.leave_embed"
          username="Alex"
        />
      </aside>
    </div>

    <transition name="dirty-bar">
      <footer v-if="dirty" class="config__footer">
        <div class="config__footer-inner">
          <div class="config__footer-status">
            <span class="dot dot--warn"></span>
            {{ t('common.unsavedChanges') }}
          </div>
          <div class="config__footer-actions">
            <AppButton variant="ghost" :disabled="saving" @click="reset">{{ t('common.reset') }}</AppButton>
            <AppButton variant="gradient" :loading="saving" @click="save">{{ t('common.saveChanges') }}</AppButton>
          </div>
        </div>
      </footer>
    </transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import AppToggle from '../components/AppToggle.vue'
import DiscordMessagePreview from '../components/DiscordMessagePreview.vue'
import EmbedEditor from '../components/EmbedEditor.vue'
import ChannelSelector from '../components/ChannelSelector.vue'
import { PLACEHOLDERS, insertAtCaret } from '../components/embedPlaceholders.js'
import { useGuildSettings } from '../stores/guildSettings.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const store = useGuildSettings()
const toast = useToast()
const { t } = useI18n()

const guildId = computed(() => route.params.guild_id)

const form = reactive({
  leave_enabled: false,
  leave_channel_id: '',
  leave_message: '{user} has left the server.',
  leave_use_embed: false,
  leave_embed: store.defaultEmbed(),
  leave_delete_after: 0
})

let initial = JSON.stringify(form)
const saving = ref(false)
const messageRef = ref(null)

const guildName = computed(() => {
  const g = store.cache.guild
  return g?.guild_name || g?.name || 'Your Server'
})

const dirty = computed(() => JSON.stringify(form) !== initial)

function clamp(v) {
  const n = Number.parseInt(v, 10)
  if (!Number.isFinite(n) || n < 0) return 0
  if (n > 600) return 600
  return n
}

function hydrateFromCache() {
  const s = store.cache.settings
  if (!s) return
  form.leave_enabled = !!s.leave_enabled
  form.leave_channel_id = s.leave_channel_id || ''
  form.leave_message = s.leave_message || '{user} has left the server.'
  form.leave_use_embed = !!s.leave_use_embed
  form.leave_embed = { ...store.defaultEmbed(), ...(s.leave_embed || {}) }
  form.leave_delete_after = clamp(s.leave_delete_after)
  initial = JSON.stringify(form)
}

async function ensureLoaded() {
  if (!store.cache.settings || store.cache.guildId !== guildId.value) {
    try {
      await store.loadFull(guildId.value)
    } catch (err) {
      toast.error(t('toast.couldNotLoadSettings'))
    }
  }
  hydrateFromCache()
}

onMounted(ensureLoaded)
watch(() => store.cache.settings, hydrateFromCache, { deep: false })
watch(() => guildId.value, ensureLoaded)

watch(() => form.leave_delete_after, (v) => {
  const c = clamp(v)
  if (c !== v) form.leave_delete_after = c
})

async function insertIntoMessage(token) {
  if (!form.leave_enabled) return
  const el = messageRef.value
  const { value, caret } = insertAtCaret(el, form.leave_message, token)
  form.leave_message = value
  await nextTick()
  if (el) {
    el.focus()
    try { el.setSelectionRange(caret, caret) } catch {
      // setSelectionRange isn't supported on every element — safe to ignore.
    }
  }
}

function reset() {
  hydrateFromCache()
  toast.info(t('toast.revertedChanges'))
}

async function save() {
  saving.value = true
  try {
    await store.saveSettings(guildId.value, {
      leave_enabled: form.leave_enabled,
      leave_channel_id: form.leave_channel_id,
      leave_message: form.leave_message,
      leave_use_embed: form.leave_use_embed,
      leave_embed: form.leave_embed,
      leave_delete_after: clamp(form.leave_delete_after)
    })
    hydrateFromCache()
    toast.success(t('leave.saved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.config__head {
  margin-bottom: var(--space-6);
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

.config__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.config__preview {
  position: sticky;
  top: calc(var(--nav-height) + var(--space-6));
}

.config__preview-label {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-soft);
  margin-bottom: var(--space-3);
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

.form-card.is-disabled {
  opacity: 0.65;
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

.form-row__hint :deep(code),
.form-row__hint code {
  font-family: var(--font-mono);
  background: var(--color-surface-2);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.82rem;
  color: var(--color-accent);
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

.input:disabled {
  background: var(--color-surface);
  cursor: not-allowed;
  opacity: 0.7;
}

.input--mono {
  font-family: var(--font-mono);
  letter-spacing: 0.02em;
}

.input--textarea {
  resize: vertical;
  min-height: 110px;
  line-height: 1.55;
}

.input--num {
  width: 100px;
  text-align: right;
  font-family: var(--font-mono);
}

.segmented {
  display: inline-flex;
  gap: var(--space-2);
}

.placeholder-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.placeholder-bar__chip {
  padding: 0.3rem 0.55rem;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--color-accent);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
}

.placeholder-bar__chip:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-surface-3);
}

.placeholder-bar__chip:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.delete-after-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.slider {
  flex: 1;
  min-width: 160px;
  height: 6px;
  appearance: none;
  -webkit-appearance: none;
  background: var(--color-surface-3);
  border-radius: var(--radius-full);
  outline: none;
  cursor: pointer;
}
.slider::-webkit-slider-thumb {
  appearance: none;
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-primary);
  border: 2px solid #fff;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
}
.slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-primary);
  border: 2px solid #fff;
  cursor: pointer;
}
.slider:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.delete-after-suffix {
  font-size: 0.82rem;
  color: var(--color-text-muted);
  white-space: nowrap;
}

.config__footer {
  position: sticky;
  bottom: var(--space-4);
  margin-top: var(--space-6);
  z-index: 10;
}

.config__footer-inner {
  background: rgba(22, 26, 35, 0.85);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-xl);
  padding: var(--space-3) var(--space-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  box-shadow: var(--shadow-lg);
}

.config__footer-status {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-muted);
  font-size: 0.88rem;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot--ok {
  background: var(--color-success);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}
.dot--warn {
  background: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

.config__footer-actions {
  display: flex;
  gap: var(--space-3);
}

@media (max-width: 1100px) {
  .config__grid {
    grid-template-columns: 1fr;
  }
  .config__preview {
    position: static;
  }
}

@media (max-width: 640px) {
  .config__footer-inner {
    flex-direction: column;
    align-items: stretch;
  }
  .config__footer-actions {
    justify-content: stretch;
  }
  .config__footer-actions > * {
    flex: 1;
  }
}
</style>
