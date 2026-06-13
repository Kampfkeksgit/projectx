<template>
  <div class="config">
    <header class="config__head">
      <div>
        <div class="config__eyebrow">{{ t('autorole.eyebrow') }}</div>
        <h1 class="config__title">{{ t('autorole.title') }}</h1>
        <p class="config__sub">{{ t('autorole.sub') }}</p>
      </div>
    </header>

    <div class="config__grid config__grid--single">
      <section class="config__form">
        <div class="form-card">
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('autorole.toggleLabel') }}</div>
              <div class="form-row__hint">{{ t('autorole.toggleHint') }}</div>
            </div>
            <AppToggle v-model="form.enabled" />
          </div>
        </div>

        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <label class="form-row__label">{{ t('autorole.rolesLabel') }}</label>
            <div class="form-row__hint">{{ t('resourceSelector.rolePickHint') }}</div>
            <RoleSelector
              v-model="form.role_ids"
              :guild-id="guildId"
              :multiple="true"
              :disabled="!form.enabled"
            />
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('autorole.applyToBotsLabel') }}</div>
              <div class="form-row__hint">{{ t('autorole.applyToBotsHint') }}</div>
            </div>
            <AppToggle v-model="form.apply_to_bots" :disabled="!form.enabled" />
          </div>
        </div>
      </section>
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import AppToggle from '../components/AppToggle.vue'
import RoleSelector from '../components/RoleSelector.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()

const guildId = computed(() => route.params.guild_id)

function defaults() {
  return {
    enabled: false,
    role_ids: [],
    apply_to_bots: false
  }
}

const form = reactive(defaults())
let initial = JSON.stringify(form)
const saving = ref(false)

const dirty = computed(() => JSON.stringify(form) !== initial)

function hydrate(settings) {
  const s = settings || {}
  form.enabled = !!s.enabled
  form.role_ids = Array.isArray(s.role_ids) ? s.role_ids.slice() : []
  form.apply_to_bots = !!s.apply_to_bots
  initial = JSON.stringify(form)
}

async function load() {
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/settings/autorole`)
    if (data?.success) {
      hydrate(data.settings || defaults())
    } else {
      hydrate(defaults())
    }
  } catch (err) {
    hydrate(defaults())
    toast.error(t('toast.couldNotLoadSettings'))
  }
}

onMounted(load)
watch(() => guildId.value, load)

function reset() {
  const snapshot = JSON.parse(initial)
  form.enabled = !!snapshot.enabled
  form.role_ids = Array.isArray(snapshot.role_ids) ? snapshot.role_ids.slice() : []
  form.apply_to_bots = !!snapshot.apply_to_bots
  toast.info(t('toast.revertedChanges'))
}

async function save() {
  saving.value = true
  try {
    const body = {
      enabled: !!form.enabled,
      role_ids: form.role_ids.slice(),
      apply_to_bots: !!form.apply_to_bots
    }
    const { data } = await api.put(`/guilds/${guildId.value}/settings/autorole`, body)
    if (data?.success) {
      hydrate(data.settings || body)
    } else {
      hydrate(body)
    }
    toast.success(t('autorole.saved'))
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

.config__grid--single {
  grid-template-columns: minmax(0, 720px);
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
  .config__grid,
  .config__grid--single {
    grid-template-columns: 1fr;
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
