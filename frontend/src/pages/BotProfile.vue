<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('botProfile.eyebrow') }}</div>
      <h1 class="config__title">{{ t('botProfile.title') }}</h1>
      <p class="config__sub">{{ t('botProfile.sub') }}</p>
    </header>

    <section class="form-card">
      <!-- Nickname -->
      <div class="row">
        <label class="row__label" for="bp-nick">{{ t('botProfile.nicknameLabel') }}</label>
        <div class="row__hint">{{ t('botProfile.nicknameHint') }}</div>
        <input
          id="bp-nick"
          v-model="form.nickname"
          class="input"
          type="text"
          maxlength="32"
          :placeholder="t('botProfile.nicknamePlaceholder')"
        />
      </div>

      <!-- Avatar -->
      <div class="row">
        <label class="row__label" for="bp-avatar">{{ t('botProfile.avatarLabel') }}</label>
        <div class="row__hint">{{ t('botProfile.avatarHint') }}</div>
        <div class="avatar-row">
          <div class="avatar-preview" :class="{ 'is-empty': !previewSrc }">
            <img v-if="previewSrc" :src="previewSrc" alt="" @error="previewError = true" />
            <svg v-else width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.5-3.5L9 20"/></svg>
          </div>
          <input
            id="bp-avatar"
            v-model="form.avatar_url"
            class="input"
            type="text"
            placeholder="https://…"
          />
        </div>
        <div v-if="previewError && form.avatar_url" class="row__hint row__hint--warn">{{ t('botProfile.avatarInvalid') }}</div>
      </div>

      <!-- Last apply status -->
      <div v-if="statusText" class="status-line" :class="`status-line--${form.status || 'pending'}`">
        <span class="status-line__dot"></span>
        <span>{{ statusText }}</span>
      </div>

      <div class="form-card__note form-card__note--info">{{ t('botProfile.permNote') }}</div>

      <div class="form-card__actions">
        <AppButton variant="ghost" :disabled="saving || !dirty" @click="reset">{{ t('common.reset') }}</AppButton>
        <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.saveChanges') }}</AppButton>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { useAutoRefresh } from '../composables/useAutoRefresh.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const form = reactive({ nickname: '', avatar_url: '', status: '', status_message: '' })
const saving = ref(false)
const previewError = ref(false)
let initial = JSON.stringify({ nickname: '', avatar_url: '' })
const dirty = computed(() => JSON.stringify({ nickname: form.nickname, avatar_url: form.avatar_url }) !== initial)

const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u.trim())
const previewSrc = computed(() => (isHttp(form.avatar_url) && !previewError.value ? form.avatar_url.trim() : ''))
watch(() => form.avatar_url, () => { previewError.value = false })

// Bot writes back a comma-separated list of status codes; translate each.
const statusText = computed(() => {
  if (form.status === 'ok') return t('botProfile.statusOk')
  if (form.status === 'pending') return t('botProfile.statusPending')
  if (form.status === 'error') {
    const codes = String(form.status_message || '').split(',').map(c => c.trim()).filter(Boolean)
    if (!codes.length) return t('botProfile.statusErrorGeneric')
    return codes.map(c => t(`botProfile.err_${c}`)).join(' · ')
  }
  return ''
})

function hydrate(s) {
  form.nickname = s.nickname || ''
  form.avatar_url = s.avatar_url || ''
  form.status = s.status || ''
  form.status_message = s.status_message || ''
  previewError.value = false
  initial = JSON.stringify({ nickname: form.nickname, avatar_url: form.avatar_url })
}

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/botprofile`)
    if (data?.success) hydrate(data.settings || {})
  } catch (err) {
    toast.error(t('botProfile.loadError'))
  }
}

onMounted(load)
watch(guildId, load)
// Keep the apply-status fresh (the bot writes it back a moment after saving).
useAutoRefresh(load, { isDirty: () => dirty.value })

function reset() { hydrate({ nickname: JSON.parse(initial).nickname, avatar_url: JSON.parse(initial).avatar_url, status: form.status, status_message: form.status_message }) }

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/botprofile`, {
      nickname: form.nickname.trim(),
      avatar_url: form.avatar_url.trim()
    })
    if (data?.success && data.settings) hydrate(data.settings)
    toast.success(t('botProfile.saved'))
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

.form-card {
  max-width: 720px;
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
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }
.row__hint--warn { color: var(--color-warning); }

.input {
  width: 100%;
  padding: 0.7rem 0.85rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.95rem;
}
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }

.avatar-row { display: flex; align-items: center; gap: var(--space-3); }
.avatar-preview {
  width: 56px; height: 56px; flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  background: var(--color-bg-elevated);
  display: flex; align-items: center; justify-content: center;
  color: var(--color-text-soft);
}
.avatar-preview img { width: 100%; height: 100%; object-fit: cover; }

.status-line {
  display: flex; align-items: center; gap: var(--space-2);
  font-size: 0.85rem;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-elevated);
}
.status-line__dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: var(--color-text-soft); }
.status-line--ok { color: var(--color-success); border-color: rgba(34, 197, 94, 0.3); }
.status-line--ok .status-line__dot { background: var(--color-success); }
.status-line--error { color: var(--color-danger); border-color: rgba(239, 68, 68, 0.3); }
.status-line--error .status-line__dot { background: var(--color-danger); }
.status-line--pending { color: var(--color-warning); }
.status-line--pending .status-line__dot { background: var(--color-warning); }

.form-card__note {
  font-size: 0.82rem;
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  line-height: 1.5;
}
.form-card__note--info {
  color: var(--color-text-muted);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
}

.form-card__actions { display: flex; justify-content: flex-end; gap: var(--space-3); }
</style>
