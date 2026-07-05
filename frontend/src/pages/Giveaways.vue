<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('giveaways.eyebrow') }}</div>
      <h1 class="config__title">{{ t('giveaways.title') }}</h1>
      <p class="config__sub">{{ t('giveaways.sub') }}</p>
    </header>

    <div class="form-card note">{{ t('giveaways.usageNote') }}</div>

    <!-- Create form -->
    <div class="form-card gw-create">
      <div class="gw-create__head" @click="showCreate = !showCreate">
        <button
          type="button"
          class="gw-create__toggle"
          :class="{ 'is-collapsed': !showCreate }"
          :aria-expanded="showCreate"
          @click.stop="showCreate = !showCreate"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <span class="gw-create__title">🎉 {{ t('giveaways.createTitle') }}</span>
      </div>

      <div v-show="showCreate" class="gw-create__body">
        <div class="gw-grid">
          <div class="form-row gw-grid__wide">
            <label class="form-row__label">{{ t('giveaways.prizeLabel') }}</label>
            <input v-model="form.prize" class="input" type="text" maxlength="256" :placeholder="t('giveaways.prizePlaceholder')" />
          </div>
          <div class="form-row">
            <label class="form-row__label">{{ t('giveaways.winnersInputLabel') }}</label>
            <input v-model.number="form.winners_count" class="input" type="number" min="1" max="50" />
          </div>
        </div>

        <div class="gw-grid">
          <div class="form-row">
            <label class="form-row__label">{{ t('giveaways.durationLabel') }}</label>
            <div class="gw-duration">
              <input v-model.number="form.duration_value" class="input" type="number" min="1" />
              <select v-model="form.duration_unit" class="input input--narrow">
                <option value="m">{{ t('giveaways.unitMinutes') }}</option>
                <option value="h">{{ t('giveaways.unitHours') }}</option>
                <option value="d">{{ t('giveaways.unitDays') }}</option>
              </select>
            </div>
          </div>
          <div class="form-row gw-grid__wide">
            <label class="form-row__label">{{ t('giveaways.channelLabel') }}</label>
            <ChannelSelector v-model="form.channel_id" :guild-id="guildId" :types="['text', 'announcement']" />
            <div class="form-row__hint">{{ t('giveaways.channelHint') }}</div>
          </div>
        </div>

        <div class="form-row">
          <label class="form-row__label">{{ t('giveaways.descriptionLabel') }}</label>
          <textarea v-model="form.description" class="input" rows="2" maxlength="1000" :placeholder="t('giveaways.descriptionPlaceholder')"></textarea>
        </div>

        <div class="gw-req">
          <div class="gw-req__title">{{ t('giveaways.requirementsTitle') }}</div>
          <div class="gw-req__hint">{{ t('giveaways.requirementsHint') }}</div>

          <div class="form-row">
            <label class="form-row__label">{{ t('giveaways.reqRolesLabel') }}</label>
            <RoleSelector v-model="form.required_role_ids" :guild-id="guildId" multiple :placeholder="t('giveaways.reqRolesPlaceholder')" />
            <div class="form-row__hint">{{ t('giveaways.reqRolesHint') }}</div>
          </div>

          <div class="gw-grid gw-grid--3">
            <div class="form-row">
              <label class="form-row__label">{{ t('giveaways.reqAccountLabel') }}</label>
              <input v-model.number="form.min_account_age_days" class="input" type="number" min="0" max="3650" />
            </div>
            <div class="form-row">
              <label class="form-row__label">{{ t('giveaways.reqMemberLabel') }}</label>
              <input v-model.number="form.min_member_days" class="input" type="number" min="0" max="3650" />
            </div>
            <div class="form-row">
              <label class="form-row__label">{{ t('giveaways.reqLevelLabel') }}</label>
              <input v-model.number="form.min_level" class="input" type="number" min="0" max="1000" />
            </div>
          </div>
        </div>

        <div class="gw-create__actions">
          <AppButton variant="gradient" :loading="creating" @click="createGiveaway">{{ t('giveaways.createButton') }}</AppButton>
        </div>
      </div>
    </div>

    <div v-if="loading && rows.length === 0" class="form-card state">{{ t('common.loading') }}</div>
    <div v-else-if="!loading && rows.length === 0" class="form-card empty">
      <div class="empty__title">{{ t('giveaways.emptyTitle') }}</div>
      <div class="empty__body">{{ t('giveaways.emptyBody') }}</div>
    </div>

    <div v-else class="gw-list">
      <div v-for="g in rows" :key="g.id" class="form-card gw-row">
        <div class="gw-row__main">
          <div class="gw-row__prize">🎉 {{ g.prize || '—' }}</div>
          <div class="gw-row__meta">
            <span class="gw-row__badge" :class="statusClass(g)">{{ statusLabel(g) }}</span>
            <span>{{ t('giveaways.winnersLabel', { count: g.winners_count }) }}</span>
            <span class="gw-row__time">{{ formatEnds(g.ends_at) }}</span>
          </div>
          <div v-if="requirementChips(g).length" class="gw-row__reqs">
            <span v-for="(chip, i) in requirementChips(g)" :key="i" class="gw-row__chip">{{ chip }}</span>
          </div>
        </div>
        <AppButton variant="danger" :loading="deletingIds.has(g.id)" @click="confirmDelete(g)">{{ t('giveaways.delete') }}</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import ChannelSelector from '../components/ChannelSelector.vue'
