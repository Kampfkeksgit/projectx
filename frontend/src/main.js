import { createApp } from 'vue'
import './styles/tokens.css'
import './mobile/mobile.css' // Mobile-UI-Schicht (greift nur unter .mobile-ui)
import './i18n/index.js' // sets document.documentElement.lang early
import router from './router/index.js'
import App from './App.vue'
import { useAuth } from './stores/auth.js'
import { initNative } from './native/capacitor.js'
import { applyMobileClass } from './mobile/platform.js'

// Markiert <html> mit .mobile-ui in der nativen App / bei ?mobile=1.
applyMobileClass()

// Kick off the /auth/me probe immediately so the router guards can resolve.
// We do NOT await it — the guard awaits internally while pages show loading.
useAuth().fetchMe()

const app = createApp(App)
app.use(router)
app.mount('#app')

// Native (Capacitor/Android) Integration — auf dem Web ein No-Op.
initNative(router)
