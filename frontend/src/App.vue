<template>
  <!-- Native App / ?mobile=1 → eigene Handy-Oberfläche (eigene Top-Bar +
       Bottom-Navigation). Desktop-Web rendert unverändert die klassische Shell. -->
  <MobileShell v-if="isMobileUI" />

  <div v-else class="app">
    <MaintenanceBanner />
    <AnnouncementBanner />
    <AppNavBar />
    <main class="app__main">
      <router-view v-slot="{ Component }">
        <transition name="route" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <AppFooter />
    <CookieBanner />
  </div>

  <!-- Toasts global über beiden Shells. -->
  <AppToast />
</template>

<script setup>
import AppNavBar from './components/AppNavBar.vue'
import AppToast from './components/AppToast.vue'
import MaintenanceBanner from './components/MaintenanceBanner.vue'
import AnnouncementBanner from './components/AnnouncementBanner.vue'
import AppFooter from './components/AppFooter.vue'
import CookieBanner from './components/CookieBanner.vue'
import MobileShell from './mobile/MobileShell.vue'
import { isMobileUI } from './mobile/platform.js'
</script>

<style>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app__main {
  flex: 1 0 auto;
  display: flex;
  flex-direction: column;
}

.app__main > * {
  flex: 1 0 auto;
}

.route-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.route-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.route-enter-active,
.route-leave-active {
  transition: opacity 220ms ease, transform 240ms cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
