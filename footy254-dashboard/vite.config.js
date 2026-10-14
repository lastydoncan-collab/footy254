import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend (uvicorn, port 8000) serves the API under /api. In development
// Vite proxies /api to it, so the browser only ever talks to ONE origin - the
// same shape as production - and the app also works from a phone on the LAN
// (http://<your-pc-ip>:5173) with no address configured anywhere.
const API_TARGET = process.env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8000'

const proxy = {
  '/api': { target: API_TARGET, changeOrigin: false },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy,
  },
  preview: {
    host: true,
    port: 4173,
    proxy,
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (/react-router|react-dom|[\\/]react[\\/]|scheduler/.test(id)) return 'react'
          if (id.includes('framer-motion')) return 'motion'
          if (id.includes('lucide-react')) return 'icons'
          return undefined
        },
      },
    },
  },
})
