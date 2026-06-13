<template>
  <div class="landing">
    <section class="hero">
      <div class="hero__glow" aria-hidden="true"></div>
      <div class="hero__inner">
        <div class="hero__pill">
          <span class="hero__pill-dot"></span>
          {{ t('landing.pill') }}
        </div>
        <h1 class="hero__title">
          {{ t('landing.titleStart') }}
          <span class="hero__title-grad">{{ t('landing.titleHighlight') }}</span>
        </h1>
        <p class="hero__sub">{{ t('landing.sub') }}</p>
        <div class="hero__cta">
          <AppButton variant="gradient" @click="auth.loginWithDiscord">
            <template #icon-left>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.32 4.37A19.79 19.79 0 0 0 16.43 3l-.2.35a14.7 14.7 0 0 1 4.13 1.65 14.42 14.42 0 0 0-12.72 0A14.7 14.7 0 0 1 11.77 3.35L11.57 3a19.79 19.79 0 0 0-3.89 1.37C5.31 7.97 4.55 11.49 4.78 14.94a19.95 19.95 0 0 0 5.99 3.06l.86-1.18a12.7 12.7 0 0 1-2.13-1.04c.18-.13.35-.27.52-.41a10.3 10.3 0 0 0 7.96 0c.17.14.34.28.52.41-.68.42-1.4.78-2.13 1.04l.86 1.18a19.95 19.95 0 0 0 5.99-3.06c.27-3.97-.62-7.47-2.9-10.57ZM9.55 13.36c-.95 0-1.72-.89-1.72-1.98 0-1.1.76-1.99 1.72-1.99.97 0 1.74.89 1.72 1.99 0 1.09-.75 1.98-1.72 1.98Zm4.9 0c-.95 0-1.72-.89-1.72-1.98 0-1.1.76-1.99 1.72-1.99.97 0 1.74.89 1.72 1.99 0 1.09-.75 1.98-1.72 1.98Z"/></svg>
            </template>
            {{ t('nav.loginWithDiscord') }}
          </AppButton>
          <a href="#features" class="hero__secondary">{{ t('landing.exploreFeatures') }}</a>
        </div>

        <div class="hero__preview">
          <DiscordMessagePreview
            channel-name="welcome"
            :message="t('landing.previewMessage')"
            username="Alex"
            guild-name="ProjectX HQ"
          />
        </div>
      </div>
    </section>

    <!-- Stats strip — live data from the bot -->
    <section class="stats">
      <div class="stats__inner" :class="{ 'is-offline': stats && !stats.online }">
        <div class="stat">
          <div class="stat__value">{{ formatNumber(stats?.servers) }}</div>
          <div class="stat__label">{{ t('landing.stats.serversLabel') }}</div>
        </div>
        <div class="stat">
          <div class="stat__value">{{ formatNumber(stats?.users) }}</div>
          <div class="stat__label">{{ t('landing.stats.usersLabel') }}</div>
        </div>
        <div class="stat">
          <div class="stat__value">{{ formatUptime(stats?.uptime_seconds) }}</div>
          <div class="stat__label">
            {{ t('landing.stats.uptimeLabel') }}
            <span v-if="stats && !stats.online" class="stat__offline-dot" :title="t('landing.stats.botOffline')"></span>
          </div>
        </div>
      </div>
    </section>

    <!-- Module showcase — all 8 modules -->
    <section class="modules" id="features">
      <div class="modules__inner">
        <div class="modules__head">
          <div class="modules__eyebrow">{{ t('landing.modules.eyebrow') }}</div>
          <h2 class="modules__title">{{ t('landing.modules.title') }}</h2>
          <p class="modules__sub">{{ t('landing.modules.sub') }}</p>
        </div>
        <div class="modules__grid">
          <article
            v-for="m in modules"
            :key="m.key"
            class="module-card"
          >
            <div class="module-card__top">
              <div class="module-card__icon" :class="`module-card__icon--${m.tone}`" v-html="m.icon" aria-hidden="true"></div>
              <span class="module-card__tier" :class="`module-card__tier--${m.tier}`">{{ tierLabel(m.tier) }}</span>
            </div>
            <h3 class="module-card__title">{{ t(`landing.modules.${m.key}Title`) }}</h3>
            <p class="module-card__body">{{ t(`landing.modules.${m.key}Body`) }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- Pricing -->
    <section class="pricing" id="pricing">
      <div class="pricing__inner">
        <div class="pricing__head">
          <div class="pricing__eyebrow">{{ t('landing.pricing.eyebrow') }}</div>
          <h2 class="pricing__title">{{ t('landing.pricing.title') }}</h2>
          <p class="pricing__sub">{{ t('landing.pricing.sub') }}</p>
        </div>

        <div class="pricing__grid">
          <article
            v-for="plan in pricingPlans"
            :key="plan.key"
            class="price-card"
            :class="{ 'price-card--featured': plan.key === 'pro' }"
          >
            <div v-if="plan.key === 'pro'" class="price-card__ribbon">{{ t('landing.pricing.popular') }}</div>
            <div class="price-card__name" :class="`price-card__name--${plan.key}`">{{ t(`premium.tiers.${plan.key}.name`) }}</div>
            <div class="price-card__price">
              <span class="price-card__amount">{{ plan.price === 0 ? t('landing.pricing.freePrice') : formatPrice(plan.price) }}</span>
              <span v-if="plan.price > 0" class="price-card__per">{{ t('landing.pricing.perMonth') }}</span>
            </div>
            <p class="price-card__tagline">{{ t(`premium.tiers.${plan.key}.tagline`) }}</p>
            <ul class="price-card__perks">
              <li v-for="(perk, i) in t(`premium.tiers.${plan.key}.perks`)" :key="i">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                <span>{{ perk }}</span>
              </li>
            </ul>
            <AppButton class="price-card__cta" :variant="plan.key === 'free' ? 'ghost' : 'gradient'" @click="auth.loginWithDiscord">
              {{ plan.key === 'pro' ? t('landing.pricing.ctaPro') : t('landing.pricing.cta') }}
            </AppButton>
          </article>
        </div>
        <p class="pricing__note">{{ t('landing.pricing.note') }}</p>
      </div>
    </section>

    <!-- How it works -->
    <section class="how">
      <div class="how__inner">
        <div class="how__head">
          <div class="how__eyebrow">{{ t('landing.howItWorks.eyebrow') }}</div>
          <h2 class="how__title">{{ t('landing.howItWorks.title') }}</h2>
        </div>
        <ol class="how__steps">
          <li class="how__step">
            <div class="how__step-num">1</div>
            <h3 class="how__step-title">{{ t('landing.howItWorks.step1Title') }}</h3>
            <p class="how__step-body">{{ t('landing.howItWorks.step1Body') }}</p>
          </li>
          <li class="how__step how__step--connector">
            <div class="how__step-num">2</div>
            <h3 class="how__step-title">{{ t('landing.howItWorks.step2Title') }}</h3>
            <p class="how__step-body">{{ t('landing.howItWorks.step2Body') }}</p>
          </li>
          <li class="how__step how__step--connector">
            <div class="how__step-num">3</div>
            <h3 class="how__step-title">{{ t('landing.howItWorks.step3Title') }}</h3>
            <p class="how__step-body">{{ t('landing.howItWorks.step3Body') }}</p>
          </li>
        </ol>
      </div>
    </section>

    <!-- FAQ -->
    <section class="faq">
      <div class="faq__inner">
        <div class="faq__head">
          <div class="faq__eyebrow">{{ t('landing.faq.eyebrow') }}</div>
          <h2 class="faq__title">{{ t('landing.faq.title') }}</h2>
        </div>
        <div class="faq__list">
          <details v-for="n in 4" :key="n" class="faq__item">
            <summary class="faq__q">
              {{ t(`landing.faq.q${n}`) }}
              <svg class="faq__chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </summary>
            <p class="faq__a">{{ t(`landing.faq.a${n}`) }}</p>
          </details>
        </div>
      </div>
    </section>

    <!-- Final CTA -->
    <section class="final-cta">
      <div class="final-cta__inner">
        <div class="final-cta__glow" aria-hidden="true"></div>
        <h2 class="final-cta__title">{{ t('landing.finalCta.title') }}</h2>
        <p class="final-cta__sub">{{ t('landing.finalCta.sub') }}</p>
        <AppButton variant="gradient" @click="auth.loginWithDiscord">
          <template #icon-left>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.32 4.37A19.79 19.79 0 0 0 16.43 3l-.2.35a14.7 14.7 0 0 1 4.13 1.65 14.42 14.42 0 0 0-12.72 0A14.7 14.7 0 0 1 11.77 3.35L11.57 3a19.79 19.79 0 0 0-3.89 1.37C5.31 7.97 4.55 11.49 4.78 14.94a19.95 19.95 0 0 0 5.99 3.06l.86-1.18a12.7 12.7 0 0 1-2.13-1.04c.18-.13.35-.27.52-.41a10.3 10.3 0 0 0 7.96 0c.17.14.34.28.52.41-.68.42-1.4.78-2.13 1.04l.86 1.18a19.95 19.95 0 0 0 5.99-3.06c.27-3.97-.62-7.47-2.9-10.57ZM9.55 13.36c-.95 0-1.72-.89-1.72-1.98 0-1.1.76-1.99 1.72-1.99.97 0 1.74.89 1.72 1.99 0 1.09-.75 1.98-1.72 1.98Zm4.9 0c-.95 0-1.72-.89-1.72-1.98 0-1.1.76-1.99 1.72-1.99.97 0 1.74.89 1.72 1.99 0 1.09-.75 1.98-1.72 1.98Z"/></svg>
          </template>
          {{ t('landing.finalCta.button') }}
        </AppButton>
      </div>
    </section>

  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import AppButton from '../components/AppButton.vue'
import DiscordMessagePreview from '../components/DiscordMessagePreview.vue'
import api from '../services/api.js'
import { useAuth } from '../stores/auth.js'
import { useI18n } from '../i18n/index.js'

const auth = useAuth()
const { t } = useI18n()

// --- Live stats ---
const stats = ref(null)
let statsTimer = null

// --- Plans / pricing (public catalog) ---
const catalog = ref({ currency: 'EUR', tiers: [{ key: 'free', price_monthly: 0 }, { key: 'basic', price_monthly: 2.99 }, { key: 'pro', price_monthly: 5.99 }] })

const pricingPlans = computed(() =>
  ['free', 'basic', 'pro'].map((key) => ({
    key,
    price: catalog.value.tiers.find((tt) => tt.key === key)?.price_monthly ?? 0
  }))
)

function formatPrice(amount) {
  const cur = catalog.value.currency === 'EUR' ? '€' : (catalog.value.currency === 'USD' ? '$' : '')
  return `${cur}${Number(amount).toFixed(2)}`
}

function tierLabel(tier) {
  return t(`landing.modules.tier${tier.charAt(0).toUpperCase()}${tier.slice(1)}`)
}

async function loadStats() {
  try {
    const { data } = await api.get('/public/stats')
    if (data) stats.value = data
  } catch {
    // Public endpoint failure (backend down, network) — leave stats null,
    // template falls back to "—".
  }
}

async function loadPlans() {
  try {
    const { data } = await api.get('/public/plans')
    if (data?.tiers?.length) catalog.value = data
  } catch {
    // keep fallback prices
  }
}

function formatNumber(n) {
  if (n == null) return '—'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + 'k'
  return String(n)
}

function formatUptime(seconds) {
  if (!seconds || seconds <= 0) return '—'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

onMounted(() => {
  loadStats()
  loadPlans()
  // Refresh the live values once per minute so uptime keeps ticking
  // without forcing the user to reload.
  statsTimer = setInterval(loadStats, 60_000)
})

onBeforeUnmount(() => {
  if (statsTimer) clearInterval(statsTimer)
})

// Module-Showcase — each module's icon + tone + tier badge.
// `key` maps to landing.modules.<key>Title / landing.modules.<key>Body in i18n.
// `tier` mirrors the backend MODULE_TIERS so the badges stay accurate.
const modules = [
  { key: 'welcome', tier: 'free', tone: 'indigo', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/></svg>' },
  { key: 'leave', tier: 'free', tone: 'pink', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="22" y1="11" x2="16" y2="11"/></svg>' },
  { key: 'autorole', tier: 'free', tone: 'violet', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>' },
  { key: 'moderation', tier: 'free', tone: 'amber', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="16" x2="12" y2="16"/></svg>' },
  { key: 'logs', tier: 'free', tone: 'cyan', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/><line x1="8" y1="9" x2="10" y2="9"/></svg>' },
  { key: 'reactionRoles', tier: 'free', tone: 'magenta', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>' },
  { key: 'verification', tier: 'free', tone: 'emerald', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg>' },
  { key: 'suggestions', tier: 'free', tone: 'sky', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>' },
  { key: 'customCommands', tier: 'free', tone: 'sky', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>' },
  { key: 'leveling', tier: 'basic', tone: 'emerald', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>' },
  { key: 'starboard', tier: 'basic', tone: 'amber', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>' },
  { key: 'tempvoice', tier: 'basic', tone: 'violet', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>' },
  { key: 'birthday', tier: 'basic', tone: 'pink', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-8a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8"/><path d="M4 16s.5-1 2-1 2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2-1 2-1"/><path d="M2 21h20"/><path d="M7 8v3M12 8v3M17 8v3"/></svg>' },
  { key: 'rolemenus', tier: 'basic', tone: 'magenta', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="4" rx="1"/><rect x="3" y="10" width="18" height="4" rx="1"/><rect x="3" y="16" width="18" height="4" rx="1"/></svg>' },
  { key: 'antiraid', tier: 'basic', tone: 'amber', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>' },
  { key: 'social', tier: 'pro', tone: 'magenta', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg>' },
  { key: 'stats', tier: 'pro', tone: 'cyan', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>' },
  { key: 'tickets', tier: 'pro', tone: 'indigo', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"/></svg>' },
  { key: 'giveaways', tier: 'pro', tone: 'amber', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 12 20 22 4 22 4 12"/><rect x="2" y="7" width="20" height="5"/><line x1="12" y1="22" x2="12" y2="7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/></svg>' },
  { key: 'scheduled', tier: 'pro', tone: 'sky', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg>' }
]
</script>

<style scoped>
.landing {
  position: relative;
  width: 100%;
  overflow: hidden;
}

/* ---------- Hero ---------- */
.hero {
  position: relative;
  padding: var(--space-20) var(--space-6) var(--space-16);
}

.hero__glow {
  position: absolute;
  inset: 0;
  background: var(--gradient-hero-glow);
  pointer-events: none;
  z-index: 0;
}

.hero__inner {
  position: relative;
  z-index: 1;
  max-width: var(--layout-max);
  margin: 0 auto;
  text-align: center;
  animation: fade-in 600ms var(--ease-out-expo) both;
}

.hero__pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.4rem 0.9rem;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--color-border);
  font-size: 0.78rem;
  color: var(--color-text-muted);
  margin-bottom: var(--space-5);
}

.hero__pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--gradient-brand);
  box-shadow: 0 0 0 3px rgba(88, 101, 242, 0.18);
}

.hero__title {
  font-family: var(--font-display);
  font-size: clamp(2.2rem, 6vw, 4rem);
  line-height: 1.05;
  letter-spacing: -0.035em;
  font-weight: 700;
  margin-bottom: var(--space-5);
  max-width: 920px;
  margin-left: auto;
  margin-right: auto;
}

.hero__title-grad {
  background: var(--gradient-brand);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  display: inline-block;
}

.hero__sub {
  max-width: 620px;
  margin: 0 auto var(--space-8);
  font-size: 1.08rem;
  color: var(--color-text-muted);
  line-height: 1.6;
}

.hero__cta {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
  justify-content: center;
}

.hero__secondary {
  color: var(--color-text-muted);
  font-weight: 500;
  font-size: 0.95rem;
  transition: color var(--transition-fast);
}
.hero__secondary:hover {
  color: var(--color-text);
}

.hero__preview {
  max-width: 540px;
  margin: var(--space-12) auto 0;
  border-radius: var(--radius-xl);
  padding: 8px;
  background: linear-gradient(140deg, rgba(88, 101, 242, 0.4), rgba(167, 139, 250, 0.2), rgba(34, 211, 238, 0.25));
  box-shadow: 0 30px 60px -20px rgba(88, 101, 242, 0.4);
  transform: perspective(1200px) rotateX(4deg);
}

/* ---------- Stats strip ---------- */
.stats {
  position: relative;
  z-index: 1;
  padding: 0 var(--space-6);
  margin-top: calc(-1 * var(--space-8));
}

.stats__inner {
  max-width: var(--layout-max);
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  padding: var(--space-5) var(--space-4);
  background: rgba(22, 26, 35, 0.72);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  transition: opacity var(--transition);
}

.stats__inner.is-offline {
  opacity: 0.78;
}

.stat__offline-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-left: 4px;
  border-radius: 50%;
  background: var(--color-warning, #f59e0b);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
  vertical-align: middle;
}

.stat {
  text-align: center;
  padding: var(--space-2) var(--space-4);
  border-right: 1px solid var(--color-border-soft);
}
.stat:last-child { border-right: none; }

.stat__value {
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 3.4vw, 2.4rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  background: var(--gradient-brand);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  line-height: 1.05;
}

.stat__label {
  font-size: 0.78rem;
  color: var(--color-text-soft);
  margin-top: var(--space-1);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

/* ---------- Modules showcase ---------- */
.modules {
  padding: var(--space-16) var(--space-6) var(--space-12);
  position: relative;
  z-index: 1;
}

.modules__inner {
  max-width: var(--layout-max);
  margin: 0 auto;
}

.modules__head {
  text-align: center;
  margin-bottom: var(--space-10);
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
}

.modules__eyebrow {
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-soft);
  margin-bottom: var(--space-3);
}

.modules__title {
  font-size: clamp(1.8rem, 3.4vw, 2.6rem);
  letter-spacing: -0.025em;
  margin-bottom: var(--space-3);
}

.modules__sub {
  color: var(--color-text-muted);
  font-size: 1.02rem;
  line-height: 1.6;
}

.modules__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--space-4);
}

.module-card {
  position: relative;
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5) var(--space-5) var(--space-6);
  transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
  box-shadow: var(--shadow-inset);
  overflow: hidden;
}

.module-card::after {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  padding: 1px;
  background: var(--gradient-brand);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
          mask-composite: exclude;
  opacity: 0;
  transition: opacity var(--transition);
  pointer-events: none;
}

.module-card:hover {
  transform: translateY(-4px);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-lg), var(--shadow-inset);
}
.module-card:hover::after { opacity: 1; }

.module-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.module-card__icon {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.module-card__tier {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-border-strong);
  color: var(--color-text-soft);
}
.module-card__tier--basic { color: #a5b4fc; border-color: rgba(99, 102, 241, 0.5); }
.module-card__tier--pro { color: #c4b5fd; border-color: rgba(167, 139, 250, 0.55); background: rgba(167, 139, 250, 0.08); }

.module-card__icon--indigo  { background: linear-gradient(135deg, #5865f2, #818cf8); }
.module-card__icon--pink    { background: linear-gradient(135deg, #f472b6, #a78bfa); }
.module-card__icon--violet  { background: linear-gradient(135deg, #a78bfa, #7c3aed); }
.module-card__icon--cyan    { background: linear-gradient(135deg, #22d3ee, #5865f2); }
.module-card__icon--amber   { background: linear-gradient(135deg, #f59e0b, #f472b6); }
.module-card__icon--magenta { background: linear-gradient(135deg, #ec4899, #a78bfa); }
.module-card__icon--emerald { background: linear-gradient(135deg, #10b981, #22d3ee); }
.module-card__icon--sky     { background: linear-gradient(135deg, #0ea5e9, #6366f1); }

.module-card__title {
  font-size: 1.05rem;
  margin-bottom: var(--space-2);
  letter-spacing: -0.015em;
}

.module-card__body {
  color: var(--color-text-muted);
  font-size: 0.91rem;
  line-height: 1.55;
}

/* ---------- Pricing ---------- */
.pricing {
  padding: var(--space-12) var(--space-6) var(--space-14);
  position: relative;
  z-index: 1;
}
.pricing__inner { max-width: var(--layout-max); margin: 0 auto; }
.pricing__head { text-align: center; max-width: 680px; margin: 0 auto var(--space-10); }
.pricing__eyebrow { font-size: 0.78rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-3); }
.pricing__title { font-size: clamp(1.8rem, 3.4vw, 2.6rem); letter-spacing: -0.025em; margin-bottom: var(--space-3); }
.pricing__sub { color: var(--color-text-muted); font-size: 1.02rem; line-height: 1.6; }

.pricing__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-5);
  align-items: stretch;
  max-width: 980px;
  margin: 0 auto;
}

.price-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: var(--space-7) var(--space-6);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  background-image: var(--gradient-card);
  box-shadow: var(--shadow-inset);
  transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
}
.price-card:hover { transform: translateY(-4px); border-color: var(--color-border-strong); box-shadow: var(--shadow-lg), var(--shadow-inset); }
.price-card--featured { border-color: rgba(167, 139, 250, 0.5); box-shadow: 0 0 50px -18px rgba(167, 139, 250, 0.55), var(--shadow-inset); }

.price-card__ribbon { position: absolute; top: var(--space-5); right: var(--space-5); font-size: 0.62rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #fff; padding: 3px 9px; border-radius: var(--radius-full); background: linear-gradient(135deg, #a78bfa, #ec4899); }

.price-card__name { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: var(--space-4); }
.price-card__name--free { color: var(--color-text-muted); }
.price-card__name--basic { color: #818cf8; }
.price-card__name--pro { color: #c4b5fd; }

.price-card__price { display: flex; align-items: baseline; gap: 6px; margin-bottom: var(--space-2); }
.price-card__amount { font-family: var(--font-display); font-size: 2.2rem; font-weight: 700; letter-spacing: -0.02em; }
.price-card__per { color: var(--color-text-soft); font-size: 0.9rem; }
.price-card__tagline { color: var(--color-text-muted); font-size: 0.92rem; line-height: 1.5; margin-bottom: var(--space-5); min-height: 2.7em; }

.price-card__perks { list-style: none; padding: 0; margin: 0 0 var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); flex: 1; }
.price-card__perks li { display: flex; align-items: flex-start; gap: var(--space-2); font-size: 0.92rem; color: var(--color-text); }
.price-card__perks svg { color: var(--color-success); margin-top: 3px; flex-shrink: 0; }

.price-card__cta { width: 100%; margin-top: auto; }

.pricing__note { text-align: center; color: var(--color-text-soft); font-size: 0.86rem; margin-top: var(--space-7); max-width: 620px; margin-left: auto; margin-right: auto; line-height: 1.6; }

/* ---------- FAQ ---------- */
.faq { padding: var(--space-12) var(--space-6); position: relative; z-index: 1; }
.faq__inner { max-width: 820px; margin: 0 auto; }
.faq__head { text-align: center; margin-bottom: var(--space-9); }
.faq__eyebrow { font-size: 0.78rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-3); }
.faq__title { font-size: clamp(1.8rem, 3.4vw, 2.6rem); letter-spacing: -0.025em; }
.faq__list { display: flex; flex-direction: column; gap: var(--space-3); }
.faq__item { border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-surface); padding: 0 var(--space-5); transition: border-color var(--transition); }
.faq__item[open] { border-color: var(--color-border-strong); }
.faq__q { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); cursor: pointer; list-style: none; padding: var(--space-4) 0; font-weight: 600; font-size: 1rem; color: var(--color-text); }
.faq__q::-webkit-details-marker { display: none; }
.faq__chevron { color: var(--color-text-soft); flex-shrink: 0; transition: transform var(--transition); }
.faq__item[open] .faq__chevron { transform: rotate(180deg); }
.faq__a { color: var(--color-text-muted); font-size: 0.94rem; line-height: 1.6; padding: 0 0 var(--space-5); margin: 0; }

/* ---------- How it works ---------- */
.how {
  padding: var(--space-14) var(--space-6);
  position: relative;
  z-index: 1;
}

.how__inner {
  max-width: var(--layout-max);
  margin: 0 auto;
}

.how__head {
  text-align: center;
  margin-bottom: var(--space-10);
}

.how__eyebrow {
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-soft);
  margin-bottom: var(--space-3);
}

.how__title {
  font-size: clamp(1.8rem, 3.4vw, 2.6rem);
  letter-spacing: -0.025em;
}

.how__steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-5);
  list-style: none;
  padding: 0;
}

.how__step {
  position: relative;
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  box-shadow: var(--shadow-inset);
}

/* Connector dots between steps on wide screens */
.how__step--connector::before {
  content: '';
  position: absolute;
  left: calc(-1 * var(--space-5) - 4px);
  top: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--gradient-brand);
  box-shadow: 0 0 0 4px rgba(88, 101, 242, 0.18);
  transform: translateY(-50%);
}

.how__step-num {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 1.05rem;
  background: var(--gradient-brand);
  color: #fff;
  margin-bottom: var(--space-4);
  box-shadow: 0 6px 20px -6px rgba(88, 101, 242, 0.45);
}

.how__step-title {
  font-size: 1.08rem;
  margin-bottom: var(--space-2);
  letter-spacing: -0.015em;
}

.how__step-body {
  color: var(--color-text-muted);
  font-size: 0.93rem;
  line-height: 1.55;
}

/* ---------- Final CTA ---------- */
.final-cta {
  padding: var(--space-12) var(--space-6) var(--space-16);
  position: relative;
  z-index: 1;
}

.final-cta__inner {
  position: relative;
  max-width: 760px;
  margin: 0 auto;
  text-align: center;
  padding: var(--space-12) var(--space-8);
  border-radius: var(--radius-xl);
  background: linear-gradient(140deg, rgba(88, 101, 242, 0.16), rgba(167, 139, 250, 0.10), rgba(34, 211, 238, 0.12));
  border: 1px solid var(--color-border-strong);
  overflow: hidden;
  box-shadow: var(--shadow-lg), var(--shadow-inset);
}

.final-cta__glow {
  position: absolute;
  inset: -40% -10% 40% -10%;
  background: radial-gradient(50% 60% at 50% 0%, rgba(88, 101, 242, 0.28) 0%, rgba(167, 139, 250, 0.14) 45%, transparent 75%);
  pointer-events: none;
  filter: blur(20px);
}

.final-cta__title {
  position: relative;
  font-size: clamp(2rem, 4vw, 2.8rem);
  letter-spacing: -0.03em;
  margin-bottom: var(--space-3);
}

.final-cta__sub {
  position: relative;
  color: var(--color-text-muted);
  font-size: 1.05rem;
  margin-bottom: var(--space-7);
  line-height: 1.5;
}

.final-cta .app-button {
  position: relative;
  padding: 0.85rem 1.6rem;
  font-size: 1rem;
}

/* ---------- Responsive ---------- */
@media (max-width: 900px) {
  .how__steps {
    grid-template-columns: 1fr;
  }
  .how__step--connector::before { display: none; }
  .pricing__grid {
    grid-template-columns: 1fr;
    max-width: 440px;
  }
}

@media (max-width: 560px) {
  .stats__inner {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .stat {
    border-right: none;
    border-bottom: 1px solid var(--color-border-soft);
    padding: var(--space-3);
  }
  .stat:last-child { border-bottom: none; }
}

@media (max-width: 640px) {
  .hero {
    padding: var(--space-12) var(--space-4) var(--space-10);
  }
  .modules {
    padding: var(--space-12) var(--space-4) var(--space-8);
  }
  .how, .final-cta {
    padding-left: var(--space-4);
    padding-right: var(--space-4);
  }
  .hero__preview {
    transform: none;
  }
  .final-cta__inner {
    padding: var(--space-8) var(--space-5);
  }
}
</style>
