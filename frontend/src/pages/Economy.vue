<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('economy.eyebrow') }}</div>
      <h1 class="config__title">{{ t('economy.title') }}</h1>
      <p class="config__sub">{{ t('economy.sub') }}</p>
    </header>

    <!-- Settings -->
    <section class="form-card">
      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('economy.enableLabel') }}</div>
          <div class="row__hint">{{ t('economy.enableHint') }}</div>
        </div>
        <AppToggle v-model="form.enabled" />
      </div>

      <div class="row-grid">
        <div class="row">
          <label class="row__label" for="ec-name">{{ t('economy.currencyNameLabel') }}</label>
          <input id="ec-name" v-model="form.currency_name" class="input" type="text" maxlength="32" placeholder="coins" />
        </div>
        <div class="row">
          <label class="row__label" for="ec-symbol">{{ t('economy.currencySymbolLabel') }}</label>
          <input id="ec-symbol" v-model="form.currency_symbol" class="input input--narrow" type="text" maxlength="16" placeholder="🪙" />
        </div>
      </div>

      <div class="row-grid">
        <div class="row">
          <label class="row__label" for="ec-start">{{ t('economy.startBalanceLabel') }}</label>
          <input id="ec-start" v-model.number="form.start_balance" class="input" type="number" min="0" />
        </div>
        <div class="row">
          <label class="row__label" for="ec-daily">{{ t('economy.dailyLabel') }}</label>
          <input id="ec-daily" v-model.number="form.daily_amount" class="input" type="number" min="0" />
        </div>
      </div>

      <div class="row-grid row-grid--3">
        <div class="row">
          <label class="row__label" for="ec-wmin">{{ t('economy.workMinLabel') }}</label>
          <input id="ec-wmin" v-model.number="form.work_min" class="input" type="number" min="0" />
        </div>
        <div class="row">
          <label class="row__label" for="ec-wmax">{{ t('economy.workMaxLabel') }}</label>
          <input id="ec-wmax" v-model.number="form.work_max" class="input" type="number" min="0" />
        </div>
        <div class="row">
          <label class="row__label" for="ec-cd">{{ t('economy.workCooldownLabel') }}</label>
          <input id="ec-cd" v-model.number="form.work_cooldown" class="input" type="number" min="0" />
        </div>
      </div>

      <div class="form-card__note form-card__note--info">{{ t('economy.usageNote') }}</div>

      <div class="form-card__actions">
        <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.saveChanges') }}</AppButton>
      </div>
    </section>

    <!-- Bank -->
    <section class="form-card">
      <h2 class="shop-head__title">{{ t('economy.bankTitle') }}</h2>
      <p class="row__hint">{{ t('economy.bankHint') }}</p>
      <div class="row row--toggle">
        <div>
          <div class="row__label">{{ t('economy.bankEnableLabel') }}</div>
          <div class="row__hint">{{ t('economy.bankEnableHint') }}</div>
        </div>
        <AppToggle v-model="form.bank_enabled" />
      </div>
      <div class="row-grid">
        <div class="row">
          <label class="row__label" for="ec-bankmax">{{ t('economy.bankMaxLabel') }}</label>
          <input id="ec-bankmax" v-model.number="form.bank_max" class="input" type="number" min="0" />
          <div class="row__hint">{{ t('economy.bankMaxHint') }}</div>
        </div>
        <div class="row">
          <label class="row__label" for="ec-interest">{{ t('economy.interestRateLabel') }}</label>
          <input id="ec-interest" v-model.number="form.interest_rate" class="input" type="number" min="0" max="100" />
          <div class="row__hint">{{ t('economy.interestRateHint') }}</div>
        </div>
      </div>
    </section>

    <!-- Ways to earn -->
    <section class="form-card">
      <h2 class="shop-head__title">{{ t('economy.earnTitle') }}</h2>
      <p class="row__hint">{{ t('economy.earnHint') }}</p>

      <!-- Weekly -->
      <div class="subgroup">
        <div class="row row--toggle">
          <div class="row__label">{{ t('economy.weeklyTitle') }}</div>
          <AppToggle v-model="form.weekly_enabled" />
        </div>
        <div class="row-grid">
          <div class="row">
            <label class="row__label">{{ t('economy.weeklyAmountLabel') }}</label>
            <input v-model.number="form.weekly_amount" class="input" type="number" min="0" />
          </div>
          <div class="row">
            <label class="row__label">{{ t('economy.weeklyCooldownLabel') }}</label>
            <input v-model.number="form.weekly_cooldown" class="input" type="number" min="0" />
          </div>
        </div>
      </div>

      <!-- Beg -->
      <div class="subgroup">
        <div class="row row--toggle">
          <div class="row__label">{{ t('economy.begTitle') }}</div>
          <AppToggle v-model="form.beg_enabled" />
        </div>
        <div class="row-grid row-grid--3">
          <div class="row"><label class="row__label">{{ t('economy.begMinLabel') }}</label><input v-model.number="form.beg_min" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.begMaxLabel') }}</label><input v-model.number="form.beg_max" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.begCooldownLabel') }}</label><input v-model.number="form.beg_cooldown" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.begSuccessLabel') }}</label><input v-model.number="form.beg_success" class="input" type="number" min="0" max="100" /></div>
        </div>
      </div>

      <!-- Crime -->
      <div class="subgroup">
        <div class="row row--toggle">
          <div class="row__label">{{ t('economy.crimeTitle') }}</div>
          <AppToggle v-model="form.crime_enabled" />
        </div>
        <div class="row-grid row-grid--3">
          <div class="row"><label class="row__label">{{ t('economy.crimeMinLabel') }}</label><input v-model.number="form.crime_min" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.crimeMaxLabel') }}</label><input v-model.number="form.crime_max" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.crimeCooldownLabel') }}</label><input v-model.number="form.crime_cooldown" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.crimeFineMinLabel') }}</label><input v-model.number="form.crime_fine_min" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.crimeFineMaxLabel') }}</label><input v-model.number="form.crime_fine_max" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.crimeSuccessLabel') }}</label><input v-model.number="form.crime_success" class="input" type="number" min="0" max="100" /></div>
        </div>
      </div>

      <!-- Fishing -->
      <div class="subgroup">
        <div class="row row--toggle">
          <div class="row__label">{{ t('economy.fishTitle') }}</div>
          <AppToggle v-model="form.fish_enabled" />
        </div>
        <div class="row-grid row-grid--3">
          <div class="row"><label class="row__label">{{ t('economy.fishMinLabel') }}</label><input v-model.number="form.fish_min" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.fishMaxLabel') }}</label><input v-model.number="form.fish_max" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.fishCooldownLabel') }}</label><input v-model.number="form.fish_cooldown" class="input" type="number" min="0" /></div>
        </div>
      </div>

      <!-- Mining -->
      <div class="subgroup">
        <div class="row row--toggle">
          <div class="row__label">{{ t('economy.mineTitle') }}</div>
          <AppToggle v-model="form.mine_enabled" />
        </div>
        <div class="row-grid row-grid--3">
          <div class="row"><label class="row__label">{{ t('economy.mineMinLabel') }}</label><input v-model.number="form.mine_min" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.mineMaxLabel') }}</label><input v-model.number="form.mine_max" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.mineCooldownLabel') }}</label><input v-model.number="form.mine_cooldown" class="input" type="number" min="0" /></div>
        </div>
      </div>
    </section>

    <!-- Robbery -->
    <section class="form-card">
      <h2 class="shop-head__title">{{ t('economy.robTitle') }}</h2>
      <p class="row__hint">{{ t('economy.robHint') }}</p>
      <div class="row row--toggle">
        <div class="row__label">{{ t('economy.robEnableLabel') }}</div>
        <AppToggle v-model="form.rob_enabled" />
      </div>
      <div class="row-grid">
        <div class="row"><label class="row__label">{{ t('economy.robCooldownLabel') }}</label><input v-model.number="form.rob_cooldown" class="input" type="number" min="0" /></div>
        <div class="row"><label class="row__label">{{ t('economy.robSuccessLabel') }}</label><input v-model.number="form.rob_success" class="input" type="number" min="0" max="100" /></div>
      </div>
      <div class="row-grid">
        <div class="row">
          <label class="row__label">{{ t('economy.robMaxPercentLabel') }}</label>
          <input v-model.number="form.rob_max_percent" class="input" type="number" min="0" max="100" />
          <div class="row__hint">{{ t('economy.robMaxPercentHint') }}</div>
        </div>
        <div class="row">
          <label class="row__label">{{ t('economy.robFinePercentLabel') }}</label>
          <input v-model.number="form.rob_fine_percent" class="input" type="number" min="0" max="100" />
          <div class="row__hint">{{ t('economy.robFinePercentHint') }}</div>
        </div>
      </div>
      <div class="row">
        <label class="row__label">{{ t('economy.robMinBalanceLabel') }}</label>
        <input v-model.number="form.rob_min_balance" class="input" type="number" min="0" />
        <div class="row__hint">{{ t('economy.robMinBalanceHint') }}</div>
      </div>
    </section>

    <!-- Gambling -->
    <section class="form-card">
      <h2 class="shop-head__title">{{ t('economy.gamblingTitle') }}</h2>
      <p class="row__hint">{{ t('economy.gamblingHint') }}</p>
      <div class="row row--toggle">
        <div class="row__label">{{ t('economy.gamblingEnableLabel') }}</div>
        <AppToggle v-model="form.gambling_enabled" />
      </div>
      <div class="row-grid">
        <div class="row"><label class="row__label">{{ t('economy.minBetLabel') }}</label><input v-model.number="form.min_bet" class="input" type="number" min="0" /></div>
        <div class="row"><label class="row__label">{{ t('economy.maxBetLabel') }}</label><input v-model.number="form.max_bet" class="input" type="number" min="0" /></div>
      </div>
      <div class="row row--toggle"><div class="row__label">{{ t('economy.coinflipLabel') }}</div><AppToggle v-model="form.coinflip_enabled" /></div>
      <div class="row row--toggle"><div class="row__label">{{ t('economy.diceLabel') }}</div><AppToggle v-model="form.dice_enabled" /></div>
      <div class="row row--toggle"><div class="row__label">{{ t('economy.slotsLabel') }}</div><AppToggle v-model="form.slots_enabled" /></div>
    </section>

    <!-- Passive earning -->
    <section class="form-card">
      <h2 class="shop-head__title">{{ t('economy.passiveTitle') }}</h2>
      <p class="row__hint">{{ t('economy.passiveHint') }}</p>
      <div class="subgroup">
        <div class="row row--toggle">
          <div class="row__label">{{ t('economy.chatEarnEnableLabel') }}</div>
          <AppToggle v-model="form.chat_earn_enabled" />
        </div>
        <div class="row-grid row-grid--3">
          <div class="row"><label class="row__label">{{ t('economy.chatEarnMinLabel') }}</label><input v-model.number="form.chat_earn_min" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.chatEarnMaxLabel') }}</label><input v-model.number="form.chat_earn_max" class="input" type="number" min="0" /></div>
          <div class="row"><label class="row__label">{{ t('economy.chatEarnCooldownLabel') }}</label><input v-model.number="form.chat_earn_cooldown" class="input" type="number" min="0" /></div>
        </div>
      </div>
      <div class="subgroup">
        <div class="row row--toggle">
          <div class="row__label">{{ t('economy.voiceEarnEnableLabel') }}</div>
          <AppToggle v-model="form.voice_earn_enabled" />
        </div>
        <div class="row">
          <label class="row__label">{{ t('economy.voiceEarnAmountLabel') }}</label>
          <input v-model.number="form.voice_earn_amount" class="input input--narrow" type="number" min="0" />
          <div class="row__hint">{{ t('economy.voiceEarnAmountHint') }}</div>
        </div>
      </div>
    </section>

    <!-- Daily streak -->
    <section class="form-card">
      <h2 class="shop-head__title">{{ t('economy.streakTitle') }}</h2>
      <p class="row__hint">{{ t('economy.streakHint') }}</p>
      <div class="row row--toggle">
        <div class="row__label">{{ t('economy.streakEnableLabel') }}</div>
        <AppToggle v-model="form.daily_streak_enabled" />
      </div>
      <div class="row-grid">
        <div class="row">
          <label class="row__label">{{ t('economy.streakBonusLabel') }}</label>
          <input v-model.number="form.daily_streak_bonus" class="input" type="number" min="0" />
          <div class="row__hint">{{ t('economy.streakBonusHint') }}</div>
        </div>
        <div class="row">
          <label class="row__label">{{ t('economy.streakMaxLabel') }}</label>
          <input v-model.number="form.daily_streak_max" class="input" type="number" min="0" />
          <div class="row__hint">{{ t('economy.streakMaxHint') }}</div>
        </div>
      </div>
    </section>

    <!-- Role multipliers -->
    <section class="form-card">
      <h2 class="shop-head__title">{{ t('economy.multipliersTitle') }}</h2>
      <p class="row__hint">{{ t('economy.multipliersHint') }}</p>

      <div v-if="form.role_multipliers.length === 0" class="lb-empty">{{ t('economy.multipliersEmpty') }}</div>
      <div v-else class="mult-list">
        <div v-for="(row, i) in form.role_multipliers" :key="row._key" class="mult-row">
          <div class="mult-row__cell">
            <label class="row__label">{{ t('economy.multiplierRoleLabel') }}</label>
            <RoleSelector v-model="row.role_id" :guild-id="guildId" />
          </div>
          <div class="mult-row__cell">
            <label class="row__label">{{ t('economy.multiplierValueLabel') }}</label>
            <input v-model.number="row.multiplier" class="input" type="number" min="0" step="0.1" />
          </div>
          <AppButton variant="danger" @click="removeMultiplier(i)">{{ t('common.delete') }}</AppButton>
        </div>
      </div>

      <div>
        <AppButton variant="ghost" @click="addMultiplier">{{ t('economy.addMultiplier') }}</AppButton>
      </div>

      <div class="form-card__actions">
        <AppButton variant="gradient" :loading="saving" :disabled="!dirty" @click="save">{{ t('common.saveChanges') }}</AppButton>
      </div>
    </section>

    <!-- Shop -->
    <section class="form-card">
      <div class="shop-head">
        <h2 class="shop-head__title">{{ t('economy.shopTitle') }}</h2>
        <AppButton variant="ghost" :loading="addingItem" @click="addItem">{{ t('economy.addItem') }}</AppButton>
      </div>
      <p class="row__hint">{{ t('economy.shopHint') }}</p>

      <div v-if="shop.length === 0" class="lb-empty">{{ t('economy.shopEmpty') }}</div>
      <div v-else class="shop-list">
        <div v-for="it in shop" :key="it.id" class="shop-row">
          <div class="shop-row__grid">
            <input v-model="it.name" class="input" type="text" maxlength="100" :placeholder="t('economy.itemName')" />
            <input v-model.number="it.price" class="input input--narrow" type="number" min="0" :placeholder="t('economy.itemPrice')" />
          </div>
          <input v-model="it.description" class="input" type="text" maxlength="300" :placeholder="t('economy.itemDesc')" />
          <div class="row">
            <label class="row__label">{{ t('economy.itemRole') }}</label>
            <RoleSelector v-model="it.role_id" :guild-id="guildId" />
          </div>
          <div class="shop-row__foot">
            <label class="inline-toggle"><AppToggle v-model="it.enabled" /> {{ t('common.enabled') }}</label>
            <div class="shop-row__actions">
              <AppButton variant="ghost" :loading="savingItems.has(it.id)" @click="saveItem(it)">{{ t('common.save') }}</AppButton>
              <AppButton variant="danger" :loading="deletingItems.has(it.id)" @click="deleteItem(it)">{{ t('common.delete') }}</AppButton>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Leaderboard -->
    <section class="form-card">
      <h2 class="shop-head__title">{{ t('economy.leaderboardTitle') }}</h2>
      <div v-if="leaderboard.length === 0" class="lb-empty">{{ t('economy.leaderboardEmpty') }}</div>
      <table v-else class="lb-table">
        <thead><tr><th>#</th><th>{{ t('economy.memberCol') }}</th><th class="num">{{ t('economy.balanceCol') }}</th></tr></thead>
        <tbody>
          <tr v-for="e in leaderboard" :key="e.user_id"><td>{{ e.rank }}</td><td class="mono">{{ e.user_id }}</td><td class="num">{{ e.balance }}</td></tr>
        </tbody>
      </table>
    </section>
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
import { useAutoRefresh } from '../composables/useAutoRefresh.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const form = reactive({
  enabled: false, currency_name: 'coins', currency_symbol: '🪙',
  start_balance: 0, daily_amount: 200, work_min: 50, work_max: 250, work_cooldown: 3600,
  // Bank
  bank_enabled: false, bank_max: 0, interest_rate: 0,
  // Weekly
  weekly_enabled: false, weekly_amount: 1000, weekly_cooldown: 604800,
  // Beg
  beg_enabled: false, beg_min: 10, beg_max: 100, beg_cooldown: 300, beg_success: 60,
  // Crime
  crime_enabled: false, crime_min: 100, crime_max: 500, crime_fine_min: 50, crime_fine_max: 250, crime_cooldown: 3600, crime_success: 50,
  // Rob
  rob_enabled: false, rob_cooldown: 3600, rob_success: 40, rob_max_percent: 50, rob_fine_percent: 20, rob_min_balance: 100,
  // Fish
  fish_enabled: false, fish_min: 10, fish_max: 100, fish_cooldown: 300,
  // Mine
  mine_enabled: false, mine_min: 10, mine_max: 100, mine_cooldown: 300,
  // Gambling
  gambling_enabled: false, min_bet: 10, max_bet: 10000, coinflip_enabled: true, dice_enabled: true, slots_enabled: true,
  // Passive earning
  chat_earn_enabled: false, chat_earn_min: 1, chat_earn_max: 5, chat_earn_cooldown: 60,
  voice_earn_enabled: false, voice_earn_amount: 5,
  // Modifiers
  daily_streak_enabled: false, daily_streak_bonus: 50, daily_streak_max: 500,
  role_multipliers: []
})
const shop = ref([])
const leaderboard = ref([])
const saving = ref(false)
const addingItem = ref(false)
const savingItems = reactive(new Set())
const deletingItems = reactive(new Set())
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