import RoleSelector from '../components/RoleSelector.vue'
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'
import { useAutoRefresh } from '../composables/useAutoRefresh.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const rows = ref([])
const loading = ref(false)
const deletingIds = reactive(new Set())
const showCreate = ref(false)
const creating = ref(false)

const UNIT_SECONDS = { m: 60, h: 3600, d: 86400 }

function emptyForm() {
  return {
    prize: '',
    winners_count: 1,
    duration_value: 1,
    duration_unit: 'h',
    channel_id: '',
    description: '',
    required_role_ids: [],
    min_account_age_days: 0,
    min_member_days: 0,
    min_level: 0
  }
}
const form = reactive(emptyForm())

function statusClass(g) {
  if (g.ended) return 'is-ended'
  if (!g.message_id) return 'is-pending'
  return 'is-active'
}
function statusLabel(g) {
  if (g.ended) return t('giveaways.ended')
  if (!g.message_id) return t('giveaways.pending')
  return t('giveaways.active')
}

function requirementChips(g) {
  const chips = []
  const roles = Array.isArray(g.required_role_ids) ? g.required_role_ids : []
  if (roles.length) chips.push(t('giveaways.reqChipRole', { count: roles.length }))
  if (g.min_account_age_days > 0) chips.push(t('giveaways.reqChipAccount', { days: g.min_account_age_days }))
  if (g.min_member_days > 0) chips.push(t('giveaways.reqChipMember', { days: g.min_member_days }))
  if (g.min_level > 0) chips.push(t('giveaways.reqChipLevel', { level: g.min_level }))
  return chips
}

