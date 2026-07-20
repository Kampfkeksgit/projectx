import { ref } from 'vue'
import api from '../services/api.js'
import { useI18n } from '../i18n/index.js'

/**
 * Operator / legal contact info (Impressum + Datenschutz).
 *
 * The sensitive owner PII (name, address, email, phone) is NOT hardcoded in the
 * locale files anymore — it lives in the DB (system_settings `legal_info`),
 * editable from the admin area. The legal texts keep {owner.*} placeholder tokens
 * which we substitute here after fetching GET /api/public/legal.
 *
 * Module-level cache: fetched once, shared across the Impressum/Privacy pages.
 */
const info = ref(null)
let loadPromise = null

function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function addressLine(i) {
  const cityLine = [i.postal_code, i.city].map((v) => (v || '').trim()).filter(Boolean).join(' ')
  return [i.street, cityLine, i.country].map((v) => (v || '').trim()).filter(Boolean).join(', ')
}

export function useLegalInfo() {
  const { t } = useI18n()

  function load() {
    if (info.value) return Promise.resolve(info.value)
    if (loadPromise) return loadPromise
    loadPromise = api
      .get('/public/legal')
      .then(({ data }) => {
        info.value = data || {}
        return info.value
      })
      .catch(() => {
        info.value = {}
        return info.value
      })
      .finally(() => { loadPromise = null })
    return loadPromise
  }

  /** Replace {owner.*} tokens in a bodyHtml string with the fetched values. */
  function resolve(html) {
    const i = info.value || {}
    const phone = (i.phone || '').trim()
    const phoneLine = phone ? `<li>${esc(t('legal.phoneLabel'))}: ${esc(phone)}</li>` : ''
    return String(html || '')
      .replace(/\{owner\.name\}/g, esc((i.name || '').trim()))
      .replace(/\{owner\.address\}/g, esc(addressLine(i)))
      .replace(/\{owner\.email\}/g, esc((i.email || '').trim()))
      .replace(/\{owner\.phoneLine\}/g, phoneLine)
  }

  return { info, load, resolve }
}