// Role multipliers repeater. Each row carries a client-only _key for a stable
// v-model binding; it is stripped before the settings are sent to the backend.
let multKeySeq = 0
const nextMultKey = () => `m${multKeySeq++}`
function normalizeMultipliers(arr) {
  if (!Array.isArray(arr)) return []
  return arr
    .filter(r => r && typeof r === 'object')
    .map(r => ({ _key: nextMultKey(), role_id: r.role_id ? String(r.role_id) : '', multiplier: Number(r.multiplier) || 1 }))
}
function addMultiplier() {
  form.role_multipliers.push({ _key: nextMultKey(), role_id: '', multiplier: 1 })
}
function removeMultiplier(i) {
  form.role_multipliers.splice(i, 1)
}
// Drop incomplete rows and strip the client-only _key for the PUT body.
function cleanMultipliers() {
  return form.role_multipliers
    .filter(r => r.role_id)
    .map(r => ({ role_id: String(r.role_id), multiplier: Number(r.multiplier) || 1 }))
}

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/economy`)
    if (data?.success) {
      Object.assign(form, data.settings || {})
      form.role_multipliers = normalizeMultipliers(form.role_multipliers)
      initial = JSON.stringify(form)
    }
  } catch (err) {
    toast.error(t('economy.loadError'))
  }
  await loadShop()
  await loadLeaderboard()
}

async function loadShop() {
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/economy/shop`)
    shop.value = (data?.success && Array.isArray(data.items)) ? data.items.map(i => ({ ...i, role_id: i.role_id || '' })) : []
  } catch { shop.value = [] }
}

