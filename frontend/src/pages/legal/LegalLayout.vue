<template>
  <div class="legal-page">
    <article class="legal-page__article">
      <header class="legal-page__header">
        <p class="legal-page__updated">{{ t('legal.lastUpdated', { date: lastUpdated }) }}</p>
        <h1 class="legal-page__title">{{ title }}</h1>
        <p v-if="intro" class="legal-page__intro">{{ intro }}</p>
      </header>

      <nav v-if="showToc && sections && sections.length" class="legal-page__toc" :aria-label="t('legal.tocTitle')">
        <p class="legal-page__toc-title">{{ t('legal.tocTitle') }}</p>
        <ol class="legal-page__toc-list">
          <li v-for="s in sections" :key="s.id">
            <a :href="`#${s.id}`">{{ s.heading }}</a>
          </li>
        </ol>
      </nav>

      <div class="legal-page__body">
        <section
          v-for="s in sections"
          :key="s.id"
          :id="s.id"
          class="legal-section"
        >
          <h2 class="legal-section__heading">{{ s.heading }}</h2>
          <div class="legal-section__body" v-html="s.bodyHtml"></div>
        </section>
      </div>
    </article>
  </div>
</template>

<script setup>
import { useI18n } from '../../i18n/index.js'

defineProps({
  title: { type: String, required: true },
  intro: { type: String, default: '' },
  sections: { type: Array, required: true },
  lastUpdated: { type: String, required: true },
  showToc: { type: Boolean, default: false }
})

const { t } = useI18n()
</script>

<style scoped>
.legal-page {
  width: 100%;
  padding: var(--space-12) var(--space-6) var(--space-16);
  scroll-behavior: smooth;
}

.legal-page__article {
  max-width: 760px;
  margin: 0 auto;
  animation: fade-in 500ms var(--ease-out-expo) both;
}

.legal-page__header {
  margin-bottom: var(--space-10);
  padding-bottom: var(--space-6);
  border-bottom: 1px solid var(--color-border);
}

.legal-page__updated {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--color-text-soft);
  letter-spacing: 0.02em;
  margin-bottom: var(--space-3);
  text-transform: uppercase;
}

.legal-page__title {
  font-family: var(--font-display);
  font-size: clamp(2rem, 4vw, 2.8rem);
  font-weight: 700;
  letter-spacing: -0.025em;
  line-height: 1.1;
  margin-bottom: var(--space-4);
}

.legal-page__intro {
  font-size: 1.05rem;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.legal-page__toc {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5) var(--space-6);
  margin-bottom: var(--space-10);
}

.legal-page__toc-title {
  font-family: var(--font-display);
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-soft);
  margin-bottom: var(--space-3);
}

.legal-page__toc-list {
  list-style: none;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-5);
  margin: 0;
  padding: 0;
  counter-reset: tocitem;
}

.legal-page__toc-list li {
  font-size: 0.9rem;
  line-height: 1.4;
}

.legal-page__toc-list a {
  color: var(--color-text-muted);
  border-bottom: 1px solid transparent;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.legal-page__toc-list a:hover {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.legal-page__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
}

.legal-section {
  scroll-margin-top: calc(var(--nav-height) + var(--space-4));
}

.legal-section__heading {
  position: relative;
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin-bottom: var(--space-5);
  padding-left: var(--space-4);
}

.legal-section__heading::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.25em;
  bottom: 0.25em;
  width: 3px;
  border-radius: var(--radius-full);
  background: var(--gradient-brand);
}

.legal-section__body {
  color: var(--color-text-muted);
  font-size: 1rem;
  line-height: 1.75;
}

.legal-section__body :deep(p) {
  margin-bottom: var(--space-4);
}

.legal-section__body :deep(p:last-child) {
  margin-bottom: 0;
}

.legal-section__body :deep(ul) {
  list-style: disc;
  padding-left: var(--space-6);
  margin-bottom: var(--space-4);
}

.legal-section__body :deep(li) {
  margin-bottom: var(--space-2);
}

.legal-section__body :deep(li:last-child) {
  margin-bottom: 0;
}

.legal-section__body :deep(strong) {
  color: var(--color-text);
  font-weight: 600;
}

.legal-section__body :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 0.1em 0.45em;
  color: var(--color-text);
}

.legal-section__body :deep(a) {
  color: var(--color-primary);
  border-bottom: 1px solid var(--color-primary);
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.legal-section__body :deep(a:hover) {
  color: var(--color-primary-hover);
  border-bottom-color: var(--color-primary-hover);
}

@media (min-width: 960px) {
  .legal-page__toc--sticky {
    position: sticky;
    top: calc(var(--nav-height) + var(--space-4));
  }
}

@media (max-width: 720px) {
  .legal-page {
    padding: var(--space-8) var(--space-4) var(--space-12);
  }
  .legal-page__toc-list {
    grid-template-columns: 1fr;
  }
}
</style>
