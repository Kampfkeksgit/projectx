<template>
  <div class="loading-page">
    <div class="loading-page__inner">
      <div class="loading-page__orb" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
      <p class="loading-page__msg">{{ message || t('common.loading') }}</p>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

defineProps({
  message: { type: String, default: '' }
})
</script>

<style scoped>
.loading-page {
  min-height: calc(100vh - var(--nav-height));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
}

.loading-page__inner {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-5);
}

.loading-page__orb {
  display: inline-flex;
  gap: 8px;
}

.loading-page__orb span {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--gradient-brand);
  animation: bob 1.2s ease-in-out infinite both;
}

.loading-page__orb span:nth-child(2) { animation-delay: 0.15s; }
.loading-page__orb span:nth-child(3) { animation-delay: 0.3s; }

@keyframes bob {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.6; }
  40% { transform: translateY(-10px); opacity: 1; }
}

.loading-page__msg {
  color: var(--color-text-muted);
  font-size: 0.95rem;
  letter-spacing: 0.01em;
}
</style>
