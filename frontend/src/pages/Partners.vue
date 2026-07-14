<template>
  <div class="partners-page">
    <header class="partners-head">
      <div class="partners-head__eyebrow">{{ t('partners.eyebrow') }}</div>
      <h1 class="partners-head__title">{{ t('partners.title') }}</h1>
      <p class="partners-head__sub">{{ t('partners.sub') }}</p>
    </header>

    <div v-if="loading" class="partners-state">{{ t('common.loading') }}</div>
    <div v-else-if="!partners.length" class="partners-state">{{ t('partners.empty') }}</div>

    <div v-else class="partners-grid">
      <article v-for="p in partners" :key="p.id" class="partner-card">
        <span class="partner-card__kind" :class="`partner-card__kind--${p.kind}`">
          {{ p.kind === 'guild' ? t('partners.kindGuild') : t('partners.kindUser') }}
        </span>
        <div class="partner-card__ring" :class="{ 'partner-card__ring--guild': p.kind === 'guild' }">
          <div class="partner-card__avatar" :style="avatarStyle(p)">
            <span v-if="!p.avatar_url">{{ initials(displayName(p)) }}</span>
          </div>
        </div>
        <h2 class="partner-card__name">{{ displayName(p) }}</h2>
        <div v-if="p.kind === 'guild' && p.member_count" class="partner-card__meta">
          {{ formatCount(p.member_count) }} {{ t('partners.members') }}
        </div>
        <p v-if="p.description" class="partner-card__bio">{{ p.description }}</p>
        <a
          v-if="p.kind === 'guild' && isHttp(p.invite_url)"
          :href="p.invite_url"
          target="_blank"
          rel="noopener noreferrer"
          class="partner-card__btn"
        >{{ t('partners.join') }}</a>
        <a
          v-else-if="isHttp(p.invite_url)"
          :href="p.invite_url"
          target="_blank"
          rel="noopener noreferrer"
          class="partner-card__btn partner-card__btn--ghost"
        >{{ t('partners.visit') }}</a>
      </article>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../services/api.js'
import { useI18n } from '../i18n/index.js'
import { useAutoRefresh } from '../composables/useAutoRefresh.js'
import { useSeo } from '../composables/useSeo.js'

const { t } = useI18n()
useSeo(() => ({ title: t('seo.partnersTitle'), description: t('seo.partnersDescription') }))
const partners = ref([])
const loading = ref(true)

function isHttp(u) { return typeof u === 'string' && /^https?:\/\//i.test(u) }

function displayName(p) {
  if (p.name && p.name.trim()) return p.name
  if (p.resolved_name && p.resolved_name !== 'unknown') {
    return p.kind === 'user' ? '@' + p.resolved_name : p.resolved_name
  }
  return '—'
}
function initials(name) {
  return String(name || '?').replace(/^@/, '').trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase()
}
function avatarStyle(p) {
  if (p.avatar_url) return { backgroundImage: `url('${p.avatar_url}')` }
  let h = 0
  for (const ch of String(displayName(p) || '')) h = (h * 31 + ch.charCodeAt(0)) % 360
  return { background: `linear-gradient(135deg, hsl(${h},60%,45%), hsl(${(h + 40) % 360},60%,55%))` }
}
function formatCount(n) {
  const v = Number(n) || 0
  if (v >= 1000) return (v / 1000).toFixed(v >= 10000 ? 0 : 1).replace(/\.0$/, '') + 'k'
  return String(v)
}

async function loadPartners() {
  try {
    const { data } = await api.get('/public/partners')
    partners.value = Array.isArray(data?.partners) ? data.partners : []
  } catch { partners.value = [] } finally { loading.value = false }
}

onMounted(loadPartners)
// Public read-only list — keep it fresh on focus/interval.
useAutoRefresh(loadPartners)
</script>

<style scoped>
.partners-page { max-width: 1040px; margin: 0 auto; padding: clamp(2rem, 6vw, 5rem) var(--space-5) 5rem; }
.partners-head { text-align: center; margin-bottom: var(--space-8); }
.partners-head__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-primary); margin-bottom: var(--space-3); }
.partners-head__title { font-family: var(--font-display); font-size: clamp(2rem, 5vw, 3rem); letter-spacing: -0.02em; margin-bottom: var(--space-3); }
.partners-head__sub { color: var(--color-text-muted); max-width: 40rem; margin: 0 auto; line-height: 1.6; }
.partners-state { text-align: center; color: var(--color-text-muted); padding: var(--space-8); }

.partners-grid { display: flex; flex-wrap: wrap; justify-content: center; gap: var(--space-5); }
.partner-card {
  position: relative; width: 268px; overflow: hidden;
  background: var(--color-surface); background-image: var(--gradient-card);
  border: 1px solid var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-7) var(--space-5) var(--space-6); text-align: center;
  box-shadow: var(--shadow-inset);
  display: flex; flex-direction: column; align-items: center;
  transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
}
.partner-card::before {
  content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 60%; height: 2px; border-radius: 2px;
  background: linear-gradient(90deg, transparent, var(--color-primary), transparent);
  opacity: 0.5; transition: opacity var(--transition), width var(--transition);
}
.partner-card:hover { transform: translateY(-6px); border-color: var(--color-primary-soft); box-shadow: 0 18px 40px -20px var(--color-primary-soft), var(--shadow-inset); }
.partner-card:hover::before { opacity: 1; width: 85%; }

.partner-card__kind {
  position: absolute; top: 12px; right: 12px;
  font-size: 0.62rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
  padding: 2px 8px; border-radius: var(--radius-full);
  color: var(--color-text-soft); background: var(--color-surface-2); border: 1px solid var(--color-border-strong);
}
.partner-card__kind--guild { color: var(--color-primary); background: var(--color-primary-soft); border-color: transparent; }

.partner-card__ring {
  width: 100px; height: 100px; margin: 0 auto var(--space-4); border-radius: 50%;
  padding: 3px; background: var(--gradient-brand);
  box-shadow: 0 8px 24px -8px var(--color-primary-soft);
  transition: transform var(--transition);
}
/* Guild avatars use a rounded-square look (like a server icon). */
.partner-card__ring--guild, .partner-card__ring--guild .partner-card__avatar { border-radius: 26px; }
.partner-card:hover .partner-card__ring { transform: scale(1.04); }
.partner-card__avatar {
  width: 100%; height: 100%; border-radius: 50%;
  background-size: cover; background-position: center;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-display); font-weight: 700; font-size: 1.8rem; color: #fff;
  border: 3px solid var(--color-surface);
}
.partner-card__name { font-family: var(--font-display); font-size: 1.25rem; font-weight: 700; letter-spacing: -0.01em; margin-bottom: var(--space-2); }
.partner-card__meta { font-size: 0.78rem; font-weight: 600; color: var(--color-text-soft); margin-bottom: var(--space-3); }
.partner-card__bio { font-size: 0.86rem; color: var(--color-text-muted); line-height: 1.55; margin-bottom: var(--space-4); }
.partner-card__btn {
  margin-top: auto; display: inline-flex; align-items: center; justify-content: center;
  padding: 8px 18px; border-radius: var(--radius-full); font-size: 0.85rem; font-weight: 700;
  color: #fff; background: var(--gradient-brand); border: 1px solid transparent;
  transition: transform var(--transition), box-shadow var(--transition), opacity var(--transition);
}
.partner-card__btn:hover { transform: translateY(-2px); box-shadow: 0 10px 24px -12px var(--color-primary-soft); }
.partner-card__btn--ghost { color: var(--color-text); background: var(--color-surface-2); border-color: var(--color-border-strong); }
</style>
