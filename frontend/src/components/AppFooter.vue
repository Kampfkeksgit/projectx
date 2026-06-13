<template>
  <footer class="app-footer">
    <div class="app-footer__inner">
      <div class="app-footer__col app-footer__col--brand">
        <router-link to="/" class="app-footer__brand">
          <span class="app-footer__mark" aria-hidden="true">
            <span class="app-footer__mark-inner"></span>
          </span>
          <span class="app-footer__brand-text">ProjectX</span>
        </router-link>
        <div class="app-footer__meta">
          <span>{{ t('footer.copyright', { year }) }}</span>
          <span class="app-footer__dot" aria-hidden="true">·</span>
          <span class="app-footer__version">{{ t('footer.version') }}</span>
        </div>
      </div>

      <nav class="app-footer__col app-footer__col--legal" :aria-label="t('footer.legalSection')">
        <p class="app-footer__col-title">{{ t('footer.legalSection') }}</p>
        <ul class="app-footer__links">
          <li>
            <router-link to="/legal/impressum">{{ t('legal.impressum.title') }}</router-link>
          </li>
          <li>
            <router-link to="/legal/datenschutz">{{ t('legal.privacy.title') }}</router-link>
          </li>
          <li>
            <router-link to="/legal/agb">{{ t('legal.terms.title') }}</router-link>
          </li>
        </ul>
      </nav>

      <div class="app-footer__col app-footer__col--meta">
        <a
          class="app-footer__github"
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 .5C5.65.5.5 5.66.5 12.02c0 5.09 3.29 9.4 7.86 10.92.58.1.79-.25.79-.56v-2.1c-3.2.7-3.87-1.36-3.87-1.36-.52-1.33-1.28-1.68-1.28-1.68-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.46.11-3.05 0 0 .96-.31 3.15 1.18a10.94 10.94 0 0 1 5.74 0c2.19-1.49 3.15-1.18 3.15-1.18.63 1.59.23 2.76.12 3.05.74.81 1.18 1.83 1.18 3.09 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.13v3.16c0 .31.2.66.8.55A10.53 10.53 0 0 0 23.5 12.02C23.5 5.66 18.35.5 12 .5z"/>
          </svg>
          <span>{{ t('footer.github') }}</span>
        </a>
        <p class="app-footer__made">{{ t('footer.madeWith') }}</p>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const year = computed(() => new Date().getFullYear())
</script>

<style scoped>
.app-footer {
  margin-top: auto;
  padding: var(--space-10) var(--space-6) var(--space-8);
  border-top: 1px solid var(--color-border);
  background: rgba(11, 13, 18, 0.5);
  color: var(--color-text-muted);
  font-size: 0.88rem;
}

.app-footer__inner {
  max-width: var(--layout-max);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--space-8);
  align-items: flex-start;
}

.app-footer__col {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.app-footer__col--legal {
  align-items: center;
  text-align: center;
}

.app-footer__col--meta {
  align-items: flex-end;
  text-align: right;
}

.app-footer__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text);
  font-family: var(--font-display);
  font-weight: 700;
  letter-spacing: -0.015em;
}

.app-footer__mark {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--gradient-brand);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.app-footer__mark-inner {
  position: absolute;
  inset: 4px;
  background: var(--color-bg);
  border-radius: 3px;
}

.app-footer__brand-text {
  font-size: 0.95rem;
}

.app-footer__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 0.82rem;
  color: var(--color-text-soft);
}

.app-footer__dot {
  opacity: 0.5;
}

.app-footer__version {
  font-family: var(--font-mono);
}

.app-footer__col-title {
  font-family: var(--font-display);
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-text-soft);
  margin-bottom: var(--space-1);
}

.app-footer__links {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.app-footer__links a {
  color: var(--color-text-muted);
  transition: color var(--transition-fast);
}

.app-footer__links a:hover {
  color: var(--color-text);
}

.app-footer__github {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-muted);
  font-weight: 500;
  transition: color var(--transition-fast);
}

.app-footer__github:hover {
  color: var(--color-text);
}

.app-footer__made {
  font-size: 0.8rem;
  color: var(--color-text-soft);
  margin: 0;
}

@media (max-width: 720px) {
  .app-footer {
    padding: var(--space-8) var(--space-4);
  }
  .app-footer__inner {
    grid-template-columns: 1fr;
    gap: var(--space-6);
    text-align: center;
  }
  .app-footer__col,
  .app-footer__col--legal,
  .app-footer__col--meta {
    align-items: center;
    text-align: center;
  }
  .app-footer__brand {
    justify-content: center;
  }
}
</style>
