<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('applications.eyebrow') }}</div>
      <h1 class="config__title">{{ t('applications.title') }}</h1>
      <p class="config__sub">{{ t('applications.sub') }}</p>
    </header>

    <div class="form-card note">{{ t('applications.usageNote') }}</div>

    <!-- Forms -->
    <section class="form-card">
      <div class="shop-head">
        <h2 class="shop-head__title">{{ t('applications.formsTitle') }}</h2>
        <AppButton variant="ghost" :loading="addingForm" @click="addForm">{{ t('applications.addForm') }}</AppButton>
      </div>

      <div v-if="forms.length === 0" class="lb-empty">{{ t('applications.formsEmpty') }}</div>
      <div v-else class="form-list">
        <div v-for="f in forms" :key="f.id" class="form-row">
          <div class="row-grid">
            <div class="row">
              <label class="row__label">{{ t('applications.nameLabel') }}</label>
              <input v-model="f.name" class="input" type="text" maxlength="100" />
            </div>
            <div class="row">
              <label class="row__label">{{ t('applications.buttonLabel') }}</label>
              <input v-model="f.button_label" class="input" type="text" maxlength="80" />
            </div>
          </div>
          <div class="row">
            <label class="row__label">{{ t('applications.descLabel') }}</label>
            <input v-model="f.description" class="input" type="text" maxlength="1000" />
          </div>
          <div class="row-grid">
            <div class="row">
              <label class="row__label">{{ t('applications.reviewChannelLabel') }}</label>
              <ChannelSelector v-model="f.review_channel_id" :guild-id="guildId" :types="['text', 'announcement']" />
            </div>
            <div class="row">
              <label class="row__label">{{ t('applications.roleLabel') }}</label>
              <RoleSelector v-model="f.accepted_role_id" :guild-id="guildId" />
            </div>
          </div>
          <div class="row">
            <label class="row__label">{{ t('applications.questionsLabel') }} <span class="muted">({{ f.questions.length }}/5)</span></label>
            <div v-for="(q, qi) in f.questions" :key="qi" class="q-row">
              <input v-model="f.questions[qi]" class="input" type="text" maxlength="300" :placeholder="t('applications.questionPlaceholder', { n: qi + 1 })" />
              <button class="q-remove" type="button" @click="f.questions.splice(qi, 1)">✕</button>
            </div>
            <AppButton v-if="f.questions.length < 5" variant="ghost" @click="f.questions.push('')">{{ t('applications.addQuestion') }}</AppButton>
          </div>
          <div class="shop-row__foot">
            <label class="inline-toggle"><AppToggle v-model="f.enabled" /> {{ t('common.enabled') }}</label>
            <div class="shop-row__actions">
              <AppButton variant="ghost" :loading="savingForms.has(f.id)" @click="saveForm(f)">{{ t('common.save') }}</AppButton>
              <AppButton variant="danger" :loading="deletingForms.has(f.id)" @click="deleteForm(f)">{{ t('common.delete') }}</AppButton>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Submissions -->
    <section class="form-card">
      <div class="shop-head">
        <h2 class="shop-head__title">{{ t('applications.submissionsTitle') }}</h2>
        <select v-model="statusFilter" class="input input--narrow" @change="loadSubmissions">
          <option value="">{{ t('applications.statusAll') }}</option>
          <option value="pending">{{ t('applications.statusPending') }}</option>
          <option value="accepted">{{ t('applications.statusAccepted') }}</option>
          <option value="denied">{{ t('applications.statusDenied') }}</option>
        </select>
      </div>
      <div v-if="submissions.length === 0" class="lb-empty">{{ t('applications.submissionsEmpty') }}</div>
      <div v-else class="sub-list">
        <div v-for="s in submissions" :key="s.id" class="sub-row">
          <div class="sub-row__head">
            <span class="sub-row__form">{{ s.form_name || '—' }}</span>
            <span class="sub-badge" :class="`is-${s.status}`">{{ t(`applications.status${capitalize(s.status)}`) }}</span>
          </div>
          <div class="sub-row__user mono">{{ s.user_id }}</div>
          <div v-for="(a, ai) in s.answers" :key="ai" class="sub-row__qa">
            <div class="sub-row__q">{{ a.q }}</div>
            <div class="sub-row__a">{{ a.a }}</div>
          </div>
        </div>
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
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const forms = ref([])
const submissions = ref([])
const statusFilter = ref('')
const addingForm = ref(false)
const savingForms = reactive(new Set())
const deletingForms = reactive(new Set())

function capitalize(s) { return (s || '').charAt(0).toUpperCase() + (s || '').slice(1) }

