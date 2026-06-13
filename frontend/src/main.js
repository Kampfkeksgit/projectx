import { createApp } from 'vue'
import './styles/tokens.css'
import './i18n/index.js' // sets document.documentElement.lang early
import router from './router/index.js'
import App from './App.vue'
import { useAuth } from './stores/auth.js'

// Kick off the /auth/me probe immediately so the router guards can resolve.
// We do NOT await it — the guard awaits internally while pages show loading.
useAuth().fetchMe()

const app = createApp(App)
app.use(router)
app.mount('#app')
