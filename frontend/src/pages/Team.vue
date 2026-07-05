<template>
  <div class="team-page">
    <header class="team-head">
      <div class="team-head__eyebrow">{{ t('team.eyebrow') }}</div>
      <h1 class="team-head__title">{{ t('team.title') }}</h1>
      <p class="team-head__sub">{{ t('team.sub') }}</p>
    </header>

    <div v-if="loading" class="team-state">{{ t('common.loading') }}</div>
    <div v-else-if="!members.length" class="team-state">{{ t('team.empty') }}</div>

    <div v-else class="team-grid">
      <article v-for="m in members" :key="m.id" class="team-card">
        <div class="team-card__ring">
          <div class="team-card__avatar" :style="avatarStyle(m)">
            <span v-if="!m.avatar_url">{{ initials(displayName(m)) }}</span>
          </div>
        </div>
        <h2 class="team-card__name">{{ displayName(m) }}</h2>
        <div v-if="m.role" class="team-card__role">{{ m.role }}</div>
        <p v-if="m.bio" class="team-card__bio">{{ m.bio }}</p>
        <div v-if="socialLinks(m).length" class="team-card__socials">
          <a
            v-for="s in socialLinks(m)"
            :key="s.key"
            :href="s.url"
            target="_blank"
            rel="noopener noreferrer"
            class="team-social"
            :title="s.label"
            :aria-label="s.label"
            v-html="s.icon"
          ></a>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../services/api.js'
import { useI18n } from '../i18n/index.js'
import { useAutoRefresh } from '../composables/useAutoRefresh.js'

const { t } = useI18n()
const members = ref([])
const loading = ref(true)

// key → { label, icon(svg inner) }
const SOCIAL_META = {
  github: { label: 'GitHub', p: '<path d="M12 .5C5.65.5.5 5.66.5 12.02c0 5.09 3.29 9.4 7.86 10.92.58.1.79-.25.79-.56v-2.1c-3.2.7-3.87-1.36-3.87-1.36-.52-1.33-1.28-1.68-1.28-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.46.11-3.05 0 0 .96-.31 3.15 1.18a10.94 10.94 0 0 1 5.74 0c2.19-1.49 3.15-1.18 3.15-1.18.63 1.59.23 2.76.12 3.05.74.81 1.18 1.83 1.18 3.09 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.13v3.16c0 .31.2.66.8.55A10.53 10.53 0 0 0 23.5 12.02C23.5 5.66 18.35.5 12 .5z"/>' },
  twitter: { label: 'X / Twitter', p: '<path d="M18.9 2H22l-7.5 8.6L23 22h-6.9l-5.4-7-6.2 7H1.4l8-9.2L1 2h7l4.9 6.5L18.9 2zm-2.4 18h1.9L7.6 4H5.6l10.9 16z"/>' },
  youtube: { label: 'YouTube', p: '<path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0 .5 6.2C0 8.1 0 12 0 12s0 3.9.5 5.8a3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1c.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8zM9.6 15.6V8.4l6.2 3.6-6.2 3.6z"/>' },
  twitch: { label: 'Twitch', p: '<path d="M4 2 3 6v13h4v3h3l3-3h4l5-5V2H4zm16 9-3 3h-4l-3 3v-3H7V4h13v7zM16 6h-2v5h2V6zm-5 0H9v5h2V6z"/>' },
  instagram: { label: 'Instagram', p: '<rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17.5" cy="6.5" r="1.3"/>' },
  tiktok: { label: 'TikTok', p: '<path d="M16 3c.3 2.1 1.5 3.6 3.6 3.9v2.7c-1.3.1-2.5-.3-3.6-1v6.1a5.6 5.6 0 1 1-5.6-5.6c.3 0 .6 0 .9.1v2.8a2.8 2.8 0 1 0 2 2.7V3H16z"/>' },
  website: { label: 'Website', p: '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 12h18M12 3c2.5 2.5 3.5 6 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-6-3.5-9s1-6.5 3.5-9z" fill="none" stroke="currentColor" stroke-width="2"/>' }
}
const ORDER = ['github', 'twitter', 'youtube', 'twitch', 'instagram', 'tiktok', 'website']

