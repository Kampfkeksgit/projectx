<template>
  <div class="config">
    <header class="config__head">
      <div>
        <div class="config__eyebrow">{{ t('welcome.eyebrow') }}</div>
        <h1 class="config__title">{{ t('welcome.title') }}</h1>
        <p class="config__sub">{{ t('welcome.sub') }}</p>
      </div>
    </header>

    <div class="config__grid">
      <section class="config__form">
        <!-- 1. Master enable -->
        <div class="form-card">
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('welcome.toggleLabel') }}</div>
              <div class="form-row__hint">{{ t('welcome.toggleHint') }}</div>
            </div>
            <AppToggle v-model="form.welcome_enabled" />
          </div>
        </div>

        <!-- 2. Channel -->
        <div class="form-card" :class="{ 'is-disabled': !form.welcome_enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('welcome.channelLabel') }}</div>
            <div class="form-row__hint">{{ t('resourceSelector.channelPickHint') }}</div>
            <ChannelSelector
              v-model="form.welcome_channel_id"
              :guild-id="guildId"
              :types="['text', 'announcement']"
              :disabled="!form.welcome_enabled"
            />
          </div>
        </div>

        <!-- 3. Message mode -->
        <div class="form-card" :class="{ 'is-disabled': !form.welcome_enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('welcome.modeLabel') }}</div>
            <div class="segmented">
              <AppButton
                :variant="!form.welcome_use_embed ? 'gradient' : 'subtle'"
                :disabled="!form.welcome_enabled"
                @click="form.welcome_use_embed = false"
              >{{ t('welcome.modePlain') }}</AppButton>
              <AppButton
                :variant="form.welcome_use_embed ? 'gradient' : 'subtle'"
                :disabled="!form.welcome_enabled"
                @click="form.welcome_use_embed = true"
              >{{ t('welcome.modeEmbed') }}</AppButton>
            </div>
          </div>
        </div>

        <!-- 4. Plain message -->
        <div v-if="!form.welcome_use_embed" class="form-card" :class="{ 'is-disabled': !form.welcome_enabled }">
          <div class="form-row">
            <label class="form-row__label" for="welcome-message">{{ t('welcome.messageLabel') }}</label>
            <div class="form-row__hint" v-html="t('welcome.messageHintHtml')"></div>
            <textarea
              id="welcome-message"
              ref="messageRef"
              class="input input--textarea"
              :disabled="!form.welcome_enabled"
              v-model="form.welcome_message"
              rows="5"
              :placeholder="t('welcome.messagePlaceholder')"
            ></textarea>
            <div class="placeholder-bar">
              <button
                v-for="ph in PLACEHOLDERS"
                :key="ph.token"
                type="button"
                class="placeholder-bar__chip"
                :disabled="!form.welcome_enabled"
                :title="t(`embedEditor.${ph.labelKey}`)"
                @click="insertIntoMessage(ph.token)"
              >{{ ph.token }}</button>
            </div>
          </div>
        </div>

        <!-- 5. Embed -->
        <div v-else class="form-card" :class="{ 'is-disabled': !form.welcome_enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('embedEditor.sectionTitle') }}</div>
          </div>
          <EmbedEditor v-model="form.welcome_embed" :disabled="!form.welcome_enabled" />
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('welcome.pingUserLabel') }}</div>
              <div class="form-row__hint">{{ t('welcome.pingUserHint') }}</div>
            </div>
            <AppToggle v-model="form.welcome_ping_user" :disabled="!form.welcome_enabled" />
          </div>
        </div>

        <!-- 6. DM the new member -->
        <div class="form-card" :class="{ 'is-disabled': !form.welcome_enabled }">
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('welcome.dmEnabledLabel') }}</div>
              <div class="form-row__hint">{{ t('welcome.dmEnabledHint') }}</div>
            </div>
            <AppToggle v-model="form.welcome_dm_enabled" :disabled="!form.welcome_enabled" />
          </div>
          <div class="form-row" v-if="form.welcome_dm_enabled">
            <label class="form-row__label" for="welcome-dm-msg">{{ t('welcome.dmMessageLabel') }}</label>
            <div class="form-row__hint">{{ t('welcome.dmMessageHint') }}</div>
            <textarea
              id="welcome-dm-msg"
              class="input input--textarea"
              rows="4"
              maxlength="2000"
              :disabled="!form.welcome_enabled"
              v-model="form.welcome_dm_message"
              :placeholder="t('welcome.dmMessagePlaceholder')"
            ></textarea>
            <div class="placeholder-bar">
              <button
                v-for="ph in PLACEHOLDERS"
                :key="ph.token"
                type="button"
                class="placeholder-bar__chip"
                :disabled="!form.welcome_enabled"
                @click="appendToDm(ph.token)"
              >{{ ph.token }}</button>
            </div>
          </div>
        </div>

        <!-- 7. Auto-delete -->
        <div class="form-card" :class="{ 'is-disabled': !form.welcome_enabled }">
          <div class="form-row">
            <label class="form-row__label" for="welcome-delete-after">{{ t('welcome.deleteAfterLabel') }}</label>
            <div class="form-row__hint">{{ t('welcome.deleteAfterHint') }}</div>
            <div class="delete-after-row">
              <input
                id="welcome-delete-after"
                class="input input--num"
                type="number"
                min="0"
                max="600"
                step="1"
                :disabled="!form.welcome_enabled"
                v-model.number="form.welcome_delete_after"
              />
              <input
                class="slider"
                type="range"
                min="0"
                max="600"
                step="5"
                :disabled="!form.welcome_enabled"
                v-model.number="form.welcome_delete_after"
              />
              <span class="delete-after-suffix">
                {{ form.welcome_delete_after > 0
                  ? t('welcome.deleteAfterSecondsSuffix')
                  : t('welcome.deleteAfterOffSuffix') }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <aside class="config__preview">
        <div class="config__preview-label">{{ t('welcome.livePreview') }}</div>
        <DiscordMessagePreview
          :channel-name="previewChannelName"
          :message="form.welcome_message"
          :guild-name="guildName"
          :mode="form.welcome_use_embed ? 'embed' : 'plain'"
          :embed="form.welcome_embed"
          :ping-user="form.welcome_ping_user"
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
  welcome_enabled: false,
  welcome_channel_id: '',
  welcome_message: 'Welcome to {guild}, {user}!',
  welcome_use_embed: false,
  welcome_embed: store.defaultEmbed(),
  welcome_ping_user: false,
  welcome_dm_enabled: false,
  welcome_dm_message: '',
  welcome_delete_after: 0
})

