// Per-route SEO for the SPA: sets document.title + meta description + canonical
// + OpenGraph/Twitter tags reactively. Without SSR the SPA otherwise serves the
// same index.html <title>/meta for every route — this differentiates the public
// pages (Google renders JS and picks these up). Dashboard/app routes stay on the
// default brand title (they're noindex via robots.txt anyway).
//
// Usage in a public page's <script setup>:
//   import { useSeo } from '../composables/useSeo.js'
//   useSeo(() => ({ title: t('seo.landingTitle'), description: t('seo.landingDescription') }))
// The getter is re-run reactively, so titles follow the i18n language switch.

import { watchEffect } from 'vue'
import { useRoute } from 'vue-router'

const SITE_URL = 'https://kampfkekse.eu'
const DEFAULT_TITLE = 'Kampfkekse (projectx) – Discord Bot Dashboard'
const DEFAULT_DESCRIPTION =
  'Kampfkekse (projectx) ist ein modernes Dashboard für deinen Discord-Bot: ' +
  'Willkommensnachrichten, Moderation, Leveling, Tickets, Statistiken und über ' +
  '30 weitere Module – einfach im Browser konfigurieren.'

function upsertMeta(key, attr, value) {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', value)
}

function upsertCanonical(href) {
  let el = document.head.querySelector('link[rel="canonical"]')
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', 'canonical')
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}

function applySeo({ title, description, path } = {}) {
  const t = title || DEFAULT_TITLE
  const d = description || DEFAULT_DESCRIPTION
  const clean = path && path !== '/' ? '/' + path.replace(/^\/+/, '').replace(/[?#].*$/, '') : '/'
  const url = SITE_URL + clean

  document.title = t
  upsertMeta('description', 'name', d)
  upsertMeta('og:title', 'property', t)
  upsertMeta('og:description', 'property', d)
  upsertMeta('og:url', 'property', url)
  upsertMeta('twitter:title', 'name', t)
  upsertMeta('twitter:description', 'name', d)
  upsertCanonical(url)
}

/** Reset to the default brand title/description for the given path. Called from
 * the router on every navigation so stale titles never persist on pages that
 * don't set their own SEO. */
export function resetSeo(path) {
  applySeo({ path })
}

/** Set page SEO. `source` is a getter returning { title, description } (so it
 * stays reactive to the i18n locale) or a plain object. */
export function useSeo(source) {
  const route = useRoute()
  watchEffect(() => {
    const v = typeof source === 'function' ? source() : source
    applySeo({ title: v && v.title, description: v && v.description, path: route.fullPath })
  })
}
