<template>
  <div v-if="page" class="fl">
    <header class="fl__hero">
      <RouterLink to="/" class="fl__brand">← Kampfkekse</RouterLink>
      <h1 class="fl__h1">{{ page.h1 }}</h1>
      <p class="fl__subtitle">{{ page.subtitle }}</p>
      <div class="fl__cta">
        <RouterLink to="/dashboard" class="fl__btn fl__btn--primary">Zum Dashboard</RouterLink>
        <RouterLink to="/" class="fl__btn fl__btn--ghost">Alle Module ansehen</RouterLink>
      </div>
    </header>

    <section class="fl__features">
      <div v-for="(f, i) in page.features" :key="i" class="fl__card">
        <div class="fl__card-icon">{{ f.icon }}</div>
        <h2 class="fl__card-title">{{ f.title }}</h2>
        <p class="fl__card-body">{{ f.body }}</p>
      </div>
    </section>

    <section class="fl__faq">
      <h2 class="fl__faq-heading">Häufige Fragen</h2>
      <details v-for="(item, i) in page.faq" :key="i" class="fl__faq-item">
        <summary class="fl__faq-q">{{ item.q }}</summary>
        <p class="fl__faq-a">{{ item.a }}</p>
      </details>
    </section>

    <section class="fl__bottom">
      <h2 class="fl__bottom-title">Bereit für {{ page.h1 }}?</h2>
      <RouterLink to="/" class="fl__btn fl__btn--primary">Jetzt kostenlos starten</RouterLink>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FEATURE_PAGES } from '../seo/featurePages.js'
import { useSeo } from '../composables/useSeo.js'

const props = defineProps({ slug: { type: String, required: true } })
const router = useRouter()

const page = computed(() => FEATURE_PAGES[props.slug] || null)

useSeo(() => (page.value
  ? { title: page.value.seoTitle, description: page.value.seoDescription }
  : {}))

// Unknown slug → send to the landing page.
onMounted(() => {
  if (!page.value) router.replace('/')
})

// FAQPage structured data for rich results — injected into <head>.
const LD_ID = 'fl-faq-jsonld'
function setFaqJsonLd() {
  let el = document.getElementById(LD_ID)
  if (!page.value) {
    if (el) el.remove()
    return
  }
  if (!el) {
    el = document.createElement('script')
    el.type = 'application/ld+json'
    el.id = LD_ID
    document.head.appendChild(el)
  }
  el.textContent = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: page.value.faq.map((f) => ({
      '@type': 'Question',
      name: f.q,
      acceptedAnswer: { '@type': 'Answer', text: f.a }
    }))
  })
}
onMounted(setFaqJsonLd)
watch(() => props.slug, setFaqJsonLd)
onUnmounted(() => {
  const el = document.getElementById(LD_ID)
  if (el) el.remove()
})
</script>

<style scoped>
.fl {
  max-width: 1000px;
  margin: 0 auto;
  padding: clamp(2rem, 6vw, 5rem) var(--space-4) 4rem;
}

.fl__brand {
  display: inline-block;
  color: var(--color-text-muted);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: var(--space-5);
}
.fl__brand:hover { color: var(--color-text); }

.fl__hero {
  text-align: center;
  margin-bottom: clamp(2.5rem, 6vw, 4.5rem);
}

.fl__h1 {
  font-family: var(--font-display);
  font-size: clamp(1.9rem, 5vw, 3.1rem);
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin: 0 0 var(--space-4);
  color: var(--color-text);
}

.fl__subtitle {
  font-size: clamp(1rem, 2.2vw, 1.25rem);
  color: var(--color-text-muted);
  max-width: 640px;
  margin: 0 auto var(--space-6);
  line-height: 1.6;
}

.fl__cta {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
  flex-wrap: wrap;
}

.fl__btn {
  display: inline-flex;
  align-items: center;
  padding: 0.7rem 1.3rem;
  border-radius: var(--radius-md);
  font-weight: 600;
  font-size: 0.95rem;
  text-decoration: none;
  transition: transform var(--transition), background var(--transition), border-color var(--transition);
}
.fl__btn:hover { transform: translateY(-1px); }

.fl__btn--primary {
  background: var(--color-primary);
  color: #fff;
}
.fl__btn--primary:hover { background: var(--color-primary-strong, var(--color-primary)); }

.fl__btn--ghost {
  background: transparent;
  color: var(--color-text);
  border: 1px solid var(--color-border-strong);
}
.fl__btn--ghost:hover { border-color: var(--color-primary); }

.fl__features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-4);
  margin-bottom: clamp(2.5rem, 6vw, 4rem);
}

.fl__card {
  background: var(--color-surface-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
}

.fl__card-icon { font-size: 1.6rem; margin-bottom: var(--space-3); }
.fl__card-title { font-size: 1.05rem; font-weight: 700; margin: 0 0 var(--space-2); color: var(--color-text); }
.fl__card-body { font-size: 0.92rem; color: var(--color-text-muted); line-height: 1.55; margin: 0; }

.fl__faq { max-width: 760px; margin: 0 auto clamp(2.5rem, 6vw, 4rem); }
.fl__faq-heading { text-align: center; font-family: var(--font-display); font-size: clamp(1.4rem, 3vw, 2rem); margin: 0 0 var(--space-5); color: var(--color-text); }

.fl__faq-item {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin-bottom: var(--space-3);
  background: var(--color-surface-1, var(--color-bg-elevated));
}
.fl__faq-q { font-weight: 600; cursor: pointer; color: var(--color-text); list-style-position: inside; }
.fl__faq-a { color: var(--color-text-muted); line-height: 1.6; margin: var(--space-3) 0 0; }

.fl__bottom { text-align: center; padding: clamp(2rem, 5vw, 3.5rem); background: var(--color-surface-2); border: 1px solid var(--color-border); border-radius: var(--radius-lg); }
.fl__bottom-title { font-family: var(--font-display); font-size: clamp(1.3rem, 3vw, 1.9rem); margin: 0 0 var(--space-5); color: var(--color-text); }
</style>
