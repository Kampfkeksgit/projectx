import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Polling-Watcher: native fs.watch (Windows ReadDirectoryChangesW) wirft auf
// nicht-Standard-Laufwerken (subst-Mounts, Netzwerk-Shares, OneDrive, externe
// Drives) sporadisch ECONNRESET und killt den Dev-Server. Polling ist langsamer
// (CPU-Last), läuft aber überall stabil.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:3000'
    },
    watch: {
      usePolling: true,
      interval: 300
    }
  }
})
