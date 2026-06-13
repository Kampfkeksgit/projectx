<template>
  <LoadingPage v-if="isProcessing" :message="t('auth.completing')" />
  <div v-else class="callback-error">
    <div class="callback-error__card">
      <div class="callback-error__icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      </div>
      <h2>{{ t('auth.failedTitle') }}</h2>
      <p>{{ error || t('auth.failedGeneric') }}</p>
      <div class="callback-error__actions">
        <AppButton variant="gradient" @click="retry">{{ t('common.retry') }}</AppButton>
        <AppButton variant="ghost" @click="goHome">{{ t('common.backHome') }}</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import LoadingPage from '../components/LoadingPage.vue'
import AppButton from '../components/AppButton.vue'
import api from '../services/api.js'
import { useAuth } from '../stores/auth.js'
import { useI18n } from '../i18n/index.js'

const router = useRouter()
const auth = useAuth()
const { t } = useI18n()
const error = ref(null)
const isProcessing = ref(true)
const LAST_OAUTH_CODE_KEY = 'last_discord_oauth_code'

onMounted(async () => {
  auth.state.status = 'authenticating'
  try {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const errParam = params.get('error')

    if (errParam) {
      error.value = params.get('error_description') || errParam
      auth.state.status = 'guest'
      return
    }

    if (!code) {
      error.value = t('auth.noCode')
      auth.state.status = 'guest'
      return
    }

    const lastCode = sessionStorage.getItem(LAST_OAUTH_CODE_KEY)
    if (lastCode === code) {
      error.value = t('auth.codeReused')
      auth.state.status = 'guest'
      return
    }

    // Clear URL of the code so a refresh doesn't replay
    window.history.replaceState({}, document.title, '/auth/callback')
    sessionStorage.setItem(LAST_OAUTH_CODE_KEY, code)

    const response = await api.post('/auth/callback', { code })

    if (!response.data?.success) {
      throw new Error(response.data?.error || 'Login failed')
    }

    auth.state.user = response.data.user
    auth.state.status = 'authenticated'

    router.replace('/dashboard')
  } catch (err) {
    console.error('OAuth callback error:', err)
    error.value = err.response?.data?.details || err.response?.data?.error || err.message || 'Login failed'
    auth.state.status = 'guest'
  } finally {
    isProcessing.value = false
  }
})

function retry() {
  sessionStorage.removeItem(LAST_OAUTH_CODE_KEY)
  auth.loginWithDiscord()
}

function goHome() {
  router.replace('/')
}
</script>

<style scoped>
.callback-error {
  min-height: calc(100vh - var(--nav-height));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
}

.callback-error__card {
  max-width: 480px;
  width: 100%;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-8);
  text-align: center;
  box-shadow: var(--shadow-lg);
  animation: fade-in var(--transition-slow) var(--ease-out-expo) both;
}

.callback-error__icon {
  width: 56px;
  height: 56px;
  margin: 0 auto var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--color-danger-soft);
  color: var(--color-danger);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.callback-error h2 {
  font-size: 1.4rem;
  margin-bottom: var(--space-2);
}

.callback-error p {
  color: var(--color-text-muted);
  margin-bottom: var(--space-6);
  line-height: 1.55;
}

.callback-error__actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
  flex-wrap: wrap;
}
</style>
