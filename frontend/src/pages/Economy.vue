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

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const form = reactive({ enabled: false, currency_name: 'coins', currency_symbol: '🪙', start_balance: 0, daily_amount: 200, work_min: 50, work_max: 250, work_cooldown: 3600 })
const shop = ref([])
const leaderboard = ref([])
const saving = ref(false)
const addingItem = ref(false)
const savingItems = reactive(new Set())
const deletingItems = reactive(new Set())
let initial = JSON.stringify(form)
const dirty = computed(() => JSON.stringify(form) !== initial)

async function load() {
  if (!guildId.value) return
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/economy`)
    if (data?.success) {
      Object.assign(form, data.settings || {})
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

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/guilds/${guildId.value}/economy`, { ...form })
    if (data?.success && data.settings) { Object.assign(form, data.settings); initial = JSON.stringify(form) }
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
@media (max-width: 560px) { .row-grid, .row-grid--3, .shop-row__grid { grid-template-columns: 1fr; } }
</style>