function normalizeForm(f) {
  return { ...f, questions: Array.isArray(f.questions) ? [...f.questions] : [], review_channel_id: f.review_channel_id || '', accepted_role_id: f.accepted_role_id || '' }
}

async function loadForms() {
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/applications/forms`)
    forms.value = (data?.success && Array.isArray(data.forms)) ? data.forms.map(normalizeForm) : []
  } catch (err) {
    forms.value = []
    toast.error(t('applications.loadError'))
  }
}

async function loadSubmissions() {
  try {
    const q = statusFilter.value ? `?status=${statusFilter.value}` : ''
    const { data } = await api.get(`/guilds/${guildId.value}/applications/submissions${q}`)
    submissions.value = (data?.success && Array.isArray(data.submissions)) ? data.submissions : []
  } catch { submissions.value = [] }
}

async function load() {
  if (!guildId.value) return
  await loadForms()
  await loadSubmissions()
}

onMounted(load)
watch(guildId, load)

async function addForm() {
  addingForm.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/applications/forms`, { name: t('applications.newForm'), questions: [''], enabled: true })
    if (data?.success && data.form) forms.value.push(normalizeForm(data.form))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    addingForm.value = false
  }
}

async function saveForm(f) {
  savingForms.add(f.id)
  try {
    await api.put(`/guilds/${guildId.value}/applications/forms/${f.id}`, {
      name: f.name, description: f.description,
      questions: f.questions.map(q => (q || '').trim()).filter(Boolean),
      review_channel_id: f.review_channel_id || null,
      accepted_role_id: f.accepted_role_id || null,
      button_label: f.button_label, enabled: !!f.enabled
    })
    toast.success(t('common.allSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    savingForms.delete(f.id)
  }
}

async function deleteForm(f) {
  if (typeof window !== 'undefined' && !window.confirm(t('applications.deleteFormConfirm'))) return
  deletingForms.add(f.id)
  try {
    await api.delete(`/guilds/${guildId.value}/applications/forms/${f.id}`)
    forms.value = forms.value.filter(r => r.id !== f.id)
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingForms.delete(f.id)
  }
}
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }
.form-card { max-width: 820px; background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-6); box-shadow: var(--shadow-inset); display: flex; flex-direction: column; gap: var(--space-5); margin-bottom: var(--space-5); }
.note { color: var(--color-text-muted); font-size: 0.88rem; }
.row { display: flex; flex-direction: column; gap: var(--space-2); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.muted { color: var(--color-text-soft); font-weight: 400; }
.row-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); align-items: start; }
.input { width: 100%; padding: 0.7rem 0.85rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.95rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--narrow { max-width: 180px; }
.shop-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
.shop-head__title { font-size: 1.1rem; }
.form-list { display: flex; flex-direction: column; gap: var(--space-4); }
.form-row { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); background: var(--color-bg-elevated); }
.q-row { display: flex; gap: var(--space-2); align-items: center; }
.q-remove { flex-shrink: 0; width: 36px; height: 36px; border-radius: var(--radius-sm); border: 1px solid var(--color-border-strong); background: var(--color-surface); color: var(--color-text-muted); cursor: pointer; }
.q-remove:hover { color: var(--color-danger); }
.shop-row__foot { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.shop-row__actions { display: flex; gap: var(--space-2); }
.inline-toggle { display: inline-flex; align-items: center; gap: var(--space-2); font-size: 0.85rem; color: var(--color-text-muted); }
.lb-empty { color: var(--color-text-muted); font-size: 0.9rem; }
.sub-list { display: flex; flex-direction: column; gap: var(--space-3); }
.sub-row { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-4); background: var(--color-bg-elevated); }
.sub-row__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: 4px; }
.sub-row__form { font-weight: 600; }
.sub-badge { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; padding: 2px 8px; border-radius: var(--radius-sm); color: #fff; }
.sub-badge.is-pending { background: var(--color-text-soft); }
.sub-badge.is-accepted { background: var(--color-success); }
.sub-badge.is-denied { background: var(--color-danger); }
.sub-row__user { font-size: 0.8rem; color: var(--color-text-muted); margin-bottom: var(--space-2); }
.mono { font-family: var(--font-mono); }
.sub-row__qa { margin-top: var(--space-2); }
.sub-row__q { font-size: 0.82rem; font-weight: 600; color: var(--color-text); }
.sub-row__a { font-size: 0.86rem; color: var(--color-text-muted); white-space: pre-wrap; }
@media (max-width: 560px) { .row-grid { grid-template-columns: 1fr; } }
</style>