function formatEnds(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const now = Date.now()
  const prefix = ts * 1000 > now ? t('giveaways.endsIn') : t('giveaways.endedAt')
  return `${prefix} ${d.toLocaleString()}`
}

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/giveaways`)
    rows.value = (data?.success && Array.isArray(data.giveaways)) ? data.giveaways : []
  } catch (err) {
    rows.value = []
    toast.error(t('giveaways.loadError'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(guildId, load)
// Auto-refresh the giveaway list; skip while the create panel is open (the
// refresh only touches `rows`, but this keeps parity with the draft pattern).
useAutoRefresh(load, { isDirty: () => showCreate.value })

async function createGiveaway() {
  const durationSeconds = Math.floor((form.duration_value || 0) * (UNIT_SECONDS[form.duration_unit] || 60))
  if (!form.prize.trim() || !form.channel_id || !(form.winners_count >= 1) || durationSeconds < 30) {
    toast.error(t('giveaways.validationError'))
    return
  }
  creating.value = true
  try {
    await api.post(`/guilds/${guildId.value}/giveaways`, {
      channel_id: form.channel_id,
      prize: form.prize.trim(),
      winners_count: form.winners_count,
      duration_seconds: durationSeconds,
      description: form.description.trim(),
      required_role_ids: form.required_role_ids,
      min_account_age_days: form.min_account_age_days || 0,
      min_member_days: form.min_member_days || 0,
      min_level: form.min_level || 0
    })
    toast.success(t('giveaways.createdToast'))
    Object.assign(form, emptyForm())
    showCreate.value = false
    await load()
  } catch (err) {
    toast.error(err.response?.data?.message || err.response?.data?.error || t('giveaways.createError'))
  } finally {
    creating.value = false
  }
}

async function confirmDelete(g) {
  if (typeof window !== 'undefined' && !window.confirm(t('giveaways.deleteConfirm'))) return
  deletingIds.add(g.id)
  try {
    await api.delete(`/guilds/${guildId.value}/giveaways/${g.id}`)
    rows.value = rows.value.filter(r => r.id !== g.id)
    toast.success(t('giveaways.deleted'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingIds.delete(g.id)
  }
}
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }
.form-card { max-width: 820px; background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5) var(--space-6); box-shadow: var(--shadow-inset); }
.note { color: var(--color-text-muted); font-size: 0.88rem; margin-bottom: var(--space-5); }
.state, .empty { text-align: center; color: var(--color-text-muted); }
.empty__title { font-family: var(--font-display); font-size: 1.05rem; font-weight: 600; margin-bottom: var(--space-2); color: var(--color-text); }

.gw-create { margin-bottom: var(--space-5); }
.gw-create__head { display: flex; align-items: center; gap: var(--space-2); cursor: pointer; }
.gw-create__toggle { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; color: var(--color-text-soft); border-radius: var(--radius-sm); transition: color var(--transition), background var(--transition), transform var(--transition); }
.gw-create__toggle:hover { color: var(--color-primary); background: var(--color-surface-2); }
.gw-create__toggle.is-collapsed { transform: rotate(-90deg); }
.gw-create__title { font-weight: 600; font-size: 1.02rem; }
.gw-create__body { display: flex; flex-direction: column; gap: var(--space-4); margin-top: var(--space-4); }
.gw-create__actions { display: flex; justify-content: flex-end; }

.gw-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.gw-grid--3 { grid-template-columns: 1fr 1fr 1fr; }
.gw-grid__wide { grid-column: span 1; }
.gw-duration { display: grid; grid-template-columns: 1fr auto; gap: var(--space-2); }

.gw-req { border: 1px dashed var(--color-border-strong); border-radius: var(--radius-lg); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }
.gw-req__title { font-weight: 600; font-size: 0.95rem; }
.gw-req__hint { font-size: 0.82rem; color: var(--color-text-muted); margin-top: calc(-1 * var(--space-3)); }

.form-row { display: flex; flex-direction: column; gap: var(--space-2); }
.form-row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.form-row__hint { font-size: 0.82rem; color: var(--color-text-muted); }
.input { width: 100%; padding: 0.6rem 0.8rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.92rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--narrow { max-width: 130px; }
textarea.input { resize: vertical; }

.gw-list { display: flex; flex-direction: column; gap: var(--space-3); }
.gw-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
.gw-row__main { min-width: 0; }
.gw-row__prize { font-weight: 600; font-size: 1.02rem; margin-bottom: 4px; }
.gw-row__meta { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; font-size: 0.84rem; color: var(--color-text-muted); }
.gw-row__badge { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; padding: 2px 8px; border-radius: var(--radius-sm); color: #fff; }
.gw-row__badge.is-active { background: var(--color-success); }
.gw-row__badge.is-pending { background: var(--color-warning); }
.gw-row__badge.is-ended { background: var(--color-text-soft); }
.gw-row__time { font-family: var(--font-mono); font-size: 0.78rem; }
.gw-row__reqs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.gw-row__chip { font-size: 0.72rem; padding: 2px 8px; border-radius: var(--radius-sm); background: var(--color-surface-2); border: 1px solid var(--color-border-strong); color: var(--color-text-muted); }

@media (max-width: 640px) {
  .gw-grid, .gw-grid--3 { grid-template-columns: 1fr; }
}
</style>
