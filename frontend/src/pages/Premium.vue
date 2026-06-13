<template>
  <div class="prem">
    <header class="prem__head">
      <div class="prem__eyebrow">{{ t('premium.eyebrow') }}</div>
      <h1 class="prem__title">{{ t('premium.title') }}</h1>
      <p class="prem__sub">{{ t('premium.sub') }}</p>
    </header>

    <!-- Current tier banner -->
    <section class="current" :class="`current--${currentTier}`">
      <div class="current__icon" aria-hidden="true">
        <svg v-if="currentTier === 'free'" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg>
        <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15 8.5 22 9.3 17 14 18.2 21 12 17.5 5.8 21 7 14 2 9.3 9 8.5 12 2"/></svg>
      </div>
      <div class="current__body">
        <div class="current__label">{{ t('premium.currentPlan') }}</div>
        <div class="current__tier">{{ t(`premium.tiers.${currentTier}.name`) }}</div>
        <div v-if="premium.cache.until" class="current__until">{{ t('premium.renewsHint', { date: untilDate }) }}</div>
      </div>
      <span v-if="premium.cache.source" class="current__source">{{ t(`premium.source.${premium.cache.source}`) }}</span>
    </section>

    <!-- Plan cards -->
    <section class="plans">
      <article
        v-for="plan in plans"
        :key="plan.key"
        class="plan"
        :class="{ 'plan--current': plan.key === currentTier, 'plan--featured': plan.key === 'pro' }"
      >
        <div v-if="plan.key === 'pro'" class="plan__ribbon">{{ t('premium.popular') }}</div>
        <div class="plan__name" :class="`plan__name--${plan.key}`">{{ t(`premium.tiers.${plan.key}.name`) }}</div>
        <div class="plan__price">
          <span class="plan__amount">{{ plan.price === 0 ? t('premium.freePrice') : formatPrice(plan.price) }}</span>
          <span v-if="plan.price > 0" class="plan__per">{{ t('premium.perMonth') }}</span>
        </div>
        <p class="plan__tagline">{{ t(`premium.tiers.${plan.key}.tagline`) }}</p>

        <ul class="plan__perks">
          <li v-for="(perk, i) in t(`premium.tiers.${plan.key}.perks`)" :key="i" class="plan__perk">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            <span>{{ perk }}</span>
          </li>
        </ul>

        <div class="plan__cta">
          <span v-if="plan.key === currentTier" class="plan__btn plan__btn--current">{{ t('premium.yourPlan') }}</span>
          <AppButton v-else-if="rank(plan.key) > rank(currentTier)" variant="gradient" tag="a" :href="upgradeHref" :target="upgradeHref === '#' ? '_self' : '_blank'" rel="noopener noreferrer">
            {{ t('premium.choosePlan') }}
          </AppButton>
          <span v-else class="plan__btn plan__btn--owned">{{ t('premium.included') }}</span>
        </div>
      </article>
    </section>

    <p class="prem__note">{{ t('premium.upgradeNote') }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import api from '../services/api.js'
import { usePremium, TIER_RANK } from '../stores/premium.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const route = useRoute()
const premium = usePremium()

const guildId = computed(() => route.params.guild_id)
const currentTier = computed(() => premium.cache.tier || 'free')

// Pricing comes from the public catalog so it stays in sync with the backend.
const catalog = ref({ currency: 'EUR', tiers: [{ key: 'free', price_monthly: 0 }, { key: 'basic', price_monthly: 2.99 }, { key: 'pro', price_monthly: 5.99 }] })

const plans = computed(() =>
  ['free', 'basic', 'pro'].map((key) => ({
    key,
    price: catalog.value.tiers.find((tt) => tt.key === key)?.price_monthly ?? 0
  }))
)

function rank(tier) { return TIER_RANK[tier] ?? 0 }

function formatPrice(amount) {
  const cur = catalog.value.currency === 'EUR' ? '€' : (catalog.value.currency === 'USD' ? '$' : '')
  return `${cur}${Number(amount).toFixed(2)}`
}

const untilDate = computed(() => {
  if (!premium.cache.until) return ''
  try { return new Date(premium.cache.until * 1000).toLocaleDateString() } catch { return '' }
})

// Where "Choose plan" points. Discord SKU subscriptions are purchased inside the
// Discord client, so we deep-link to the app's store when configured; otherwise
// it's a no-op the owner can grant manually.
const upgradeHref = computed(() => {
  const appId = import.meta.env.VITE_DISCORD_CLIENT_ID
  return appId ? `https://discord.com/application-directory/${appId}/store` : '#'
})

async function loadPlans() {
  try {
    const { data } = await api.get('/public/plans')
    if (data?.tiers?.length) catalog.value = data
  } catch {
    // keep fallback prices
  }
}

onMounted(() => {
  loadPlans()
  if (guildId.value) premium.load(guildId.value)
})
</script>

<style scoped>
.prem__head { margin-bottom: var(--space-8); }
.prem__eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }
.prem__title { font-size: clamp(1.7rem, 3vw, 2.2rem); letter-spacing: -0.025em; margin-bottom: var(--space-2); }
.prem__sub { color: var(--color-text-muted); }

