<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('birthday.eyebrow') }}</div>
      <h1 class="config__title">{{ t('birthday.title') }}</h1>
      <p class="config__sub">{{ t('birthday.sub') }}</p>
    </header>

    <section class="form-card">
      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('birthday.enableLabel') }}</div>
          <div class="row__hint">{{ t('birthday.enableHint') }}</div>
        </div>
        <AppToggle v-model="form.enabled" />
      </div>

      <div class="row">
        <label class="row__label">{{ t('birthday.channelLabel') }}</label>
        <div class="row__hint">{{ t('birthday.channelHint') }}</div>
        <ChannelSelector v-model="form.announce_channel_id" :guild-id="guildId" :types="['text', 'announcement']" />
      </div>

      <div class="row">
        <label class="row__label" for="bd-msg">{{ t('birthday.messageLabel') }}</label>
        <div class="row__hint">{{ t('birthday.messageHint') }}</div>
        <input id="bd-msg" v-model="form.message_template" class="input" type="text" maxlength="1000" placeholder="🎉 Happy Birthday {user}!" />
      </div>

      <div class="row">
        <label class="row__label">{{ t('birthday.roleLabel') }}</label>
        <div class="row__hint">{{ t('birthday.roleHint') }}</div>
        <RoleSelector v-model="form.birthday_role_id" :guild-id="guildId" :placeholder="t('birthday.rolePlaceholder')" />
      </div>

      <div class="form-card__note form-card__note--info">{{ t('birthday.usageNote') }}</div>

      <div class="form-card__actions">
        <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.saveChanges') }}</AppButton>
      </div>
    </section>

    <section class="list-card">
      <h2 class="list-card__title">{{ t('birthday.listTitle') }}</h2>
      <div v-if="birthdays.length === 0" class="list-card__empty">{{ t('birthday.listEmpty') }}</div>
      <ul v-else class="bd-list">
        <li v-for="b in birthdays" :key="b.user_id" class="bd-list__item">
          <span class="bd-list__date">{{ String(b.day).padStart(2,'0') }}.{{ String(b.month).padStart(2,'0') }}<span v-if="b.year">.{{ b.year }}</span></span>
          <span class="bd-list__user">{{ b.user_id }}</span>
          <button class="bd-list__del" :title="t('birthday.remove')" @click="removeOne(b.user_id)">✕</button>
        </li>
      </ul>
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
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const form = reactive({ enabled: false, announce_channel_id: '', message_template: '🎉 Happy Birthday {user}!', birthday_role_id: '' })
const saving = ref(false)
const birthdays = ref([])
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

async function load() {
  if (!guildId.value) return
  try {
    const [{ data }, listRes] = await Promise.all([
      api.get(`/guilds/${guildId.value}/birthday`),
      api.get(`/guilds/${guildId.value}/birthday/list`).catch(() => ({ data: null }))
    ])
    if (data?.success) {
      const s = data.settings || {}
      form.enabled = !!s.enabled
      form.announce_channel_id = s.announce_channel_id || ''
      form.message_template = s.message_template || '🎉 Happy Birthday {user}!'
      form.birthday_role_id = s.birthday_role_id || ''
      initial = JSON.stringify(form)
    }
    birthdays.value = listRes.data?.success ? (listRes.data.birthdays || []) : []
  } catch (err) {
    toast.error(t('birthday.loadError'))
  }
}

onMounted(load)
watch(guildId, load)

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/birthday`, {
      enabled: !!form.enabled,
      announce_channel_id: form.announce_channel_id || null,
      message_template: form.message_template || '🎉 Happy Birthday {user}!',
      birthday_role_id: form.birthday_role_id || null
    })
    if (data?.success && data.settings) {
      Object.assign(form, {
        enabled: !!data.settings.enabled,
        announce_channel_id: data.settings.announce_channel_id || '',
        message_template: data.settings.message_template || '🎉 Happy Birthday {user}!',
        birthday_role_id: data.settings.birthday_role_id || ''
      })
      initial = JSON.stringify(form)
    }
    toast.success(t('common.allSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}

async function removeOne(userId) {
  try {
    await api.delete(`/guilds/${guildId.value}/birthday/list/${userId}`)
    birthdays.value = birthdays.value.filter(b => b.user_id !== userId)
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  }
}
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }

.form-card, .list-card {
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
.list-card { margin-top: var(--space-5); gap: var(--space-4); }
.list-card__title { font-family: var(--font-display); font-size: 1.1rem; font-weight: 600; }
.list-card__empty { color: var(--color-text-muted); font-size: 0.92rem; }

.row { display: flex; flex-direction: column; gap: var(--space-2); }
.row--toggle { flex-direction: row; align-items: center; justify-content: space-between; gap: var(--space-4); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }

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

.form-card__note { font-size: 0.82rem; border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); line-height: 1.5; }
.form-card__note--info { color: var(--color-text-muted); background: var(--color-bg-elevated); border: 1px solid var(--color-border); }
.form-card__actions { display: flex; justify-content: flex-end; }

.bd-list { display: flex; flex-direction: column; gap: var(--space-2); list-style: none; }
.bd-list__item { display: flex; align-items: center; gap: var(--space-3); padding: 0.5rem 0.75rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.bd-list__date { font-family: var(--font-mono); font-weight: 700; color: var(--color-accent); }
.bd-list__user { font-family: var(--font-mono); font-size: 0.82rem; color: var(--color-text-muted); flex: 1; overflow: hidden; text-overflow: ellipsis; }
.bd-list__del { color: var(--color-text-soft); padding: 0 6px; border-radius: 4px; }
.bd-list__del:hover { color: var(--color-danger); background: var(--color-surface-2); }
</style>
