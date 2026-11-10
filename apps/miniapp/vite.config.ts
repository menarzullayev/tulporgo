/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Served as static files at settings.miniapp_url (https://tulporgo.uz/app): relative base + hash routing,
// so no server-side rewrites are needed. The API lives at /api on the same origin (override with VITE_API_BASE).
export default defineConfig({
  base: './',
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { target: 'es2022', sourcemap: false },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
