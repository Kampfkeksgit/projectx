/**
 * Plattform-Erkennung für die dedizierte Handy-Oberfläche.
 *
 * `isMobileUI` ist `true`, wenn die App in der nativen Capacitor-Hülle läuft
 * (Android-App). Damit die Mobile-UI auch im Browser testbar bleibt, lässt sie
 * sich per `?mobile=1` (persistiert in localStorage) erzwingen bzw. mit
 * `?mobile=0` wieder abschalten.
 *
 * WICHTIG: Auf der normalen Web-Domain (Desktop-Browser ohne Override) ist das
 * immer `false` — die bestehende Desktop-Website bleibt damit unverändert.
 */
import { computed, ref } from 'vue'
import { Capacitor } from '@capacitor/core'

const STORAGE_FORCE = 'projectx_force_mobile'
const forced = ref(false)

function readForceFlag() {
  try {
    const params = new URLSearchParams(window.location.search)
    const q = params.get('mobile')
    if (q === '1') localStorage.setItem(STORAGE_FORCE, '1')
    else if (q === '0') localStorage.removeItem(STORAGE_FORCE)
    forced.value = localStorage.getItem(STORAGE_FORCE) === '1'
  } catch {
    forced.value = false
  }
}
readForceFlag()

function detectNative() {
  try {
    return Capacitor.isNativePlatform()
  } catch {
    return false
  }
}

/** Reaktiv: rendert die App die Handy-Oberfläche? */
export const isMobileUI = computed(() => detectNative() || forced.value)

/**
 * Setzt die `mobile-ui`-Klasse auf <html>, damit die globale Mobile-CSS-Schicht
 * (mobile.css) greift. Einmalig beim Bootstrap aufrufen.
 */
export function applyMobileClass() {
  try {
    document.documentElement.classList.toggle('mobile-ui', isMobileUI.value)
  } catch {
    /* document evtl. nicht verfügbar */
  }
}

export default isMobileUI