let initial = JSON.stringify(form)
const saving = ref(false)
const messageRef = ref(null)

const guildName = computed(() => {
  const g = store.cache.guild
  return g?.guild_name || g?.name || 'Your Server'
})

const previewChannelName = computed(() => 'welcome')

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
  form.welcome_enabled = !!s.welcome_enabled
  form.welcome_channel_id = s.welcome_channel_id || ''
  form.welcome_message = s.welcome_message || 'Welcome to {guild}, {user}!'
  form.welcome_use_embed = !!s.welcome_use_embed
  form.welcome_embed = { ...store.defaultEmbed(), ...(s.welcome_embed || {}) }
  form.welcome_ping_user = !!s.welcome_ping_user
  form.welcome_dm_enabled = !!s.welcome_dm_enabled
  form.welcome_dm_message = s.welcome_dm_message || ''
  form.welcome_delete_after = clamp(s.welcome_delete_after)
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

// Keep the delete-after value in range even if the user types manually.
watch(() => form.welcome_delete_after, (v) => {
  const c = clamp(v)
  if (c !== v) form.welcome_delete_after = c
})

async function insertIntoMessage(token) {
  if (!form.welcome_enabled) return
  const el = messageRef.value
  const { value, caret } = insertAtCaret(el, form.welcome_message, token)
  form.welcome_message = value
  await nextTick()
  if (el) {
    el.focus()
    try { el.setSelectionRange(caret, caret) } catch {
      // setSelectionRange isn't supported on every element — safe to ignore.
    }
  }
}

function appendToDm(token) {
  if (!form.welcome_enabled) return
  form.welcome_dm_message = (form.welcome_dm_message || '') + token
}

function reset() {
  hydrateFromCache()
  toast.info(t('toast.revertedChanges'))
}

async function save() {
  saving.value = true
  try {
    await store.saveSettings(guildId.value, {
      welcome_enabled: form.welcome_enabled,
      welcome_channel_id: form.welcome_channel_id,
      welcome_message: form.welcome_message,
      welcome_use_embed: form.welcome_use_embed,
      welcome_embed: form.welcome_embed,
      welcome_ping_user: form.welcome_ping_user,
      welcome_dm_enabled: form.welcome_dm_enabled,
      welcome_dm_message: form.welcome_dm_message,
      welcome_delete_after: clamp(form.welcome_delete_after)
    })
    hydrateFromCache()
    toast.success(t('welcome.saved'))
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

/* Segmented control */
.segmented {
  display: inline-flex;
  gap: var(--space-2);
}

/* Placeholder chip bar (next to the plain message textarea) */
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

/* Delete-after row */
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

/* Footer */
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
