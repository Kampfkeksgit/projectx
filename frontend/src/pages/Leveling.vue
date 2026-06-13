<template>
  <div class="config">
    <header class="config__head">
      <div>
        <div class="config__eyebrow">{{ t('leveling.eyebrow') }}</div>
        <h1 class="config__title">{{ t('leveling.title') }}</h1>
        <p class="config__sub">{{ t('leveling.sub') }}</p>
      </div>
    </header>

    <div class="config__grid config__grid--single">
      <section class="config__form">
        <!-- Master enable -->
        <div class="form-card">
          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('leveling.toggleLabel') }}</div>
              <div class="form-row__hint">{{ t('leveling.toggleHint') }}</div>
            </div>
            <AppToggle v-model="form.enabled" />
          </div>
        </div>

        <!-- XP per message -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('leveling.xpRangeLabel') }}</div>
            <div class="form-row__hint">{{ t('leveling.xpRangeHint') }}</div>
            <div class="xp-range">
              <label class="xp-range__field">
                <span class="xp-range__label">{{ t('leveling.xpMin') }}</span>
                <input
                  class="input input--num"
                  type="number"
                  min="0"
                  max="1000"
                  :disabled="!form.enabled"
                  v-model.number="form.xp_per_message_min"
                />
              </label>
              <label class="xp-range__field">
                <span class="xp-range__label">{{ t('leveling.xpMax') }}</span>
                <input
                  class="input input--num"
                  type="number"
                  min="0"
                  max="1000"
                  :disabled="!form.enabled"
                  v-model.number="form.xp_per_message_max"
                />
              </label>
            </div>
          </div>
        </div>

        <!-- Cooldown -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <label class="form-row__label" for="lvl-cooldown">{{ t('leveling.cooldownLabel') }}</label>
            <div class="form-row__hint">{{ t('leveling.cooldownHint') }}</div>
            <div class="inline-input">
              <input
                id="lvl-cooldown"
                class="input input--num"
                type="number"
                min="0"
                max="600"
                step="1"
                :disabled="!form.enabled"
                v-model.number="form.cooldown_seconds"
              />
              <span class="suffix">{{ t('leveling.cooldownSecondsSuffix') }}</span>
            </div>
          </div>
        </div>

        <!-- Level-up channel -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('leveling.levelUpChannelLabel') }}</div>
            <div class="form-row__hint">{{ t('leveling.levelUpChannelHint') }}</div>
            <ChannelSelector
              v-model="form.level_up_channel_id"
              :guild-id="guildId"
              :types="['text', 'announcement']"
              :allow-clear="true"
              :disabled="!form.enabled"
            />
          </div>
        </div>

        <!-- Level-up message -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <label class="form-row__label" for="lvl-msg">{{ t('leveling.levelUpMessageLabel') }}</label>
            <div class="form-row__hint">{{ t('leveling.levelUpMessageHint') }}</div>
            <textarea
              id="lvl-msg"
              ref="levelMsgRef"
              class="input input--textarea"
              rows="3"
              maxlength="2000"
              :disabled="!form.enabled"
              v-model="form.level_up_message"
              :placeholder="t('leveling.levelUpMessagePlaceholder')"
            ></textarea>
            <div class="placeholder-bar">
              <button
                v-for="ph in LEVELING_PLACEHOLDERS"
                :key="ph.token"
                type="button"
                class="placeholder-bar__chip"
                :disabled="!form.enabled"
                @click="insertLevelPlaceholder(ph.token)"
              >{{ ph.token }}</button>
            </div>
          </div>
        </div>

        <!-- Ignored channels -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('leveling.ignoredChannelsLabel') }}</div>
            <div class="form-row__hint">{{ t('leveling.ignoredChannelsHint') }}</div>
            <div class="ignored-row">
              <ChannelSelector
                v-model="ignoredPick"
                :guild-id="guildId"
                :types="['text', 'announcement']"
                :disabled="!form.enabled"
              />
              <AppButton
                variant="ghost"
                :disabled="!form.enabled || !ignoredPick || form.ignored_channel_ids.includes(ignoredPick)"
                @click="addIgnored"
              >{{ t('leveling.ignoredChannelsAdd') }}</AppButton>
            </div>
            <div v-if="form.ignored_channel_ids.length === 0" class="hint-dim">{{ t('leveling.ignoredChannelsEmpty') }}</div>
            <ul v-else class="ignored-list">
              <li v-for="id in form.ignored_channel_ids" :key="id" class="ignored-chip">
                <span class="ignored-chip__name">#{{ resolveChannelName(id) }}</span>
                <span class="ignored-chip__id">{{ shortId(id) }}</span>
                <button
                  type="button"
                  class="ignored-chip__remove"
                  :disabled="!form.enabled"
                  @click="removeIgnored(id)"
                  :aria-label="t('common.reset')"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </li>
            </ul>
          </div>
        </div>

        <!-- Reward roles -->
        <div class="form-card" :class="{ 'is-disabled': !form.enabled }">
          <div class="form-row">
            <div class="form-row__label">{{ t('leveling.rewardsLabel') }}</div>
            <div class="form-row__hint">{{ t('leveling.rewardsHint') }}</div>
            <div v-if="form.rewards.length === 0" class="hint-dim">{{ t('leveling.rewardsEmpty') }}</div>
            <div v-else class="rewards-list">
              <div
                v-for="(r, idx) in form.rewards"
                :key="idx"
                class="reward-row"
              >
                <label class="reward-row__col reward-row__col--lvl">
                  <span class="reward-row__label">{{ t('leveling.rewardLevel') }}</span>
                  <input
                    class="input input--num"
                    type="number"
                    min="1"
                    max="500"
                    step="1"
                    :disabled="!form.enabled"
                    v-model.number="r.level"
                  />
                </label>
                <div class="reward-row__col reward-row__col--role">
                  <span class="reward-row__label">{{ t('leveling.rewardRole') }}</span>
                  <RoleSelector
                    v-model="r.role_id"
                    :guild-id="guildId"
                    :multiple="false"
                    :disabled="!form.enabled"
                  />
                </div>
                <button
                  type="button"
                  class="reward-row__remove"
                  :disabled="!form.enabled"
                  :aria-label="t('common.reset')"
                  @click="removeReward(idx)"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
            </div>
            <AppButton variant="ghost" :disabled="!form.enabled" @click="addReward">
              <template #icon-left>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              </template>
              {{ t('leveling.addReward') }}
            </AppButton>
          </div>

          <div class="form-row form-row--toggle">
            <div>
              <div class="form-row__label">{{ t('leveling.stackRewardsLabel') }}</div>
              <div class="form-row__hint">{{ t('leveling.stackRewardsHint') }}</div>
            </div>
            <AppToggle v-model="form.stack_role_rewards" :disabled="!form.enabled" />
          </div>
        </div>

        <!-- Leaderboard -->
        <div class="form-card">
          <div class="leaderboard__head">
            <div class="form-row__label">{{ t('leveling.leaderboardTitle') }}</div>
            <AppButton variant="ghost" :loading="leaderboard.loading" @click="loadLeaderboard">
              <template #icon-left>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10"/><path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14"/></svg>
              </template>
              {{ t('leveling.leaderboardRefresh') }}
            </AppButton>
          </div>

          <div v-if="leaderboard.loading && leaderboard.rows.length === 0" class="leaderboard__state">
            <div class="skeleton skeleton--row" v-for="i in 5" :key="i"></div>
          </div>
          <div v-else-if="leaderboard.rows.length === 0" class="leaderboard__state">
            {{ t('leveling.leaderboardEmpty') }}
          </div>
          <div v-else class="leaderboard__table-wrap">
            <table class="leaderboard__table">
              <thead>
                <tr>
                  <th>{{ t('leveling.leaderboardRank') }}</th>
                  <th>{{ t('leveling.leaderboardUser') }}</th>
                  <th>{{ t('leveling.leaderboardLevel') }}</th>
                  <th>{{ t('leveling.leaderboardXp') }}</th>
                  <th>{{ t('leveling.leaderboardMessages') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in leaderboard.rows" :key="row.user_id">
                  <td class="rank">#{{ row.rank }}</td>
                  <td class="user-id" :title="row.user_id">{{ shortenUser(row.user_id) }}</td>
                  <td>{{ row.level }}</td>
                  <td>{{ row.xp }}</td>
                  <td>{{ row.messages }}</td>
                </tr>
              </tbody>
            </table>
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
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import AppToggle from '../components/AppToggle.vue'
import ChannelSelector from '../components/ChannelSelector.vue'
import RoleSelector from '../components/RoleSelector.vue'
import { PLACEHOLDERS, insertAtCaret } from '../components/embedPlaceholders.js'
import api from '../services/api.js'
import { useGuildResources } from '../composables/useGuildResources.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()

const guildId = computed(() => route.params.guild_id)
const resources = computed(() => useGuildResources(guildId.value))

// Leveling-specific placeholders. {level} isn't in the shared list, so we
// build a focused subset and add {level} on top.
const LEVELING_PLACEHOLDERS = [
  ...PLACEHOLDERS.filter(p => ['{user}', '{user.name}', '{guild}'].includes(p.token)),
  { token: '{level}', labelKey: 'placeholderLevel' }
]

function defaults() {
  return {
    enabled: false,
    xp_per_message_min: 15,
    xp_per_message_max: 25,
    cooldown_seconds: 60,
    level_up_channel_id: '',
    level_up_message: 'GG {user}, you reached level {level}!',
    ignored_channel_ids: [],
    stack_role_rewards: false,
    rewards: []
  }
}

const form = reactive(defaults())
let initial = JSON.stringify(form)
const saving = ref(false)
const levelMsgRef = ref(null)
const ignoredPick = ref('')

const dirty = computed(() => JSON.stringify(form) !== initial)

function shortId(id) {
  if (!id) return ''
  return id.length > 10 ? `…${id.slice(-4)}` : id
}

function shortenUser(id) {
  if (!id) return ''
  return id.length > 12 ? `…${id.slice(-4)}` : id
}

function resolveChannelName(id) {
  if (!id) return id
  const ch = resources.value.state.channels?.find(c => c.id === id)
  return ch?.name || id
}

function hydrate(settings) {
  const s = settings || {}
  const d = defaults()
  form.enabled = !!s.enabled
  form.xp_per_message_min = Number.isFinite(s.xp_per_message_min) ? s.xp_per_message_min : d.xp_per_message_min
  form.xp_per_message_max = Number.isFinite(s.xp_per_message_max) ? s.xp_per_message_max : d.xp_per_message_max
  form.cooldown_seconds = Number.isFinite(s.cooldown_seconds) ? s.cooldown_seconds : d.cooldown_seconds
  form.level_up_channel_id = s.level_up_channel_id || ''
  form.level_up_message = typeof s.level_up_message === 'string' ? s.level_up_message : d.level_up_message
  form.ignored_channel_ids = Array.isArray(s.ignored_channel_ids) ? s.ignored_channel_ids.slice() : []
  form.stack_role_rewards = !!s.stack_role_rewards
  form.rewards = Array.isArray(s.rewards)
    ? s.rewards.map(r => ({ level: Number(r.level) || 1, role_id: r.role_id || '' }))
    : []
  initial = JSON.stringify(form)
}

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/settings/leveling`)
    if (data?.success) hydrate(data.settings || defaults())
    else hydrate(defaults())
  } catch (err) {
    hydrate(defaults())
    toast.error(t('toast.couldNotLoadSettings'))
  }
  resources.value.loadChannels()
  resources.value.loadRoles()
  loadLeaderboard()
}

onMounted(load)
watch(() => guildId.value, load)

// Keep min <= max
watch(() => form.xp_per_message_min, (v) => {
  if (Number.isFinite(v) && Number.isFinite(form.xp_per_message_max) && v > form.xp_per_message_max) {
    form.xp_per_message_max = v
  }
})
watch(() => form.xp_per_message_max, (v) => {
  if (Number.isFinite(v) && Number.isFinite(form.xp_per_message_min) && v < form.xp_per_message_min) {
    form.xp_per_message_min = v
  }
})

async function insertLevelPlaceholder(token) {
  if (!form.enabled) return
  const el = levelMsgRef.value
  const { value, caret } = insertAtCaret(el, form.level_up_message, token)
  form.level_up_message = value
  await nextTick()
  if (el) {
    el.focus()
    try { el.setSelectionRange(caret, caret) } catch {
      // ignored
    }
  }
}

function addIgnored() {
  const id = ignoredPick.value
  if (!id) return
  if (form.ignored_channel_ids.includes(id)) return
  form.ignored_channel_ids = [...form.ignored_channel_ids, id]
  ignoredPick.value = ''
}

function removeIgnored(id) {
  form.ignored_channel_ids = form.ignored_channel_ids.filter(x => x !== id)
}

function addReward() {
  const nextLevel = form.rewards.length
    ? Math.max(...form.rewards.map(r => Number(r.level) || 0)) + 5
    : 5
  form.rewards.push({ level: nextLevel, role_id: '' })
}

function removeReward(idx) {
  form.rewards.splice(idx, 1)
}

function reset() {
  hydrate(JSON.parse(initial))
  toast.info(t('toast.revertedChanges'))
}

async function save() {
  saving.value = true
  try {
    const body = {
      enabled: !!form.enabled,
      xp_per_message_min: Math.max(0, Number(form.xp_per_message_min) || 0),
      xp_per_message_max: Math.max(0, Number(form.xp_per_message_max) || 0),
      cooldown_seconds: Math.max(0, Math.min(600, Number(form.cooldown_seconds) || 0)),
      level_up_channel_id: form.level_up_channel_id || '',
      level_up_message: form.level_up_message || '',
      ignored_channel_ids: form.ignored_channel_ids.slice(),
      stack_role_rewards: !!form.stack_role_rewards,
      rewards: form.rewards
        .filter(r => r.role_id && Number(r.level) >= 1)
        .map(r => ({ level: Number(r.level), role_id: r.role_id }))
    }
    if (body.xp_per_message_max < body.xp_per_message_min) {
      body.xp_per_message_max = body.xp_per_message_min
    }
    const { data } = await api.put(`/guilds/${guildId.value}/settings/leveling`, body)
    if (data?.success) hydrate(data.settings || body)
    else hydrate(body)
    toast.success(t('leveling.saved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}

// Leaderboard
const leaderboard = reactive({
  rows: [],
  total: 0,
  loading: false
})

async function loadLeaderboard() {
  if (!guildId.value) return
  leaderboard.loading = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/leveling/leaderboard`, {
      params: { limit: 25, offset: 0 }
    })
    if (data?.success) {
      leaderboard.rows = Array.isArray(data.leaderboard) ? data.leaderboard : []
      leaderboard.total = Number(data.total) || leaderboard.rows.length
    } else {
      leaderboard.rows = []
      leaderboard.total = 0
    }
  } catch (err) {
    leaderboard.rows = []
    leaderboard.total = 0
  } finally {
    leaderboard.loading = false
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

.hint-dim {
  font-size: 0.82rem;
  color: var(--color-text-soft);
  font-style: italic;
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

.input--num {
  width: 100px;
  text-align: right;
  font-family: var(--font-mono);
}

.input--textarea {
  resize: vertical;
  min-height: 90px;
  line-height: 1.55;
}

.inline-input {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
}

.suffix {
  font-size: 0.82rem;
  color: var(--color-text-muted);
}

.xp-range {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.xp-range__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.xp-range__label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-soft);
  font-weight: 600;
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

.ignored-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-3);
  align-items: center;
}

