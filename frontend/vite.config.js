import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { readAllowedHosts, domainSettingsPlugin } from './domain-settings.js'

const settingsPath = process.env.MARCHITECT_DOMAIN_SETTINGS_FILE ||
  fileURLToPath(new URL('../data/frontend-settings/domains.json', import.meta.url))

// https://vite.dev/config/
export default defineConfig(() => ({
  plugins: [react(), domainSettingsPlugin(settingsPath)],
  server: {
    // Allow access through the server's public DNS name in development.
    allowedHosts: readAllowedHosts(settingsPath),
    // Match production's /api reverse-proxy path while developing with Vite.
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
}))
