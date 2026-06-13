import { ref } from 'vue'
import en from './locales/en.js'
import de from './locales/de.js'

const messages = { en, de }

export const SUPPORTED_LOCALES = [
  { code: 'en', label: 'English', flag: 'EN' },
  { code: 'de', label: 'Deutsch', flag: 'DE' }
]

const STORAGE_KEY = 'projectx_locale'
const SUPPORTED = SUPPORTED_LOCALES.map(l => l.code)

function detectInitial() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && SUPPORTED.includes(stored)) return stored
  } catch {
    // localStorage might be unavailable (private mode, SSR)
  }
  const nav = (typeof navigator !== 'undefined' && navigator.language ? navigator.language : 'en').slice(0, 2).toLowerCase()
  return SUPPORTED.includes(nav) ? nav : 'en'
}

export const locale = ref(detectInitial())

if (typeof document !== 'undefined') {
  document.documentElement.lang = locale.value
}

export function setLocale(code) {
  if (!SUPPORTED.includes(code)) return
  locale.value = code
  try {
    localStorage.setItem(STORAGE_KEY, code)
  } catch {
    // ignore
  }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = code
  }
}

function getNested(obj, path) {
  return path.split('.').reduce((acc, k) => (acc == null ? acc : acc[k]), obj)
}

/**
 * t(key, vars?) — reactive translation lookup.
 * Reads `locale.value` so Vue re-renders any template that calls it
 * whenever the locale changes. Falls back to English, then to the raw key.
 */
export function t(key, vars) {
  const dict = messages[locale.value] || messages.en
  let str = getNested(dict, key)
  if (str == null) str = getNested(messages.en, key)
  if (str == null) return key
  if (vars && typeof str === 'string') {
    for (const [k, v] of Object.entries(vars)) {
      str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
    }
  }
  return str
}

export function useI18n() {
  return { t, locale, setLocale, SUPPORTED_LOCALES }
}

export default useI18n
