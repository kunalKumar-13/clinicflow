import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the Vite dev server proxies /api to the backend so the browser
// only ever talks to one origin. In production Nginx does the same job.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
