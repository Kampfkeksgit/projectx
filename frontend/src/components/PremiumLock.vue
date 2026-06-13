<template>
  <div class="lock">
    <div class="lock__card">
      <div class="lock__glow" aria-hidden="true"></div>
      <div class="lock__icon" :class="`lock__icon--${requiredTier}`" aria-hidden="true">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      </div>

      <span class="lock__tier" :class="`lock__tier--${requiredTier}`">{{ tierLabel }}</span>
      <h2 class="lock__title">{{ t('premiumLock.title') }}</h2>
      <p class="lock__body">{{ t('premiumLock.body', { tier: tierLabel }) }}</p>

      <div class="lock__cta">
        <AppButton variant="gradient" tag="router-link" :to="`/dashboard/${guildId}/premium`">
          <template #icon-left>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15 8.5 22 9.3 17 14 18.2 21 12 17.5 5.8 21 7 14 2 9.3 9 8.5 12 2"/></svg>
          </template>
          {{ t('premiumLock.upgrade') }}
        </AppButton>
        <router-link :to="`/dashboard/${guildId}`" class="lock__back">{{ t('premiumLock.back') }}</router-link>
      </div>

      <div class="lock__current">{{ t('premiumLock.current', { tier: currentLabel }) }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AppButton from './AppButton.vue'
import { usePremium } from '../stores/premium.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const premium = usePremium()

const props = defineProps({
  module: { type: String, required: true },
  guildId: { type: String, required: true }
})

const requiredTier = computed(() => premium.tierOf(props.module) || 'pro')
const tierLabel = computed(() => t(`premium.tiers.${requiredTier.value}.name`))
const currentLabel = computed(() => t(`premium.tiers.${premium.cache.tier || 'free'}.name`))
</script>

<style scoped>
.lock {
  display: flex;
  justify-content: center;
  padding: var(--space-10) var(--space-4);
}

.lock__card {
  position: relative;
  max-width: 520px;
  width: 100%;
  text-align: center;
  padding: var(--space-10) var(--space-8);
  border-radius: var(--radius-xl);
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border-strong);
  box-shadow: var(--shadow-lg), var(--shadow-inset);
  overflow: hidden;
}

.lock__glow {
  position: absolute;
  inset: -50% -20% auto -20%;
  height: 70%;
  background: radial-gradient(50% 70% at 50% 0%, rgba(167, 139, 250, 0.22) 0%, rgba(88, 101, 242, 0.12) 45%, transparent 75%);
  pointer-events: none;
  filter: blur(14px);
}

.lock__icon {
  position: relative;
  width: 64px;
  height: 64px;
  margin: 0 auto var(--space-5);
  border-radius: var(--radius-lg);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.lock__icon--basic { background: linear-gradient(135deg, #22d3ee, #6366f1); }
.lock__icon--pro { background: linear-gradient(135deg, #a78bfa, #ec4899); }

.lock__tier {
  position: relative;
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  color: #fff;
  margin-bottom: var(--space-4);
}
.lock__tier--basic { background: linear-gradient(135deg, #22d3ee, #6366f1); }
.lock__tier--pro { background: linear-gradient(135deg, #a78bfa, #ec4899); }

.lock__title {
  position: relative;
  font-size: clamp(1.4rem, 3vw, 1.9rem);
  letter-spacing: -0.02em;
  margin-bottom: var(--space-3);
}

.lock__body {
  position: relative;
  color: var(--color-text-muted);
  font-size: 1rem;
  line-height: 1.6;
  margin-bottom: var(--space-7);
}

.lock__cta {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.lock__back {
  color: var(--color-text-soft);
  font-size: 0.9rem;
  transition: color var(--transition-fast);
}
.lock__back:hover { color: var(--color-text); }

.lock__current {
  position: relative;
  margin-top: var(--space-6);
  font-size: 0.8rem;
  color: var(--color-text-soft);
}
</style>
