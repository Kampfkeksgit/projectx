/**
 * Native (Capacitor / Android) Integrationsschicht.
 *
 * WICHTIG: Dieser Code ist auf dem Web ein **No-Op**. Alle nativen Aktionen
 * sind hinter `Capacitor.isNativePlatform()` gekapselt, damit das normale
 * Web-Dashboard exakt wie bisher läuft (keine Auth-/Cookie-/Routing-Änderung).
 *
 * Die App selbst läuft im Capacitor "Remote-URL"-Modus: die native Hülle lädt
 * das deployte Dashboard (HTTPS) in einer WebView. Dadurch bleiben das
 * HTTP-only-Session-Cookie und der Discord-OAuth-Redirect unverändert
 * funktionsfähig (alles same-origin innerhalb der WebView).
 *
 * Aufgaben hier:
 *  - Statusbar (dunkel, an das Theme #0b0d12 angepasst)
 *  - Splash-Screen nach dem Laden ausblenden
 *  - Hardware-Back-Button → Vue-Router/History zurück, an der Wurzel App beenden
 *  - Externe Links (GitHub, Bot-Invite, Discord-Store) im System-Browser/
 *    In-App-Tab öffnen, statt aus der App heraus zu navigieren.
 *    (Der OAuth-LOGIN läuft über window.location und bleibt bewusst in der
 *    WebView, damit das Session-Cookie korrekt gesetzt wird.)
 */
import { Capacitor } from '@capacitor/core'

export async function initNative(router) {
  if (!Capacitor.isNativePlatform()) return

  // Module dynamisch laden — auf dem Web werden sie nie ausgeführt.
  const [{ App }, { StatusBar, Style }, { SplashScreen }, { Browser }] = await Promise.all([
    import('@capacitor/app'),
    import('@capacitor/status-bar'),
    import('@capacitor/splash-screen'),
    import('@capacitor/browser')
  ])

  // --- Statusbar ---
  try {
    await StatusBar.setStyle({ style: Style.Dark })
    await StatusBar.setBackgroundColor({ color: '#0b0d12' })
    await StatusBar.setOverlaysWebView({ overlay: false })
  } catch (e) {
    /* Plugin evtl. nicht verfügbar — ignorieren */
  }

  // --- Splash ausblenden, sobald die App-Shell steht ---
  try {
    await SplashScreen.hide()
  } catch (e) {
    /* ignorieren */
  }

  // --- Hardware-Back-Button ---
  App.addListener('backButton', ({ canGoBack }) => {
    if (canGoBack && window.history.length > 1) {
      window.history.back()
    } else {
      App.exitApp()
    }
  })

  // --- Externe Links in den System-Browser/In-App-Tab umleiten ---
  // Fängt Klicks auf <a href="https://andere-domain"> ab. Interne Links und
  // der OAuth-Login (window.location, kein <a>-Klick) sind nicht betroffen.
  document.addEventListener(
    'click',
    async (event) => {
      const anchor = event.target?.closest?.('a[href]')
      if (!anchor) return

      const href = anchor.getAttribute('href') || ''
      if (!/^https?:\/\//i.test(href)) return // relative/Anchor-Links normal lassen

      let url
      try {
        url = new URL(href, window.location.href)
      } catch {
        return
      }

      // Gleiche Domain → in der WebView lassen (normale Navigation).
      if (url.host === window.location.host) return

      // Fremde Domain → extern öffnen.
      event.preventDefault()
      try {
        await Browser.open({ url: url.href })
      } catch {
        window.open(url.href, '_blank')
      }
    },
    true
  )
}

export default initNative