function isHttp(u) { return typeof u === 'string' && /^https?:\/\//i.test(u) }

function socialLinks(m) {
  const out = []
  for (const key of ORDER) {
    const url = m.socials?.[key]
    if (isHttp(url) && SOCIAL_META[key]) {
      out.push({ key, url, label: SOCIAL_META[key].label, icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${SOCIAL_META[key].p}</svg>` })
    }
  }
  return out
}

function displayName(m) {
  if (m.name && m.name.trim()) return m.name
  if (m.discord_username && m.discord_username !== 'unknown') return '@' + m.discord_username
  return '—'
}
function initials(name) {
  return String(name || '?').replace(/^@/, '').trim().split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase()
}
function avatarStyle(m) {
  if (m.avatar_url) return { backgroundImage: `url('${m.avatar_url}')` }
  // Deterministic gradient from the name for the initials fallback.
  let h = 0
  for (const ch of String(m.name || '')) h = (h * 31 + ch.charCodeAt(0)) % 360
  return { background: `linear-gradient(135deg, hsl(${h},60%,45%), hsl(${(h + 40) % 360},60%,55%))` }
}

async function loadTeam() {
  try {
    const { data } = await api.get('/public/team')
    members.value = Array.isArray(data?.members) ? data.members : []
  } catch { members.value = [] } finally { loading.value = false }
}

onMounted(loadTeam)
// Public read-only list — keep it fresh on focus/interval.
useAutoRefresh(loadTeam)
</script>

<style scoped>
.team-page { max-width: 1040px; margin: 0 auto; padding: clamp(2rem, 6vw, 5rem) var(--space-5) 5rem; }
.team-head { text-align: center; margin-bottom: var(--space-8); }
.team-head__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-primary); margin-bottom: var(--space-3); }
.team-head__title { font-family: var(--font-display); font-size: clamp(2rem, 5vw, 3rem); letter-spacing: -0.02em; margin-bottom: var(--space-3); }
.team-head__sub { color: var(--color-text-muted); max-width: 40rem; margin: 0 auto; line-height: 1.6; }
.team-state { text-align: center; color: var(--color-text-muted); padding: var(--space-8); }

.team-grid { display: flex; flex-wrap: wrap; justify-content: center; gap: var(--space-5); }
.team-card {
  position: relative; width: 268px; overflow: hidden;
  background: var(--color-surface); background-image: var(--gradient-card);
  border: 1px solid var(--color-border); border-radius: var(--radius-xl);
  padding: var(--space-7) var(--space-5) var(--space-6); text-align: center;
  box-shadow: var(--shadow-inset);
  transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
}
/* Accent glow line along the top edge. */
.team-card::before {
  content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 60%; height: 2px; border-radius: 2px;
  background: linear-gradient(90deg, transparent, var(--color-primary), transparent);
  opacity: 0.5; transition: opacity var(--transition), width var(--transition);
}
.team-card:hover { transform: translateY(-6px); border-color: var(--color-primary-soft); box-shadow: 0 18px 40px -20px var(--color-primary-soft), var(--shadow-inset); }
.team-card:hover::before { opacity: 1; width: 85%; }

/* Gradient ring around the avatar. */
.team-card__ring {
  width: 100px; height: 100px; margin: 0 auto var(--space-4); border-radius: 50%;
  padding: 3px; background: var(--gradient-brand);
  box-shadow: 0 8px 24px -8px var(--color-primary-soft);
  transition: transform var(--transition);
}
.team-card:hover .team-card__ring { transform: scale(1.04); }
.team-card__avatar {
  width: 100%; height: 100%; border-radius: 50%;
  background-size: cover; background-position: center;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-display); font-weight: 700; font-size: 1.8rem; color: #fff;
  border: 3px solid var(--color-surface);
}
.team-card__name { font-family: var(--font-display); font-size: 1.25rem; font-weight: 700; letter-spacing: -0.01em; margin-bottom: var(--space-2); }
.team-card__role {
  display: inline-block; font-size: 0.74rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--color-primary); background: var(--color-primary-soft);
  padding: 3px 12px; border-radius: var(--radius-full); margin-bottom: var(--space-3);
}
.team-card__bio { font-size: 0.86rem; color: var(--color-text-muted); line-height: 1.55; margin-bottom: var(--space-4); }
.team-card__socials { display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }
.team-social { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: var(--radius-md); color: var(--color-text-soft); background: var(--color-surface-2); border: 1px solid var(--color-border-strong); transition: color var(--transition), background var(--transition), border-color var(--transition), transform var(--transition); }
.team-social:hover { color: #fff; background: var(--gradient-brand); border-color: transparent; transform: translateY(-3px); }
</style>
