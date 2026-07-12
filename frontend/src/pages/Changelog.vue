<template>
  <div class="cl-page">
    <header class="cl-head">
      <div class="cl-head__eyebrow">{{ t('changelog.eyebrow') }}</div>
      <h1 class="cl-head__title">{{ t('changelog.title') }}</h1>
      <p class="cl-head__sub">{{ t('changelog.subtitle') }}</p>
    </header>

    <div v-if="loading" class="cl-state">{{ t('common.loading') }}</div>
    <div v-else-if="!entries.length" class="cl-state">{{ t('changelog.empty') }}</div>

    <div v-else class="cl-list">
      <article v-for="e in entries" :key="e.id" class="cl-card">
        <div class="cl-card__head">
          <span v-if="e.version" class="cl-card__version">{{ e.version }}</span>
          <span v-if="e.entry_date" class="cl-card__date">{{ fmtDate(e.entry_date) }}</span>
        </div>
        <h2 class="cl-card__title">{{ e.title }}</h2>
        <div v-if="e.body" class="cl-body">{{ e.body }}</div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../services/api.js'
import { useI18n } from '../i18n/index.js'

const { t, locale } = useI18n()
const entries = ref([])
const loading = ref(true)

function fmtDate(sec) {
  if (!sec) return ''
  const d = new Date(Number(sec) * 1000)
  return isNaN(d.getTime()) ? '' : d.toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })
}

async function loadChangelog() {
  try {
    const { data } = await api.get('/public/changelog')
    entries.value = Array.isArray(data?.entries) ? data.entries : []
  } catch { entries.value = [] } finally { loading.value = false }
}

onMounted(loadChangelog)
</script>

<style scoped>
.cl-page { max-width: 760px; margin: 0 auto; padding: clamp(2rem, 6vw, 5rem) var(--space-5) 5rem; }
.cl-head { text-align: center; margin-bottom: var(--space-8); }
.cl-head__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-primary); margin-bottom: var(--space-3); }
.cl-head__title { font-family: var(--font-display); font-size: clamp(2rem, 5vw, 3rem); letter-spacing: -0.02em; margin-bottom: var(--space-3); }
.cl-head__sub { color: var(--color-text-muted); max-width: 40rem; margin: 0 auto; line-height: 1.6; }
.cl-state { text-align: center; color: var(--color-text-muted); padding: var(--space-8); }

.cl-list { display: flex; flex-direction: column; gap: var(--space-5); }
.cl-card {
  position: relative;
  background: var(--color-surface); background-image: var(--gradient-card);
  border: 1px solid var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-6) var(--space-6) var(--space-5);
  box-shadow: var(--shadow-inset);
  transition: border-color var(--transition), box-shadow var(--transition);
}
.cl-card:hover { border-color: var(--color-primary-soft); box-shadow: 0 18px 40px -22px var(--color-primary-soft), var(--shadow-inset); }
.cl-card__head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-2); flex-wrap: wrap; }
.cl-card__version {
  display: inline-block; font-family: var(--font-mono); font-size: 0.74rem; font-weight: 700; letter-spacing: 0.02em;
  color: var(--color-primary); background: var(--color-primary-soft);
  padding: 3px 12px; border-radius: var(--radius-full);
}
.cl-card__date { font-size: 0.8rem; color: var(--color-text-soft); }
.cl-card__title { font-family: var(--font-display); font-size: 1.35rem; font-weight: 700; letter-spacing: -0.01em; margin-bottom: var(--space-3); }
.cl-body {
  color: var(--color-text-muted); font-size: 0.92rem; line-height: 1.6;
  white-space: pre-wrap; word-break: break-word;
}
</style>