.ignored-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.ignored-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.3rem 0.6rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
}

.ignored-chip__name {
  color: var(--color-text);
}

.ignored-chip__id {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--color-text-soft);
}

.ignored-chip__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--color-text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.ignored-chip__remove:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.18);
  color: var(--color-danger);
}

.rewards-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.reward-row {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: flex-end;
  padding: var(--space-3);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.reward-row__col {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.reward-row__label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-soft);
  font-weight: 600;
}

.reward-row__col--lvl .input--num {
  width: 100%;
  text-align: left;
}

.reward-row__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--color-text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
  align-self: flex-end;
}

.reward-row__remove:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.18);
  color: var(--color-danger);
}

/* Leaderboard */
.leaderboard__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.leaderboard__state {
  padding: var(--space-3) 0;
  color: var(--color-text-muted);
  font-size: 0.88rem;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.skeleton--row {
  height: 28px;
  border-radius: var(--radius-sm);
  background: linear-gradient(90deg, var(--color-surface-2), var(--color-surface-3), var(--color-surface-2));
  background-size: 200% 100%;
  animation: skeleton 1.2s ease-in-out infinite;
}

@keyframes skeleton {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.leaderboard__table-wrap {
  overflow-x: auto;
}

.leaderboard__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.leaderboard__table th {
  text-align: left;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-soft);
  font-weight: 600;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
}

.leaderboard__table td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
}

.leaderboard__table tr:last-child td {
  border-bottom: 0;
}

.rank {
  font-family: var(--font-mono);
  color: var(--color-text-muted);
}

.user-id {
  font-family: var(--font-mono);
  color: var(--color-text);
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

.dot--warn {
  background: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

.config__footer-actions {
  display: flex;
  gap: var(--space-3);
}

.dirty-bar-enter-active,
.dirty-bar-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.dirty-bar-enter-from,
.dirty-bar-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 1100px) {
  .config__grid,
  .config__grid--single {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .reward-row {
    grid-template-columns: 1fr;
  }
  .ignored-row {
    grid-template-columns: 1fr;
  }
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
