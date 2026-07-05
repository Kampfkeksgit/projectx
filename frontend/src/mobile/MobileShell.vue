<template>
  <div class="m-shell">
    <MaintenanceBanner />
    <AnnouncementBanner />
    <MobileTopBar @open-account="accountOpen = true" />

    <main class="m-shell__main">
      <router-view v-slot="{ Component }">
        <transition name="m-page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- Footer (Brand/Version + Rechtliches: Impressum/Datenschutz/AGB/Team).
         In einen Wrapper gepackt, damit die fixe Bottom-Nav ihn bei
         eingeloggten Nutzern nicht überdeckt. -->
    <div class="m-shell__footer" :class="{ 'm-shell__footer--tabbar': authed }">
      <AppFooter />
    </div>

    <MobileTabBar v-if="authed" @open-account="accountOpen = true" />

    <MobileAccountSheet :open="accountOpen" @close="accountOpen = false" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useAuth } from '../stores/auth.js'
import MobileTopBar from './MobileTopBar.vue'
import MobileTabBar from './MobileTabBar.vue'
import MobileAccountSheet from './MobileAccountSheet.vue'
import MaintenanceBanner from '../components/MaintenanceBanner.vue'
import AnnouncementBanner from '../components/AnnouncementBanner.vue'
import AppFooter from '../components/AppFooter.vue'

const auth = useAuth()
const accountOpen = ref(false)
const authed = computed(() => auth.state.status === 'authenticated')
</script>

<style scoped>
.m-shell {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}

.m-shell__main {
  flex: 1 0 auto;
  display: flex;
  flex-direction: column;
}

.m-shell__main > * {
  flex: 1 0 auto;
}

/* Footer sitzt am Seitenende. Basis-Safe-Area (Gesten-Leiste), damit die
   Links nicht am Bildschirmrand kleben. */
.m-shell__footer {
  flex-shrink: 0;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}

/* Eingeloggt: die fixe Bottom-Nav liegt darüber → genug Freiraum lassen,
   damit die Footer-Links nicht dahinter verschwinden. */
.m-shell__footer--tabbar {
  padding-bottom: calc(var(--mobile-tabbar-h, 64px) + env(safe-area-inset-bottom, 0px) + var(--space-3));
}

.m-page-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.m-page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.m-page-enter-active,
.m-page-leave-active {
  transition: opacity 180ms ease, transform 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
