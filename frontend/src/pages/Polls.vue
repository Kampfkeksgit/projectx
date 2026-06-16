<template>
  <div class="config">
    <header class="config__head">
      <div class="config__eyebrow">{{ t('polls.eyebrow') }}</div>
      <h1 class="config__title">{{ t('polls.title') }}</h1>
      <p class="config__sub">{{ t('polls.sub') }}</p>
    </header>

    <div class="form-card note">{{ t('polls.usageNote') }}</div>

    <div v-if="loading && rows.length === 0" class="form-card state">{{ t('common.loading') }}</div>
    <div v-else-if="!loading && rows.length === 0" class="form-card empty">
      <div class="empty__title">{{ t('polls.emptyTitle') }}</div>
      <div class="empty__body">{{ t('polls.emptyBody') }}</div>
    </div>

    <div v-else class="poll-list">
      <div v-for="p in rows" :key="p.id" class="form-card poll-row">
        <div class="poll-row__main">
          <div class="poll-row__q">📊 {{ p.question || '—' }}</div>
          <div class="poll-row__meta">
            <span class="poll-row__badge" :class="p.ended ? 'is-ended' : 'is-active'">{{ p.ended ? t('polls.closed') : t('polls.open') }}</span>
            <span>{{ t('polls.optionsCount', { count: p.options.length }) }}</span>
            <span>{{ t('polls.votesCount', { count: p.total_votes || 0 }) }}</span>
          </div>
        </div>
        <AppButton variant="danger" :loading="deletingIds.has(p.id)" @click="confirmDelete(p)">{{ t('common.delete') }}</AppButton>
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

async function load() {
  if (!guildId.value) return
  loading.value = true
  try {
    const { data } = await api.get(`/guilds/${guildId.value}/polls`)
    rows.value = (data?.success && Array.isArray(data.polls)) ? data.polls : []
  } catch (err) {
    rows.value = []
    toast.error(t('polls.loadError'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(guildId, load)

async function confirmDelete(p) {
  if (typeof window !== 'undefined' && !window.confirm(t('polls.deleteConfirm'))) return
  deletingIds.add(p.id)
  try {
    await api.delete(`/guilds/${guildId.value}/polls/${p.id}`)
    rows.value = rows.value.filter(r => r.id !== p.id)
    toast.success(t('polls.deleted'))
  } catch (err) {
    toast.error(err.response?.data?.error || t('toast.failedToSave'))
  } finally {
    deletingIds.delete(p.id)
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
.poll-list { display: flex; flex-direction: column; gap: var(--space-3); }
.poll-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
.poll-row__main { min-width: 0; }
.poll-row__q { font-weight: 600; font-size: 1.02rem; margin-bottom: 4px; }
.poll-row__meta { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; font-size: 0.84rem; color: var(--color-text-muted); }
.poll-row__badge { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; padding: 2px 8px; border-radius: var(--radius-sm); color: #fff; }
.poll-row__badge.is-active { background: var(--color-success); }
.poll-row__badge.is-ended { background: var(--color-text-soft); }
</style>
