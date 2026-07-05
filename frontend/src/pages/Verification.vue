<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('verification.eyebrow') }}</div>
      <h1 class="config__title">{{ t('verification.title') }}</h1>
      <p class="config__sub">{{ t('verification.sub') }}</p>
    </header>

    <div class="config__grid">
      <section class="config__form">
        <div class="form-card">
          <div class="row row--toggle">
            <div>
              <div class="row__label">{{ t('verification.enableLabel') }}</div>
              <div class="row__hint">{{ t('verification.enableHint') }}</div>
            </div>
            <AppToggle v-model="form.enabled" />
          </div>

          <div class="row">
            <label class="row__label">{{ t('verification.channelLabel') }}</label>
            <div class="row__hint">{{ t('verification.channelHint') }}</div>
            <ChannelSelector v-model="form.channel_id" :guild-id="guildId" :types="['text', 'announcement']" />
          </div>

          <div class="row">
            <label class="row__label">{{ t('verification.roleLabel') }}</label>
            <div class="row__hint">{{ t('verification.roleHint') }}</div>
            <RoleSelector v-model="form.verified_role_id" :guild-id="guildId" :placeholder="t('verification.rolePlaceholder')" />
          </div>

          <!-- Message mode: plain text or a designed embed -->
          <div class="row">
            <label class="row__label">{{ t('verification.messageModeLabel') }}</label>
            <div class="mode">
              <button type="button" class="mode__btn" :class="{ 'is-active': !form.use_embed }" @click="form.use_embed = false">{{ t('verification.messageModePlain') }}</button>
              <button type="button" class="mode__btn" :class="{ 'is-active': form.use_embed }" @click="form.use_embed = true">{{ t('verification.messageModeEmbed') }}</button>
            </div>
            <div class="row__hint">{{ t('verification.messageModeHint') }}</div>
          </div>

          <div v-if="!form.use_embed" class="row">
            <label class="row__label" for="vf-msg">{{ t('verification.messageLabel') }}</label>
            <textarea id="vf-msg" v-model="form.message" class="input input--textarea" rows="3" maxlength="2000"></textarea>
          </div>

          <div v-else class="row">
            <label class="row__label">{{ t('verification.embedLabel') }}</label>
            <div class="row__hint">{{ t('verification.embedHint') }}</div>
            <EmbedEditor v-model="form.embed" />
          </div>

          <div class="row">
            <label class="row__label" for="vf-btn">{{ t('verification.buttonLabel') }}</label>
            <input id="vf-btn" v-model="form.button_label" class="input input--narrow" type="text" maxlength="80" placeholder="Verify" />
          </div>

          <div class="form-card__note form-card__note--info">{{ t('verification.usageNote') }}</div>

          <div class="form-card__actions">
            <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.saveChanges') }}</AppButton>
          </div>
        </div>
      </section>

      <aside class="config__preview">
        <div class="preview__label">{{ t('verification.livePreview') }}</div>
        <DiscordMessagePreview mode="embed" :embed="previewEmbed" channel-name="verify">
          <template #components>
            <div class="dc-row">
              <span class="dc-btn dc-btn--success"><span class="dc-btn__emoji">✅</span>{{ form.button_label || 'Verify' }}</span>
            </div>
          </template>
        </DiscordMessagePreview>
      </aside>
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
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { useAutoRefresh } from '../composables/useAutoRefresh.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const VERIFY_COLOR = '#22C55E'
function defaultEmbed() {
  return { title: '', description: '', color: VERIFY_COLOR, thumbnail: '', image: '', footer: '', show_timestamp: false, author_name: '', author_icon_url: '' }
}

const form = reactive({
  enabled: false, channel_id: '', verified_role_id: '',
  message: 'Click the button below to verify and unlock the server.',
  button_label: 'Verify', use_embed: false, embed: defaultEmbed()
})
const saving = ref(false)
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

// Mirror what the bot posts: plain mode → author "Verification" + message.
const previewEmbed = computed(() => {
  if (form.use_embed) return form.embed
  return { ...defaultEmbed(), author_name: t('verification.author'), description: form.message || t('verification.defaultMessage') }
})

function hydrate(s) {
  form.enabled = !!s.enabled
  form.channel_id = s.channel_id || ''
  form.verified_role_id = s.verified_role_id || ''
  form.message = s.message || form.message
  form.button_label = s.button_label || 'Verify'
  form.use_embed = !!s.use_embed
  form.embed = { ...defaultEmbed(), ...(s.embed || {}) }
  initial = JSON.stringify(form)
}

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/verification`)
    if (data?.success) hydrate(data.settings || {})
  } catch (err) {
    toast.error(t('verification.loadError'))
  }
}

onMounted(load)
watch(guildId, load)
useAutoRefresh(load, { isDirty: () => dirty.value })

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/verification`, {
      enabled: !!form.enabled,
      channel_id: form.channel_id || null,
      verified_role_id: form.verified_role_id || null,
      message: form.message,
      button_label: form.button_label || 'Verify',
      use_embed: !!form.use_embed,
      embed: form.embed
    })
    if (data?.success && data.settings) hydrate(data.settings)
    toast.success(t('common.allSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }

/* Form left, sticky live-preview right — like the welcome/leave pages. */
.config__grid { display: grid; grid-template-columns: 1.15fr 1fr; gap: var(--space-5); align-items: flex-start; }
.config__form { display: flex; flex-direction: column; gap: var(--space-4); min-width: 0; }
.config__preview { position: sticky; top: calc(var(--nav-height) + var(--space-6)); min-width: 0; }
@media (max-width: 1100px) {
  .config__grid { grid-template-columns: 1fr; }
  .config__preview { position: static; }
}

.form-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-inset);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.row { display: flex; flex-direction: column; gap: var(--space-2); }
.row--toggle { flex-direction: row; align-items: center; justify-content: space-between; gap: var(--space-4); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }
.input {
  width: 100%; padding: 0.7rem 0.85rem; background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong); border-radius: var(--radius-md);
  color: var(--color-text); font-family: var(--font-sans); font-size: 0.95rem;
}
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--textarea { resize: vertical; min-height: 70px; line-height: 1.5; }
.input--narrow { max-width: 220px; }
.mode { display: inline-flex; gap: 4px; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); padding: 3px; width: fit-content; }
.mode__btn { padding: 0.45rem 0.9rem; border-radius: var(--radius-sm); font-size: 0.88rem; font-weight: 600; color: var(--color-text-muted); }
.mode__btn.is-active { background: var(--gradient-brand); color: #fff; }
.preview__label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.dc-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.dc-btn { display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 14px; border-radius: 3px; font-size: 0.86rem; font-weight: 500; color: #fff; line-height: 1; }
.dc-btn--success { background: #248046; }
.dc-btn__emoji { font-size: 0.95rem; }
.form-card__note { font-size: 0.82rem; border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); line-height: 1.5; }
.form-card__note--info { color: var(--color-text-muted); background: var(--color-bg-elevated); border: 1px solid var(--color-border); }
.form-card__actions { display: flex; justify-content: flex-end; }
</style>
