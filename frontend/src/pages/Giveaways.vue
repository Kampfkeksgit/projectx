<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('giveaways.eyebrow') }}</div>
      <h1 class="config__title">{{ t('giveaways.title') }}</h1>
      <p class="config__sub">{{ t('giveaways.sub') }}</p>
    </header>

    <div class="form-card note">{{ t('giveaways.usageNote') }}</div>

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
            <span class="gw-row__badge" :class="g.ended ? 'is-ended' : 'is-active'">{{ g.ended ? t('giveaways.ended') : t('giveaways.active') }}</span>
            <span>{{ t('giveaways.winnersLabel', { count: g.winners_count }) }}</span>
            <span class="gw-row__time">{{ formatEnds(g.ends_at) }}</span>
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
import api from '../services/api.js'
import { useToast } from '../composables/useToast.js'
import { useI18n } from '../i18n/index.js'

const route = useRoute()
const toast = useToast()
const { t } = useI18n()
const guildId = computed(() => route.params.guild_id)

const rows = ref([])
const loading = ref(false)
const deletingIds = reactive(new Set())

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
.gw-list { display: flex; flex-direction: column; gap: var(--space-3); }
.gw-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
.gw-row__main { min-width: 0; }
.gw-row__prize { font-weight: 600; font-size: 1.02rem; margin-bottom: 4px; }
.gw-row__meta { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; font-size: 0.84rem; color: var(--color-text-muted); }
.gw-row__badge { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; padding: 2px 8px; border-radius: var(--radius-sm); color: #fff; }
.gw-row__badge.is-active { background: var(--color-success); }
.gw-row__badge.is-ended { background: var(--color-text-soft); }
.gw-row__time { font-family: var(--font-mono); font-size: 0.78rem; }
</style>
