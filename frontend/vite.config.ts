/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  envDir: '..',
  server: {
    port: 3000,
    host: true,
  },
  // Vitest config (ignored by Vite, used by Vitest).
  // Vite's config types don't include `test` in some setups, so we widen the config.
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
  },
} as any)