.current {
  display: flex; align-items: center; gap: var(--space-4);
  padding: var(--space-5) var(--space-6); margin-bottom: var(--space-7);
  border-radius: var(--radius-xl); border: 1px solid var(--color-border-strong);
  background: var(--color-surface); background-image: var(--gradient-card);
  box-shadow: var(--shadow-inset);
}
.current--basic { border-color: rgba(99, 102, 241, 0.4); }
.current--pro { border-color: rgba(167, 139, 250, 0.45); box-shadow: 0 0 30px -12px rgba(167, 139, 250, 0.4), var(--shadow-inset); }
.current__icon { width: 46px; height: 46px; flex-shrink: 0; border-radius: var(--radius-md); display: inline-flex; align-items: center; justify-content: center; color: #fff; background: linear-gradient(135deg, #5865f2, #a78bfa); }
.current--free .current__icon { background: var(--color-surface-2); color: var(--color-text-muted); }
.current__body { flex: 1; min-width: 0; }
.current__label { font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-soft); }
.current__tier { font-family: var(--font-display); font-size: 1.25rem; font-weight: 700; }
.current__until { font-size: 0.82rem; color: var(--color-text-muted); margin-top: 2px; }
.current__source { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-muted); background: var(--color-bg-elevated); border: 1px solid var(--color-border); padding: 4px 10px; border-radius: var(--radius-full); }

.plans { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-5); align-items: stretch; }

.plan {
  position: relative; display: flex; flex-direction: column;
  padding: var(--space-6); border-radius: var(--radius-xl);
  border: 1px solid var(--color-border); background: var(--color-surface);
  background-image: var(--gradient-card); box-shadow: var(--shadow-inset);
  transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
}
.plan:hover { transform: translateY(-3px); border-color: var(--color-border-strong); box-shadow: var(--shadow-lg), var(--shadow-inset); }
.plan--featured { border-color: rgba(167, 139, 250, 0.5); box-shadow: 0 0 40px -16px rgba(167, 139, 250, 0.5), var(--shadow-inset); }
.plan--current { outline: 2px solid var(--color-primary); outline-offset: 2px; }

.plan__ribbon { position: absolute; top: var(--space-4); right: var(--space-4); font-size: 0.64rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #fff; padding: 3px 8px; border-radius: var(--radius-full); background: linear-gradient(135deg, #a78bfa, #ec4899); }

.plan__name { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: var(--space-3); }
.plan__name--free { color: var(--color-text-muted); }
.plan__name--basic { color: #818cf8; }
.plan__name--pro { color: #c4b5fd; }

.plan__price { display: flex; align-items: baseline; gap: 6px; margin-bottom: var(--space-2); }
.plan__amount { font-family: var(--font-display); font-size: 2rem; font-weight: 700; letter-spacing: -0.02em; }
.plan__per { color: var(--color-text-soft); font-size: 0.85rem; }
.plan__tagline { color: var(--color-text-muted); font-size: 0.9rem; line-height: 1.5; margin-bottom: var(--space-5); min-height: 2.6em; }

.plan__perks { list-style: none; padding: 0; margin: 0 0 var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); flex: 1; }
.plan__perk { display: flex; align-items: flex-start; gap: var(--space-2); font-size: 0.9rem; color: var(--color-text); }
.plan__perk svg { color: var(--color-success); margin-top: 2px; flex-shrink: 0; }

.plan__cta { margin-top: auto; }
.plan__btn { display: block; text-align: center; padding: 0.7rem 1rem; border-radius: var(--radius-md); font-weight: 600; font-size: 0.92rem; }
.plan__btn--current { background: var(--color-primary-soft); color: #fff; }
.plan__btn--owned { background: var(--color-bg-elevated); color: var(--color-text-soft); border: 1px solid var(--color-border); }
.plan__cta :deep(.app-button) { width: 100%; }

.prem__note { margin-top: var(--space-6); font-size: 0.85rem; color: var(--color-text-muted); line-height: 1.6; background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-4) var(--space-5); }

@media (max-width: 820px) {
  .plans { grid-template-columns: 1fr; }
}
</style>
