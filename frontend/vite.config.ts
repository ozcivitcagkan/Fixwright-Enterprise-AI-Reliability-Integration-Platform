import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development the API runs on :8000; the proxy lets the browser use one origin, as in production
const api = 'http://localhost:8000'

export default defineConfig({
  // FastAPI serves the built app under /ui/
  base: '/ui/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    proxy: {
      '/incidents': api,
      '/analyses': api,
      '/auth': api,
      '/health': api,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})