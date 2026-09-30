import { defineConfig } from 'vitest/config'
import type { ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'

// The backend only accepts writes whose Origin equals OAUTH_BASE_URL, so the dev
// proxy presents requests as coming from the backend origin.
const backend = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:7860'

const proxy: ProxyOptions = {
  target: backend,
  configure(server) {
    server.on('proxyReq', (req) => {
      if (req.getHeader('origin')) req.setHeader('origin', backend)
    })
  },
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': proxy, '/oauth/notion': proxy },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