async function loadLeaderboard() {
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/economy/leaderboard`)
    leaderboard.value = (data?.success && Array.isArray(data.leaderboard)) ? data.leaderboard : []
  } catch { leaderboard.value = [] }
}

onMounted(load)
watch(guildId, load)
// Keep settings + shop + leaderboard fresh; skip while the settings form is dirty.
useAutoRefresh(load, { isDirty: () => dirty.value })

async function save() {
  saving.value = true
  try {
    const payload = { ...form, role_multipliers: cleanMultipliers() }
    const { data } = await api.put(`/guilds/${guildId.value}/economy`, payload)
    if (data?.success && data.settings) {
      Object.assign(form, data.settings)
      form.role_multipliers = normalizeMultipliers(form.role_multipliers)
      initial = JSON.stringify(form)
    }
    toast.success(t('common.allSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    saving.value = false
  }
}

async function addItem() {
  addingItem.value = true
  try {
    const { data } = await api.post(`/guilds/${guildId.value}/economy/shop`, { name: t('economy.newItem'), price: 100, enabled: true })
    if (data?.success && data.item) shop.value.push({ ...data.item, role_id: data.item.role_id || '' })
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    addingItem.value = false
  }
}

async function saveItem(it) {
  savingItems.add(it.id)
  try {
    await api.put(`/guilds/${guildId.value}/economy/shop/${it.id}`, {
      name: it.name, description: it.description, price: it.price, role_id: it.role_id || null, enabled: !!it.enabled
    })
    toast.success(t('common.allSaved'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    savingItems.delete(it.id)
  }
}

async function deleteItem(it) {
  if (typeof window !== 'undefined' && !window.confirm(t('economy.deleteItemConfirm'))) return
  deletingItems.add(it.id)
  try {
    await api.delete(`/guilds/${guildId.value}/economy/shop/${it.id}`)
    shop.value = shop.value.filter(r => r.id !== it.id)
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingItems.delete(it.id)
  }
}
</script>

<style scoped>
.config__head { margin-bottom: var(--space-6); }
.config__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.config__title { font-size: clamp(1.6rem, 2.5vw, 2rem); letter-spacing: -0.02em; margin-bottom: var(--space-2); }
.config__sub { color: var(--color-text-muted); }
.form-card { max-width: 820px; background: var(--color-surface); background-image: var(--gradient-card); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-6); box-shadow: var(--shadow-inset); display: flex; flex-direction: column; gap: var(--space-5); margin-bottom: var(--space-5); }
.row { display: flex; flex-direction: column; gap: var(--space-2); }
.row--toggle { flex-direction: row; align-items: center; justify-content: space-between; gap: var(--space-4); }
.row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.5; }
.row-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); align-items: start; }
.row-grid--3 { grid-template-columns: 1fr 1fr 1fr; }
.input { width: 100%; padding: 0.7rem 0.85rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); color: var(--color-text); font-family: var(--font-sans); font-size: 0.95rem; }
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--narrow { max-width: 140px; }
.form-card__note { font-size: 0.82rem; border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); line-height: 1.5; }
.form-card__note--info { color: var(--color-text-muted); background: var(--color-bg-elevated); border: 1px solid var(--color-border); }
.form-card__actions { display: flex; justify-content: flex-end; }
.shop-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
.shop-head__title { font-size: 1.1rem; }
.shop-list { display: flex; flex-direction: column; gap: var(--space-4); }
.shop-row { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); background: var(--color-bg-elevated); }
.shop-row__grid { display: grid; grid-template-columns: 1fr 140px; gap: var(--space-3); }
.shop-row__foot { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.shop-row__actions { display: flex; gap: var(--space-2); }
.inline-toggle { display: inline-flex; align-items: center; gap: var(--space-2); font-size: 0.85rem; color: var(--color-text-muted); }
.lb-empty { color: var(--color-text-muted); font-size: 0.9rem; }
.lb-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.lb-table th, .lb-table td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--color-border); }
.lb-table th { color: var(--color-text-soft); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; }
.lb-table .num { text-align: right; font-family: var(--font-mono); }
.lb-table .mono { font-family: var(--font-mono); font-size: 0.82rem; color: var(--color-text-muted); }
.subgroup { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); background: var(--color-bg-elevated); }
.mult-list { display: flex; flex-direction: column; gap: var(--space-3); }
.mult-row { display: grid; grid-template-columns: 1fr 140px auto; gap: var(--space-3); align-items: end; }
.mult-row__cell { display: flex; flex-direction: column; gap: var(--space-2); min-width: 0; }
@media (max-width: 560px) { .row-grid, .row-grid--3, .shop-row__grid, .mult-row { grid-template-columns: 1fr; } }
</style>
